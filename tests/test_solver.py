from __future__ import annotations

from types import SimpleNamespace

from vulnclaw.agent import solver
from vulnclaw.agent.blackboard import Blackboard, IntentStatus


def _fake_agent(tool_outputs: list[str] | None = None):
    state = SimpleNamespace(board=Blackboard(), save=lambda: None)
    context = SimpleNamespace(state=state, add_user_message=lambda *a: None)
    queue = list(tool_outputs or [])

    async def _execute(tool_name, tool_args):
        return queue.pop(0) if queue else "Status: 200"

    return SimpleNamespace(context=context, _execute_mcp_tool=_execute)


def test_flag_evidence_helpers():
    assert solver._extract_flags("got flag{abc} and ctfshow{xyz}") == ["flag{abc}", "ctfshow{xyz}"]
    # 声称的 flag 不在证据中 → 判定未验证
    assert solver._unverified_flags("flag{fake}", "server said: error") == ["flag{fake}"]
    # 在证据中 → 视为已验证
    assert solver._unverified_flags("flag{real}", "body: flag{real}") == []
    # flag 目标但证据无 flag → 完成不成立
    ok, _ = solver._completion_is_grounded("找到 flag", "only status 200")
    assert ok is False
    ok2, _ = solver._completion_is_grounded("找到 flag", "leaked flag{x}")
    assert ok2 is True
    # 非 flag 目标 → 不强制
    ok3, _ = solver._completion_is_grounded("枚举子域名", "")
    assert ok3 is True


def test_extract_json_handles_fences_and_noise():
    assert solver._extract_json('```json\n{"complete": "ok"}\n```') == {"complete": "ok"}
    assert solver._extract_json('prefix {"intents": []} suffix') == {"intents": []}
    assert solver._extract_json("not json at all") is None


async def test_solve_completes_when_reason_signals_goal(monkeypatch):
    calls = {"reason": 0}

    async def fake_reason(agent, board, max_intents):
        calls["reason"] += 1
        if calls["reason"] == 1:
            return {"intents": [{"from": [], "description": "test sqli bypass"}]}
        return {"complete": "flag{captured} 已验证"}

    async def fake_explore(agent, board, intent, *, max_tool_rounds, evidence_buffer, stream_sink=None):
        # 模拟真实工具输出里出现了 flag（证据闸门据此放行）
        evidence_buffer.append("HTTP 200\n<html>... flag{captured} ...</html>")
        return True, "sqli 确认，提取到 flag{captured}"

    monkeypatch.setattr(solver, "reason_step", fake_reason)
    monkeypatch.setattr(solver, "explore_step", fake_explore)

    events: list[str] = []
    result = await solver.solve(
        _fake_agent(),
        origin="http://t",
        goal="flag",
        max_steps=10,
        on_event=lambda kind, payload: events.append(kind),
    )

    assert result.completed is True
    assert "flag{captured}" in result.reason
    # origin fact + 1 concluded fact
    assert result.facts == 2
    assert "conclude" in events


async def test_solve_completes_immediately_on_verified_flag(monkeypatch):
    """探索一拿到有真实证据的 flag 就立即完成，不再多跑验证轮。"""
    reason_calls = {"n": 0}

    async def fake_reason(agent, board, max_intents):
        reason_calls["n"] += 1
        return {"intents": [{"from": [], "description": "union inject"}]}

    async def fake_explore(agent, board, intent, *, max_tool_rounds, evidence_buffer, stream_sink=None):
        evidence_buffer.append("欢迎你，flag{real_one}")  # 真实工具输出含 flag
        return True, "union 注入回显 flag{real_one}"

    monkeypatch.setattr(solver, "reason_step", fake_reason)
    monkeypatch.setattr(solver, "explore_step", fake_explore)

    result = await solver.solve(_fake_agent(), origin="t", goal="找到 flag", max_steps=10)

    assert result.completed is True
    assert "flag{real_one}" in result.board.complete_reason
    # 拿到 flag 立即收敛：reason 只被调用一次，不再进入下一轮验证
    assert reason_calls["n"] == 1


