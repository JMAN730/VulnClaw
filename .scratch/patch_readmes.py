"""Apply OpenRouter-only README edits onto upstream HEAD versions."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dump(path: str) -> str:
    data = subprocess.check_output(["git", "show", f"HEAD:{path}"])
    return data.decode("utf-8")


OPENROUTER_SECTION_ZH = """
### OpenRouter 安全与路由说明

```bash
vulnclaw config provider openrouter
vulnclaw config set llm.api_key <openrouter-inference-key>
```

OpenRouter 是模型网关，不是单一上游模型提供商。VulnClaw 使用标准静态推理密钥和现有的 `llm.api_key` / `llm.api_keys`、`VULNCLAW_LLM_API_KEY` / `VULNCLAW_LLM_API_KEYS` 配置；请使用专用推理密钥，并在 OpenRouter 中设置消费上限和适当的有效期，不要使用管理密钥。

默认路由可能在多个上游模型提供商之间选择并在请求开始输出前回退，因此一个 Model ID 不保证固定上游。VulnClaw 会要求上游支持发送的工具和生成参数，但首个版本不提供 OpenRouter 专属的路由、回退或隐私开关。

OpenRouter 会保留请求元数据；被选中的上游提供商还有各自独立的数据保留和训练政策。处理敏感目标数据前，请检查 OpenRouter 账户级隐私、数据收集和 ZDR 设置以及候选上游政策。ZDR 可限制路由范围，但不能在本文中视为无条件的端到端零保留保证。

