"""VulnClaw basic integration tests: verify imports and version."""

import pytest


def test_import_vulnclaw():
    """Test that the main package can be imported."""
    from pathlib import Path

    import vulnclaw

    # Read version from pyproject.toml to avoid hardcoding (tomllib needs
    # Python 3.11+, but this project supports 3.10, so parse the line directly)
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    version_line = next(
        line
        for line in pyproject_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("version = ")
    )
    expected_version = version_line.split('"')[1]

    assert vulnclaw.__version__ == expected_version


def test_all_submodules_importable():
    """Test that all major submodules can be imported."""


def test_no_import_errors():
    """Verify no module raises on import."""
    import importlib
    import importlib.util

    modules = [
        "vulnclaw",
        "vulnclaw.config.schema",
        "vulnclaw.config.settings",
        "vulnclaw.agent.context",
        "vulnclaw.agent.memory",
        "vulnclaw.agent.prompts",
        "vulnclaw.agent.core",
        "vulnclaw.mcp.registry",
        "vulnclaw.mcp.router",
        "vulnclaw.mcp.lifecycle",
        "vulnclaw.skills.loader",
        "vulnclaw.skills.dispatcher",
        "vulnclaw.kb.store",
        "vulnclaw.kb.retriever",
        "vulnclaw.kb.updater",
        "vulnclaw.report.generator",
        "vulnclaw.report.poc_builder",
    ]
    if importlib.util.find_spec("typer") is not None:
        modules.append("vulnclaw.cli.main")

    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
        except ImportError as e:
            pytest.fail(f"Failed to import {mod_name}: {e}")
