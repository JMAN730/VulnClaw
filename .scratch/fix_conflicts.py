from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- zh.json ---
zh_path = ROOT / "vulnclaw" / "i18n" / "zh.json"
text = zh_path.read_text(encoding="utf-8")
pattern = re.compile(
    r"<<<<<<< HEAD\n"
    r'  "tui\.no_models_available": "该提供商未返回可用模型"\n'
    r"=======\n"
    r".*?"
    r">>>>>>> 99eafa2 \(feat: validate openrouter model discovery\)\n?",
    re.S,
)
replacement = (
    '  "tui.no_models_available": "该提供商未返回可用模型",\n'
    '  "tui.model_discovery_missing_key": "请先保存推理 API 密钥，再获取模型列表。",\n'
    '  "tui.model_discovery_untrusted_url": "已保存的密钥不会发送到不受信任的 Base URL。",\n'
    '  "tui.model_discovery_authentication_failed": "提供商拒绝了已保存的推理密钥。",\n'
    '  "tui.model_discovery_timeout": "模型发现超时，请检查网络连接后重试。",\n'
    '  "tui.model_discovery_malformed_response": "提供商返回了无效的模型目录。",\n'
    '  "tui.model_discovery_response_too_large": "提供商的模型目录超过安全限制。",\n'
    '  "tui.model_discovery_empty_catalog": "未找到兼容模型，请手动输入模型 ID。",\n'
    '  "tui.model_discovery_redirect_blocked": "模型发现发生重定向；为保护已保存的密钥，请求已停止。",\n'
    '  "tui.model_discovery_upstream_error": "无法加载提供商模型目录。",\n'
    '  "tui.openrouter_warning": "OpenRouter 可能在多个上游提供商之间路由请求。发送敏感的授权目标数据前，请核验账户隐私与 ZDR 偏好。"\n'
)
new_text, n = pattern.subn(replacement, text, count=1)
if n != 1:
    raise SystemExit(f"zh.json replace count={n}")
json.loads(new_text)
zh_path.write_text(new_text, encoding="utf-8")
print("zh.json fixed")

# --- settings.py sanity ---
settings = (ROOT / "vulnclaw" / "config" / "settings.py").read_text(encoding="utf-8")
if "<<<<<<<" in settings or "=======" in settings or ">>>>>>>" in settings:
    raise SystemExit("settings.py still has conflict markers")
if "import json" not in settings or "import logging" not in settings:
    raise SystemExit("settings.py missing required imports")
print("settings.py ok")

# --- append catalog test into test_provider_models.py ---
test_path = ROOT / "tests" / "test_provider_models.py"
test_text = test_path.read_text(encoding="utf-8")
marker = "test_provider_discovery_catalogs_have_matching_keys_and_placeholders"
if marker in test_text:
    print("catalog test already present")
else:
    append = '''

def test_provider_discovery_catalogs_have_matching_keys_and_placeholders():
    """OpenRouter/model-discovery i18n keys stay in sync across en/zh."""
    from pathlib import Path
    from string import Formatter

    def _catalog(lang: str) -> dict[str, str]:
        path = Path(__file__).resolve().parents[1] / "vulnclaw" / "i18n" / f"{lang}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _placeholders(value: str) -> set[str]:
        return {name for _, name, _, _ in Formatter().parse(value) if name}

    prefixes = ("tui.model_discovery_", "tui.openrouter_warning")
    english = {
        key: value for key, value in _catalog("en").items() if key.startswith(prefixes)
    }
    chinese = {
        key: value for key, value in _catalog("zh").items() if key.startswith(prefixes)
    }

    assert english.keys() == chinese.keys()
    assert {
        key: (_placeholders(english[key]), _placeholders(chinese[key]))
        for key in english
        if _placeholders(english[key]) != _placeholders(chinese[key])
    } == {}
'''
    # Ensure json import exists at module level or use local import above (local used)
    if "import json" not in test_text.split("\n")[:40]:
        # add import json near top after future/annotations if present
        lines = test_text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines[:30]):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1
        lines.insert(insert_at, "import json\n")
        test_text = "".join(lines)
        if "import json\nimport json\n" in test_text:
            test_text = test_text.replace("import json\nimport json\n", "import json\n", 1)
    test_path.write_text(test_text.rstrip() + append + "\n", encoding="utf-8")
    print("catalog test appended to test_provider_models.py")
