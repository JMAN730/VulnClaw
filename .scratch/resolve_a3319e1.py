from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# schema.py
p = ROOT / "vulnclaw" / "config" / "schema.py"
text = p.read_text(encoding="utf-8")
old = """<<<<<<< HEAD
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
=======
from pydantic import BaseModel, ConfigDict, Field, field_validator

LLM_MODEL_ID_MAX_LENGTH = 160


def normalize_llm_model_id(value: str) -> str:
    \"\"\"Normalize an opaque Model ID and reject unsafe/invalid values.\"\"\"
    normalized = value.strip()
    if not normalized:
        raise ValueError(\"model must not be blank\")
    if len(normalized) > LLM_MODEL_ID_MAX_LENGTH:
        raise ValueError(
            f\"model must not exceed {LLM_MODEL_ID_MAX_LENGTH} characters\"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError(\"model must not include ASCII control characters\")
    return normalized
>>>>>>> a3319e1 (fix: harden openrouter configuration edges)
"""
new = """from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

LLM_MODEL_ID_MAX_LENGTH = 160


def normalize_llm_model_id(value: str) -> str:
    \"\"\"Normalize an opaque Model ID and reject unsafe/invalid values.\"\"\"
    normalized = value.strip()
    if not normalized:
        raise ValueError(\"model must not be blank\")
    if len(normalized) > LLM_MODEL_ID_MAX_LENGTH:
        raise ValueError(
            f\"model must not exceed {LLM_MODEL_ID_MAX_LENGTH} characters\"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError(\"model must not include ASCII control characters\")
    return normalized
"""
if old not in text:
    raise SystemExit("schema conflict not found")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("schema fixed")

# zh.json
zhp = ROOT / "vulnclaw" / "i18n" / "zh.json"
zh = zhp.read_text(encoding="utf-8")
pat = re.compile(
    r"<<<<<<< HEAD\n"
    r'  "tui\.openrouter_warning": "[^"]*"\n'
    r"=======\n"
    r".*?"
    r">>>>>>> a3319e1 \(fix: harden openrouter configuration edges\)\n?",
    re.S,
)
rep = (
    '  "tui.model_invalid": "Model ID 去除首尾空白后必须为 1–160 个字符，且不能包含 ASCII 控制字符。",\n'
    '  "tui.openrouter_static_auth": "OpenRouter 使用静态推理密钥；OAuth 与 ChatGPT 自动代理已禁用。",\n'
    '  "tui.openrouter_warning": "OpenRouter 可能在多个上游提供商之间路由请求。发送敏感的授权目标数据前，请核验账户隐私与 ZDR 偏好。"\n'
)
zh2, n = pat.subn(rep, zh, count=1)
if n != 1:
    raise SystemExit(f"zh replace={n}")
json.loads(zh2)
zhp.write_text(zh2, encoding="utf-8")
print("zh fixed")

# update catalog prefixes
tp = ROOT / "tests" / "test_provider_models.py"
t = tp.read_text(encoding="utf-8")
old_p = 'prefixes = ("tui.model_discovery_", "tui.openrouter_warning")'
new_p = 'prefixes = ("tui.model_discovery_", "tui.openrouter_")'
if old_p not in t:
    raise SystemExit("prefix line not found")
tp.write_text(t.replace(old_p, new_p, 1), encoding="utf-8")
print("catalog prefix updated")
