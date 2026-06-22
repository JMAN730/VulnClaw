"""目标驱动的 OODA 求解循环 — 用黑板图替代固定轮数工作流。

循环结构（无固定轮数）：
  1. 用 origin/goal 播种初始 Fact。
  2. REASON：读全图 → 判断目标是否达成 / 提出新的探索 Intent / 不提出。
  3. EXPLORE：领取一个 Intent，用工具实际执行，把确认的结论写回为一个新 Fact。
  4. 终止条件：目标达成 / 探索前沿耗尽（无 Intent 且 Reason 不再提出）/ 触达安全预算。

安全预算（max_steps）只是防止失控的兜底上限，不是工作流阶段计数；
正常情况下循环会在「目标达成」或「前沿耗尽」时提前结束。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from vulnclaw.agent.blackboard import Blackboard, BoardIntent
from vulnclaw.agent.llm_client import build_chat_completion_kwargs, call_llm_auto
from vulnclaw.agent.think_filter import strip_think_tags

# 探索阶段判定「已推进/已确认结论」的信号
_ADVANCE_MARKERS = [
    "确认",
    "成功",
    "拿到",
    "获取到",
    "提取到",
    "flag{",
    "flag ",
    "绕过成功",
    "回显",
    "漏洞存在",
]
# 探索阶段判定「该方向走不通」的信号
_DEAD_END_MARKERS = [
    "不存在",
    "无法",
    "失败",
    "走不通",
    "没有发现",
    "无注入",
    "无回显",
    "排除",
]


@dataclass
class SolveResult:
    completed: bool
    reason: str
    steps: int
    facts: int
    board: Blackboard


# 形如 flag{...} / ctfshow{...} / NSSCTF{...} 的旗标
_FLAG_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,20}\{[^{}\n]{1,200}\}")


def _extract_flags(text: str) -> list[str]:
    """抽取文本中所有 flag 形态的 token（去重保序）。"""
    return list(dict.fromkeys(_FLAG_RE.findall(text or "")))


def _goal_wants_flag(goal: str) -> bool:
    g = (goal or "").lower()
    return any(k in g for k in ("flag", "夺旗", "ctf", "shell", "getshell"))


def _unverified_flags(claim: str, evidence: str) -> list[str]:
    """返回在 claim 中声称、但未在真实工具证据中出现的 flag（疑似幻觉）。"""
    return [f for f in _extract_flags(claim) if f not in evidence]


def _completion_is_grounded(goal: str, evidence: str) -> tuple[bool, str]:
    """完成判定的证据校验：若目标要求 flag，则真实工具输出里必须真的出现过 flag。"""
    if not _goal_wants_flag(goal):
        return True, ""
    if _extract_flags(evidence):
        return True, ""
    return False, "目标要求 flag，但任何真实工具输出中都没有出现 flag，判定为未验证/疑似幻觉"


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 回复中稳健地抽取一个 JSON 对象。"""
    if not text:
        return None
    cleaned = strip_think_tags(text).strip()
    # 去掉 ```json ... ``` 代码围栏
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    # 直接尝试
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except (ValueError, TypeError):
        pass
    # 退化：抓取第一个平衡花括号块
    start = cleaned.find("{")
    if start < 0:
        return None
    depth = 0
    for idx in range(start, len(cleaned)):
        ch = cleaned[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                with_suppress = cleaned[start : idx + 1]
                try:
                    obj = json.loads(with_suppress)
                    return obj if isinstance(obj, dict) else None
                except (ValueError, TypeError):
                    return None
    return None


async def _structured_call(agent: Any, prompt: str, *, max_tokens: int = 900) -> str:
    """无工具的结构化 LLM 调用（用于 Reason / Conclude）。"""
    client = agent._get_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs = build_chat_completion_kwargs(agent, messages, max_tokens=max_tokens, temperature=0.2)
    response = client.chat.completions.create(**kwargs)
    if response and response.choices:
        return response.choices[0].message.content or ""
    return ""


def _reason_prompt(board: Blackboard, max_intents: int) -> str:
    return (
        "你是该领域的资深渗透专家。下面是当前任务的「黑板图」快照：facts 是已确认的客观事实，"
        "intents 是探索方向。图从 facts 出发、通过 intent 探索得到新的 fact，逐步逼近 goal。\n\n"
        "请判断两件事：① 现有 facts 是否已满足 goal；② 若未满足，是否应提出新的探索方向。\n\n"
        "只返回一个 JSON 对象，不要输出别的内容：\n"
        '- 若 goal 已达成： {"complete": "引用具体 fact id 说明为何现有客观事实足以证明目标达成"}\n'
        '- 若未达成且应提出新方向： {"intents": [{"from": ["f001"], "description": "高价值且独立的探索方向"}]}\n'
        '- 若未达成但当前不必新增方向： {}\n\n'
        "规则：\n"
        "- **完成判定必须基于 facts 里已确认的客观事实**，不得基于猜测或愿望。若 goal 要求 flag，"
        "则 facts 中必须有一条记录了**真实拿到的 flag 值**才能 complete；只要 flag 来源可疑/未被工具输出证实，"
        "一律视为未达成，继续提方向去验证，绝不能 complete。\n"
        "- 若某条 fact 标注了 [未验证]/[拒绝完成]/疑似幻觉，绝对不能据此判定达成。\n"
        "- 若没有任何处于 open 的 intent，则必须提出新方向。\n"
        f"- 一次最多提出 {max_intents} 个高价值、互不重叠、可独立推进的方向，每个聚焦核心思路。\n"
        "- 反思是否走偏：若之前方向无效，提出能纠偏的新方向。\n"
        "- description 简洁聚焦，不要冗长；不同 intent 覆盖不同维度。\n\n"
        "## 黑板图\n```\n" + board.to_prompt_graph() + "\n```\n"
    )


def _conclude_prompt(board: Blackboard, intent: BoardIntent, evidence: str) -> str:
    return (
        "现在是「结论阶段」。它覆盖之前一切让你继续探索/继续发请求/继续等待结果的指令——立即停止动作，只做总结。\n"
        "你只能基于「真实工具输出」里**已经实际确认**的信息来总结，不得继续调用工具、不得等待未完成的结果。\n\n"
        "只返回一个 JSON 对象：\n"
        '{"advanced": true/false, "fact": "本次新确认的客观事实（增量）"}\n\n'
        "铁律（违反即视为失败）：\n"
        "- fact 必须是**已被真实工具输出证实**的客观事实，不得是计划、猜测、推断或填充性描述。\n"
        "- **严禁编造 flag/shell/密码/数据**。任何 flag 只有在下方「真实工具输出」中**逐字符出现过**才能写进 fact；"
        "若工具输出里没有，就绝对不能声称拿到了 flag——这种情况 advanced=false。\n"
        "- advanced=true 仅当本次探索有**工具输出支撑的**实质推进（确认注入点/绕过/拿到真实回显数据等）。\n"
        "- advanced=false 表示该方向走不通或暂无被证实的结论；此时 fact 写明客观观察（如『响应返回 sql inject error，注入被过滤』）。\n"
        "- 不要放大段原始数据，不要重复图里已有信息。\n\n"
        f"## 当前探索方向 {intent.id}\n{intent.description}\n\n"
        "## 本次探索的真实工具输出（你唯一可信的事实来源）\n```\n" + (evidence.strip() or "(无工具输出)") + "\n```\n\n"
        "## 黑板图\n```\n" + board.to_prompt_graph() + "\n```\n"
    )


def _explore_context(board: Blackboard, intent: BoardIntent, step: int, max_rounds: int) -> str:
    from_desc = ""
    if intent.from_facts:
        refs = [board.get_fact(fid) for fid in intent.from_facts]
        from_desc = "\n".join(f"  - {f.id}: {f.description}" for f in refs if f)
        from_desc = f"\n基于已知事实：\n{from_desc}"
    return (
        f"[探索方向 {intent.id} · 第 {step}/{max_rounds} 步]\n"
        f"目标(goal): {board.goal}\n"
        f"当前探索方向：{intent.description}{from_desc}\n\n"
        "请只围绕这个方向用工具实际执行（发请求/构造 payload/解析响应），不要泛泛而谈。\n"
        "每一步都要有真实的工具调用与对响应的具体分析；若该方向确认走不通就明确说明并停止。\n"
    )


async def reason_step(agent: Any, board: Blackboard, max_intents: int) -> dict:
    raw = await _structured_call(agent, _reason_prompt(board, max_intents), max_tokens=1200)
    parsed = _extract_json(raw)
    return parsed or {}


async def explore_step(
    agent: Any,
    board: Blackboard,
    intent: BoardIntent,
    *,
    max_tool_rounds: int,
    evidence_buffer: list[str],
    stream_sink: Any = None,
) -> tuple[bool, str]:
    """围绕一个 Intent 实际探索，返回 (是否推进, 结论事实描述)。

    结论阶段只喂给模型「本次探索真实捕获的工具输出」作为唯一可信事实来源，降低幻觉。
    """
    system_prompt = agent._build_system_prompt(
        agent.context.state.target, auto_mode=True, user_input=intent.description
    )
    evidence_start = len(evidence_buffer)
    last_text = ""
    for step in range(1, max_tool_rounds + 1):
        ctx = _explore_context(board, intent, step, max_tool_rounds)
        text = await call_llm_auto(agent, system_prompt, ctx, stream_sink=stream_sink)
        last_text = text or ""
        agent.context.add_assistant_message(f"[探索 {intent.id} 第{step}步] {last_text}")
        # 复用既有的发现提取逻辑
        if hasattr(agent, "_finding_parser"):
            agent._finding_parser.parse(last_text)
        lowered = last_text.lower()
        # 早停：明确推进或明确死路
        if any(m.lower() in lowered for m in _ADVANCE_MARKERS):
            break
        if any(m in last_text for m in _DEAD_END_MARKERS) and step >= 2:
            break

    # 本次探索真实捕获的工具输出（HTTP 响应 / python_execute 输出等）
    intent_evidence = "\n".join(evidence_buffer[evidence_start:])[-6000:]
    raw = await _structured_call(
        agent, _conclude_prompt(board, intent, intent_evidence), max_tokens=600
    )
    parsed = _extract_json(raw) or {}
    advanced = bool(parsed.get("advanced"))
    fact = str(parsed.get("fact", "")).strip()
    if not fact:
        fact = strip_think_tags(last_text).strip()[:200]
    return advanced, fact


async def solve(
    agent: Any,
    *,
    origin: str,
    goal: str,
    hints: Optional[list[str]] = None,
    max_steps: int = 40,
    max_intents: int = 3,
    max_tool_rounds: int = 4,
    stream_sink: Any = None,
    on_event: Optional[Callable[[str, dict], None]] = None,
) -> SolveResult:
    """运行目标驱动的求解循环，直到目标达成 / 前沿耗尽 / 触达安全预算。"""
    board = agent.context.state.board
    board.origin = origin or board.origin
    board.goal = goal or board.goal

    def emit(kind: str, payload: dict) -> None:
        if on_event is not None:
            on_event(kind, payload)

    # 真实工具输出缓冲区——所有 flag/完成判定的唯一可信证据来源
    evidence_buffer: list[str] = []
    original_execute = agent._execute_mcp_tool

    async def _recording_execute(tool_name: str, tool_args: dict) -> str:
        output = await original_execute(tool_name, tool_args)
        evidence_buffer.append(str(output))
        if len(evidence_buffer) > 400:
            del evidence_buffer[:200]
        return output

    agent._execute_mcp_tool = _recording_execute  # type: ignore[method-assign]

    try:
        # 播种初始事实
        if not board.facts:
            seed = f"目标 origin={origin}；目标 goal={goal}"
            if hints:
                seed += "；提示：" + " | ".join(hints)
            board.add_fact(seed, source="origin")

        empty_reason_streak = 0
        consecutive_errors = 0
        steps = 0

        while steps < max_steps and not board.completed:
            try:
                decision = await reason_step(agent, board, max_intents)
            except Exception as exc:  # LLM/网络异常：不崩溃，累计熔断
                consecutive_errors += 1
                emit("error", {"phase": "reason", "error": str(exc)})
                if consecutive_errors >= 3:
                    break
                continue
            emit("reason", {"decision": decision, "step": steps})

            complete_reason = decision.get("complete")
            if complete_reason:
                full_evidence = "\n".join(evidence_buffer)
                grounded, why = _completion_is_grounded(board.goal, full_evidence)
                fake = _unverified_flags(str(complete_reason), full_evidence)
                if grounded and not fake:
                    board.mark_complete(str(complete_reason))
                    break
                # 完成声明缺乏真实证据 → 拒绝，写入纠偏事实，继续探索
                reject_reason = why or f"完成声明引用的 flag {fake[0]} 未在真实工具输出中出现"
                board.add_fact(f"[拒绝完成] {reject_reason}；继续探索验证", source="verify")
                emit("complete_rejected", {"reason": reject_reason})
                continue

            for item in decision.get("intents") or []:
                desc = (item or {}).get("description", "").strip() if isinstance(item, dict) else ""
                if desc:
                    board.add_intent(desc, (item or {}).get("from"))

            open_intents = board.open_intents()
            if not open_intents:
                empty_reason_streak += 1
                if empty_reason_streak >= 2:
                    # 探索前沿耗尽：Reason 连续不再提出新方向
                    break
                continue
            empty_reason_streak = 0

            intent = open_intents[0]
            board.claim_intent(intent.id)
            emit("explore_start", {"intent_id": intent.id, "description": intent.description})

            try:
                advanced, fact = await explore_step(
                    agent,
                    board,
                    intent,
                    max_tool_rounds=max_tool_rounds,
                    evidence_buffer=evidence_buffer,
                    stream_sink=stream_sink,
                )
            except Exception as exc:  # 探索异常：放弃该 intent，累计熔断
                consecutive_errors += 1
                board.abandon_intent(intent.id, note=f"探索异常: {exc}")
                emit("error", {"phase": "explore", "intent_id": intent.id, "error": str(exc)})
                if consecutive_errors >= 3:
                    break
                continue
            consecutive_errors = 0

            # 证据闸门：结论里声称的 flag 必须在真实工具输出里逐字符出现过
            full_evidence = "\n".join(evidence_buffer)
            fake_flags = _unverified_flags(fact, full_evidence)
            if fake_flags:
                note = f"声称获得 flag {fake_flags[0]} 但未在任何真实工具输出中出现，判定为幻觉，已拒绝"
                board.abandon_intent(intent.id, note=note)
                board.add_fact(f"[未验证] 探索 {intent.id}：{note}", source="verify")
                emit("hallucination", {"intent_id": intent.id, "flags": fake_flags})
            elif advanced and fact:
                new_fact = board.conclude_intent(intent.id, fact)
                emit(
                    "conclude",
                    {"intent_id": intent.id, "fact": new_fact.id if new_fact else "", "desc": fact},
                )
                # 拿到经证据验证的 flag 即刻收敛，不再多跑验证轮
                captured = _extract_flags(fact)
                if captured and _goal_wants_flag(board.goal):
                    board.mark_complete(
                        f"已从 {new_fact.id if new_fact else 'fact'} 验证获取 flag: {captured[0]}"
                    )
                    emit("reason", {"decision": {"complete": board.complete_reason}, "step": steps})
                    break
            else:
                board.abandon_intent(intent.id, note=(fact or "未推进")[:120])
                emit("abandon", {"intent_id": intent.id, "note": fact})

            steps += 1
            agent.context.state.save()
    finally:
        agent._execute_mcp_tool = original_execute  # type: ignore[method-assign]

    reason = (
        board.complete_reason
        if board.completed
        else ("探索前沿耗尽" if steps < max_steps else "触达安全预算上限")
    )
    return SolveResult(
        completed=board.completed,
        reason=reason,
        steps=steps,
        facts=len(board.facts),
        board=board,
    )
