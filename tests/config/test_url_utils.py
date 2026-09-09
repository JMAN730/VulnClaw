"""Tests for shared URL helper behavior."""

from vulnclaw.config import infer_port_from_url


def test_infer_port_from_url_handles_explicit_and_scheme_defaults():
    assert infer_port_from_url("https://example.com") == 443
    assert infer_port_from_url("http://example.com") == 80
    assert infer_port_from_url("https://example.com:8443/path") == 8443


def test_infer_port_from_url_rejects_malformed_ports_without_raising():
    assert infer_port_from_url("https://example.com:not-a-port") is None
    assert infer_port_from_url("https://example.com:65536") is None
