from vulnclaw.agent.context import ContextManager
from vulnclaw.agent.finding_parser import FindingParser
from vulnclaw.agent.runtime_state import RuntimeState


def test_finding_parser_localizes_display_text_but_preserves_vulnerability_type(
    i18n_language,
):
    context = ContextManager()
    parser = FindingParser(context, RuntimeState())

    i18n_language("en")
    parser.parse(
        "发现 SQL注入 漏洞，访问 https://example.com/search?id=1 后返回 SQL 错误，差异: 155"
    )

    finding = context.state.findings[0]
    assert finding.title == "[Auto] SQL Injection"
    assert finding.description == "Automatically detected: SQL注入"
    assert finding.vuln_type == "SQL注入"


def test_finding_parser_preserves_chinese_display_text(i18n_language):
    context = ContextManager()
    parser = FindingParser(context, RuntimeState())

    i18n_language("zh")
    parser.parse("发现 SQL注入 漏洞，返回 SQL 错误，差异: 155")

    finding = context.state.findings[0]
    assert finding.title == "[自动] SQL注入"
    assert finding.description.startswith("自动检测：")
    assert finding.vuln_type == "SQL注入"
