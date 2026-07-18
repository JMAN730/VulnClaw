"""VulnClaw system prompt builder — language-aware dispatch.

The actual prompt text lives in per-language modules (``prompts_zh`` /
``prompts_en``). This module selects the active language via the i18n
translator and assembles the final system prompt from the chosen bundle.
"""

from __future__ import annotations

from typing import Optional

from vulnclaw.agent import prompts_en, prompts_zh
from vulnclaw.i18n import current_lang


def _bundle(lang: Optional[str] = None):
    """Return the prompt-text module for the active (or given) language."""
    lang = lang or current_lang()
    return prompts_en if lang == "en" else prompts_zh


def build_system_prompt(
    target: Optional[str] = None,
    phase: Optional[str] = None,
    skill_context: Optional[str] = None,
    mcp_tools: Optional[list[dict]] = None,
    enable_personnel_dim: bool = True,
    lang: Optional[str] = None,
) -> str:
    """Dynamically assemble the full system prompt in the active language.

    Args:
        target: Current target identifier (IP/URL).
        phase: Current pentest phase name. Looked up against the (Chinese)
            phase keys shared by every language bundle.
        skill_context: Additional context from a loaded Skill.
        mcp_tools: List of available MCP tool schemas.
        enable_personnel_dim: Kept for backward compatibility; the recon
            dimension toggle is applied by ``get_recon_instruction``.
        lang: Explicit language override ('zh'/'en'); defaults to the active
            UI language.

    Returns:
        Assembled system prompt string.
    """
    b = _bundle(lang)
    parts = [b.BASE_IDENTITY, b.CORE_CONTRACT]

    if target:
        parts.append(b.LABELS["target_section"].format(target=target))

    if phase and phase in b.PHASE_DESCRIPTIONS:
        parts.append(b.PHASE_DESCRIPTIONS[phase])

    if skill_context:
        parts.append(b.LABELS["skill_section"].format(context=skill_context))

    # WAF bypass knowledge (always included)
    parts.append(b.WAF_BYPASS_KNOWLEDGE)

    if mcp_tools:
        tools_desc = _format_mcp_tools(mcp_tools)
        parts.append(b.LABELS["mcp_section"].format(tools=tools_desc))

    return "\n".join(parts)


def get_auto_pentest_instruction(lang: Optional[str] = None) -> str:
    """Return the auto-pentest loop instruction in the active language."""
    return _bundle(lang).AUTO_PENTEST_INSTRUCTION


def get_recon_instruction(
    enable_personnel_dim: bool = True, lang: Optional[str] = None
) -> str:
    """Return the recon instruction, optionally with the personnel dimension
    disabled, in the active language."""
    b = _bundle(lang)
    return b.RECON_INSTRUCTION if enable_personnel_dim else b.RECON_INSTRUCTION_NO_PERSONNEL


def _format_mcp_tools(tools: list[dict]) -> str:
    """Format MCP tool schemas into a readable description for the LLM."""
    lines = []
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        lines.append(f"- **{name}**: {desc}")

        params = tool.get("inputSchema", {}).get("properties", {})
        if params:
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "any")
                param_desc = param_info.get("description", "")
                lines.append(f"  - `{param_name}` ({param_type}): {param_desc}")

    return "\n".join(lines)