免费模型变体通常有更低的限额和可用性；动态路由器还会降低上游选择、价格和输出的确定性。它们适合试用，不是 VulnClaw 的生产默认模型。详见 [OpenRouter 路由](https://openrouter.ai/docs/guides/routing/provider-selection) 和 [隐私与日志](https://openrouter.ai/docs/guides/privacy/provider-logging)。

"""

OPENROUTER_SECTION_EN = """
### OpenRouter security and routing notes

```bash
vulnclaw config provider openrouter
vulnclaw config set llm.api_key <openrouter-inference-key>
```

OpenRouter is a model gateway, not a single upstream model provider. VulnClaw uses a standard static inference key through the existing `llm.api_key` / `llm.api_keys` and `VULNCLAW_LLM_API_KEY` / `VULNCLAW_LLM_API_KEYS` settings. Use a dedicated inference key with a spend limit and an appropriate expiry in OpenRouter; do not use management keys.

Default routing may choose among multiple upstream model providers and can fall back before a request starts producing output, so one Model ID does not guarantee a fixed upstream. VulnClaw requires upstream support for the tools and generation parameters it sends, but v1 does not expose OpenRouter-specific routing, fallback, or privacy controls.

OpenRouter retains request metadata, and selected upstream providers have their own retention and training policies. Before handling sensitive target data, review OpenRouter account-level privacy, data-collection, and ZDR settings plus candidate upstream policies. ZDR can constrain routing, but it must not be treated as an unconditional end-to-end zero-retention guarantee in this document.

Free model variants usually have lower limits and availability; dynamic routers also reduce upstream, pricing, and output determinism. They are fine for trials, not VulnClaw's production default. See [OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection) and [privacy / logging](https://openrouter.ai/docs/guides/privacy/provider-logging).

"""


def patch_zh(text: str) -> str:
    text = text.replace(
        "- **13 个 LLM Provider** — OpenAI / Anthropic / MiniMax / DeepSeek / 智谱 / Moonshot / 千问 / SiliconFlow / 豆包 / 百川 / 阶跃星辰 / 商汤 / 零一万物，一键切换",
        "- **14 个 LLM Provider** — OpenAI / OpenRouter / Anthropic / MiniMax / DeepSeek / 智谱 / Moonshot / 千问 / SiliconFlow / 豆包 / 百川 / 阶跃星辰 / 商汤 / 零一万物，一键切换",
        1,
    )
    text = text.replace(
        "vulnclaw config provider minimax   (或 openai/anthropic/deepseek/zhipu/moonshot/qwen/siliconflow)",
        "vulnclaw config provider minimax   (或 openai/openrouter/anthropic/deepseek/zhipu/moonshot/qwen/siliconflow)",
        1,
    )
    text = text.replace(
        "VulnClaw 支持 OpenAI 兼容协议的 API，内置 13 个提供商预设并支持自定义端点：",
        "VulnClaw 支持 OpenAI 兼容协议的 API，内置 14 个提供商预设并支持自定义端点：",
        1,
    )
    # Insert OpenRouter row after OpenAI in provider table
    openai_row = "| OpenAI      | `provider openai`      | gpt-4o                |"
    openrouter_row = "| OpenRouter（模型网关） | `provider openrouter` | openai/gpt-4o |"
    if openrouter_row not in text:
        if openai_row not in text:
            raise SystemExit("zh: OpenAI provider row not found")
        text = text.replace(openai_row, openai_row + "\n" + openrouter_row, 1)

    # Insert OpenRouter section before architecture / after provider table
    if "### OpenRouter 安全与路由说明" not in text:
        # Prefer inserting after the custom provider row / before --- following provider table
        anchor = "| 自定义      | `provider custom`      | 手动填写              |\n\n---"
        alt = "| 自定义 | `provider custom` | 手动填写 |\n\n---"
        if anchor in text:
            text = text.replace(anchor, "| 自定义      | `provider custom`      | 手动填写              |\n" + OPENROUTER_SECTION_ZH + "---", 1)
        elif alt in text:
            text = text.replace(alt, "| 自定义 | `provider custom` | 手动填写 |\n" + OPENROUTER_SECTION_ZH + "---", 1)
        else:
            # try looser match
            m = re.search(r"\| 自定义.*手动填写.*\|\n\n---", text)
            if not m:
                raise SystemExit("zh: could not find provider table end to insert OpenRouter section")
            text = text[: m.end() - 3] + OPENROUTER_SECTION_ZH + "---" + text[m.end() :]

    text = text.replace(
        "| **配置管理** | `config/schema.py` + `settings.py` | Pydantic + YAML + 13 Provider 预设 |",
        "| **配置管理** | `config/schema.py` + `settings.py` | Pydantic + YAML + 14 Provider 预设 |",
        1,
    )
    # config table provider description
    text = text.replace(
        "| `llm.provider` | openai | LLM 提供商 |",
        "| `llm.provider` | openai | LLM 提供商（14 个内置 + custom） |",
        1,
    )
    return text


def patch_en(text: str) -> str:
    text = text.replace(
        "- **13 LLM Providers** — OpenAI / Anthropic / MiniMax / DeepSeek / Zhipu / Moonshot / Qwen / SiliconFlow / Doubao / Baichuan / StepFun / SenseTime / Yi, one-command switch",
        "- **14 LLM Providers** — OpenAI / OpenRouter / Anthropic / MiniMax / DeepSeek / Zhipu / Moonshot / Qwen / SiliconFlow / Doubao / Baichuan / StepFun / SenseTime / Yi, one-command switch",
        1,
    )
    text = text.replace(
        "vulnclaw config provider minimax   (or openai/anthropic/deepseek/zhipu/moonshot/qwen/siliconflow)",
        "vulnclaw config provider minimax   (or openai/openrouter/anthropic/deepseek/zhipu/moonshot/qwen/siliconflow)",
        1,
    )
    text = text.replace(
        "VulnClaw supports OpenAI-compatible APIs with 13 built-in provider presets plus custom endpoints:",
        "VulnClaw supports OpenAI-compatible APIs with 14 built-in provider presets plus custom endpoints:",
        1,
    )
    # common EN variant
    text = text.replace(
        "built-in 13 provider presets",
        "built-in 14 provider presets",
    )
    text = text.replace(
        "13 built-in providers",
        "14 built-in providers",
    )

    openai_row = "| OpenAI      | `provider openai`      | gpt-4o                |"
    openrouter_row = "| OpenRouter (model gateway) | `provider openrouter` | openai/gpt-4o |"
    # try common variants
    candidates = [
        "| OpenAI | `provider openai` | gpt-4o |",
        "| OpenAI      | `provider openai`      | gpt-4o                |",
    ]
    if openrouter_row not in text and "| OpenRouter" not in text:
        inserted = False
        for row in candidates:
            if row in text:
                text = text.replace(row, row + "\n" + openrouter_row, 1)
                inserted = True
                break
        if not inserted:
            raise SystemExit("en: OpenAI provider row not found")

    if "### OpenRouter security and routing notes" not in text:
        m = re.search(r"\| Custom.*manual.*\|\n\n---", text, re.I)
        if not m:
            m = re.search(r"\| 自定义.*\|\n\n---", text)  # unlikely in EN
        if not m:
            # English custom row variants
            m = re.search(r"\| Custom\s+\| `provider custom`\s+\| .*\|\n\n---", text)
        if not m:
            raise SystemExit("en: could not find provider table end")
        text = text[: m.end() - 3] + OPENROUTER_SECTION_EN + "---" + text[m.end() :]

    text = text.replace(
        "| **Config** | `config/schema.py` + `settings.py` | Pydantic + YAML + 13 Provider presets |",
        "| **Config** | `config/schema.py` + `settings.py` | Pydantic + YAML + 14 Provider presets |",
        1,
    )
    text = text.replace(
        "| **Configuration** | `config/schema.py` + `settings.py` | Pydantic + YAML + 13 Provider presets |",
        "| **Configuration** | `config/schema.py` + `settings.py` | Pydantic + YAML + 14 Provider presets |",
        1,
    )
    # looser config module line
    text = re.sub(
        r"(\| \*\*Config(?:uration)?\*\* \| `config/schema\.py` \+ `settings\.py` \|[^|]*?)13( Provider)",
        r"\g<1>14\2",
        text,
        count=1,
    )
    text = text.replace(
        "| `llm.provider` | openai | LLM provider |",
        "| `llm.provider` | openai | LLM provider (14 built-in + custom) |",
        1,
    )
    text = re.sub(
        r"(\| `llm\.provider` \| openai \| LLM provider)[^\n|]*\|",
        r"\1 (14 built-in + custom) |",
        text,
        count=1,
    )
    return text


def main() -> None:
    zh = patch_zh(dump("README.md"))
    en = patch_en(dump("README_EN.md"))
    for marker in ("<<<<<<<", "=======", ">>>>>>>"):
        if marker in zh or marker in en:
            raise SystemExit("conflict markers remain")
    (ROOT / "README.md").write_text(zh, encoding="utf-8", newline="\n")
    (ROOT / "README_EN.md").write_text(en, encoding="utf-8", newline="\n")
    print("README.md / README_EN.md patched")
    # sanity: OpenRouter mentions
    for name, text in (("zh", zh), ("en", en)):
        if "openrouter" not in text.lower():
            raise SystemExit(f"{name} missing openrouter")
        print(name, "openrouter count", text.lower().count("openrouter"))


if __name__ == "__main__":
    main()
