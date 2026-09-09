"""Tests for published project metadata consistency."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_REPOSITORY = "https://github.com/Unclecheng-li/VulnClaw"


def test_user_facing_repository_links_point_to_the_maintained_upstream():
    paths = [
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "README_EN.md",
        PROJECT_ROOT / "vulnclaw" / "web" / "static" / "index.html",
    ]

    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert "Netw0rkNoob/VulnClaw" not in content
        assert UPSTREAM_REPOSITORY in content