async def test_solve_rejects_hallucinated_flag(monkeypatch):
    """结论声称的 flag 不在真实工具输出里 → 判定幻觉、拒绝、不完成。"""
    reason_calls = {"n": 0}

    async def fake_reason(agent, board, max_intents):
        reason_calls["n"] += 1
        if reason_calls["n"] == 1:
            return {"intents": [{"from": [], "description": "test sqli"}]}
        return {}  # 之后不再提出 → 前沿耗尽

    async def fake_explore(agent, board, intent, *, max_tool_rounds, evidence_buffer, stream_sink=None):
        # 不往 evidence_buffer 写 flag —— 模拟模型凭空编造
        return True, "成功拿到 flag{HALLUCINATED}"

    monkeypatch.setattr(solver, "reason_step", fake_reason)
    monkeypatch.setattr(solver, "explore_step", fake_explore)

    events: list[str] = []
    result = await solver.solve(
        _fake_agent(),
        origin="t",
        goal="找到 flag",
        max_steps=10,
        on_event=lambda kind, payload: events.append(kind),
    )

    assert result.completed is False
    assert "hallucination" in events
    # 被拒绝的旗标产生一条 [未验证] 事实
    assert any("[未验证]" in f.description for f in result.board.facts)


async def test_solve_rejects_ungrounded_completion(monkeypatch):
    """目标要 flag，但真实工具输出里从未出现 flag → 拒绝 Reason 的完成声明。"""
    reason_calls = {"n": 0}

    async def fake_reason(agent, board, max_intents):
        reason_calls["n"] += 1
        if reason_calls["n"] == 1:
            return {"complete": "我觉得已经拿到 flag 了"}  # 无任何证据支撑
        return {}  # 之后不再提出 → 前沿耗尽

    async def fake_explore(agent, board, intent, *, max_tool_rounds, evidence_buffer, stream_sink=None):
        return True, "x"

    monkeypatch.setattr(solver, "reason_step", fake_reason)
    monkeypatch.setattr(solver, "explore_step", fake_explore)

    events: list[str] = []
    result = await solver.solve(
        _fake_agent(),
        origin="t",
        goal="找到 flag",
        max_steps=10,
        on_event=lambda kind, payload: events.append(kind),
    )

    assert result.completed is False
    assert "complete_rejected" in events


async def test_solve_stops_when_frontier_exhausted(monkeypatch):
    async def fake_reason_noop(agent, board, max_intents):
        return {}  # never proposes intents

    async def fake_explore(agent, board, intent, *, max_tool_rounds, evidence_buffer, stream_sink=None):
        return True, "unused"

    monkeypatch.setattr(solver, "reason_step", fake_reason_noop)
    monkeypatch.setattr(solver, "explore_step", fake_explore)

    result = await solver.solve(_fake_agent(), origin="t", goal="g", max_steps=10)

    assert result.completed is False
    assert result.reason == "探索前沿耗尽"
    # only the seeded origin fact
    assert result.facts == 1


async def test_solve_abandons_unproductive_intent(monkeypatch):
    state = {"reason": 0}

    async def fake_reason(agent, board, max_intents):
        state["reason"] += 1
        if state["reason"] == 1:
            return {"intents": [{"from": [], "description": "dead path"}]}
        return {}  # afterward propose nothing -> frontier exhausts

    async def fake_explore(agent, board, intent, *, max_tool_rounds, evidence_buffer, stream_sink=None):
        return False, "该方向走不通"

    monkeypatch.setattr(solver, "reason_step", fake_reason)
    monkeypatch.setattr(solver, "explore_step", fake_explore)

    result = await solver.solve(_fake_agent(), origin="t", goal="g", max_steps=10)

    assert result.completed is False
    board = result.board
    assert board.intents[0].status == IntentStatus.ABANDONED
    assert board.intents[0].note == "该方向走不通"


async def test_solve_respects_safety_step_budget(monkeypatch):
    async def fake_reason(agent, board, max_intents):
        # always propose a fresh intent -> would loop forever without the cap
        return {"intents": [{"from": [], "description": "endless"}]}

    async def fake_explore(agent, board, intent, *, max_tool_rounds, evidence_buffer, stream_sink=None):
        return True, "step fact"

    monkeypatch.setattr(solver, "reason_step", fake_reason)
    monkeypatch.setattr(solver, "explore_step", fake_explore)

    result = await solver.solve(_fake_agent(), origin="t", goal="g", max_steps=3)

    assert result.completed is False
    assert result.reason == "触达安全预算上限"
    assert result.steps == 3
