"""Regression tests for normalized, persisted targets."""

import pytest

from vulnclaw.targets import parse_target


def test_parse_target_preserves_ipv6_url_authority_syntax():
    target = parse_target("https://[2001:db8::1]:8443/path//to/")

    assert target.canonical == "https://[2001:db8::1]:8443/path/to"


def test_parse_target_rejects_malformed_url_port_cleanly():
    with pytest.raises(ValueError, match="invalid port"):
        parse_target("https://example.com:not-a-port")


def test_explicit_url_target_requires_scheme_and_host():
    with pytest.raises(ValueError, match="http\\(s\\) scheme and hostname"):
        parse_target("example.com", target_type="web_url")
