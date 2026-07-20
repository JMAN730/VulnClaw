from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from vulnclaw.config.domain_models import EvidenceRef
from vulnclaw.config.schema import VulnClawConfig
from vulnclaw.run_context import create_run_context
from vulnclaw.targets import parse_target


class FakeDockerClient:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.calls: list[tuple] = []
        self.created_name = ""
        self.exec_result = SimpleNamespace(
            returncode=0,
            stdout="sandbox output\n",
            stderr="",
            timed_out=False,
        )

    def require_available(self) -> None:
        self.calls.append(("available",))
        if not self.available:
            from vulnclaw.sandbox import DockerUnavailableError

            raise DockerUnavailableError("Docker is unavailable")

    def ensure_image(self, image: str) -> None:
        self.calls.append(("image", image))

    def create_container(self, **kwargs) -> str:
        self.calls.append(("create", kwargs))
        self.created_name = str(kwargs["name"])
        return "container-id"

    def copy_workspace(self, container: str, workspace: Path) -> None:
        self.calls.append(("copy", container, workspace))

    def execute(self, container: str, argv: list[str], **kwargs):
        self.calls.append(("exec", container, argv, kwargs))
        return self.exec_result

    def copy_artifacts(self, container: str, source: str, destination: Path) -> None:
        self.calls.append(("artifacts", container, source, destination))
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "proof.txt").write_text("proof", encoding="utf-8")

    def remove_container(self, container: str) -> None:
        self.calls.append(("remove", container))


def _run_context(tmp_path: Path, *, ingress_mode: str = "copy"):
    workspace = tmp_path / "target"
    workspace.mkdir()
    (workspace / "host.txt").write_text("unchanged", encoding="utf-8")
    target = parse_target(str(workspace), ingress_mode=ingress_mode)
    context = create_run_context(
        command="run",
        targets=[target],
        runs_dir=tmp_path / "runs",
        run_name=f"sandbox-{ingress_mode}",
    )
    return context, target, workspace


def test_docker_boundary_copy_lifecycle_and_evidence_bundle(tmp_path):
    from vulnclaw.sandbox import DockerBoundary

    context, target, workspace = _run_context(tmp_path)
    client = FakeDockerClient()
    boundary = DockerBoundary(
        run_context=context,
        target=target,
        image="vulnclaw/sandbox:test",
        network="none",
        client=client,
    )

    result = boundary.run(["python3", "-c", "print('ok')"], timeout=5, label="python_execute")
    boundary.close()

    assert result.stdout == "sandbox output\n"
    assert result.bundle_ref == EvidenceRef(
        kind="sandbox_output", path="sandbox/python-execute-0001"
    )
    assert workspace.joinpath("host.txt").read_text(encoding="utf-8") == "unchanged"
    assert any(call[0] == "copy" and call[2] == workspace for call in client.calls)
    assert any(call[0] == "remove" for call in client.calls)

    bundle = context.run_dir / "evidence" / result.bundle_ref.path
    meta = json.loads((bundle / "meta.json").read_text(encoding="utf-8"))
    assert meta["argv"] == ["python3", "-c", "print('ok')"]
    assert meta["exit_code"] == 0
    assert meta["ingress_mode"] == "copy"
    assert (bundle / "stdout.txt").read_text(encoding="utf-8") == "sandbox output\n"
    assert (bundle / "stderr.txt").read_text(encoding="utf-8") == ""
    assert (bundle / "artifacts" / "proof.txt").read_text(encoding="utf-8") == "proof"


def test_docker_boundary_mount_is_read_only(tmp_path):
    from vulnclaw.sandbox import DockerBoundary

    context, target, workspace = _run_context(tmp_path, ingress_mode="mount")
    client = FakeDockerClient()
    boundary = DockerBoundary(
        run_context=context,
        target=target,
        image="vulnclaw/sandbox:test",
        network="none",
        client=client,
    )

    boundary.run(["sh", "-c", "touch /workspace/denied"], timeout=5, label="mount_check")
    boundary.close()

    create = next(call[1] for call in client.calls if call[0] == "create")
    assert create["workspace"] == workspace
    assert create["ingress_mode"] == "mount"
    assert not any(call[0] == "copy" for call in client.calls)
    assert not (workspace / "denied").exists()


def test_docker_absent_fails_without_executing_or_falling_back(tmp_path):
    from vulnclaw.sandbox import DockerBoundary, DockerUnavailableError

    context, target, _workspace = _run_context(tmp_path)
    client = FakeDockerClient(available=False)
    boundary = DockerBoundary(
        run_context=context,
        target=target,
        image="vulnclaw/sandbox:test",
        network="none",
        client=client,
    )

    with pytest.raises(DockerUnavailableError, match="Docker"):
        boundary.run(["python3", "-c", "print('host must not run')"], timeout=5, label="python")

    assert [call[0] for call in client.calls] == ["available"]


def test_local_boundary_is_explicit_and_creates_no_evidence(tmp_path):
    from vulnclaw.sandbox import LocalBoundary

    boundary = LocalBoundary()
    result = boundary.run(
        [boundary.python_executable, "-c", "print('local ok')"],
        timeout=5,
        label="trusted_local",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "local ok"
    assert result.bundle_ref is None


def test_sandbox_http_transport_executes_request_through_boundary():
    from vulnclaw.sandbox import ExecResult
    from vulnclaw.sandbox.http import BoundaryHTTPTransport

    class FakeBoundary:
        mode = "docker"
        python_executable = "/usr/bin/python3"

        def __init__(self) -> None:
            self.calls = []

        def run(self, argv, **kwargs):
            self.calls.append((argv, kwargs))
            payload = {
                "status": 201,
                "headers": [["content-type", "text/plain"]],
                "body": "Y3JlYXRlZA==",
                "reason": "Created",
                "url": "https://example.com/resource",
            }
            return ExecResult(0, json.dumps(payload), "", None)

        def close(self) -> None:
            pass

    boundary = FakeBoundary()
    transport = BoundaryHTTPTransport(boundary, verify=True)

    with httpx.Client(transport=transport) as client:
        response = client.post("https://example.com/resource", content=b"input")

    assert response.status_code == 201
    assert response.text == "created"
    assert boundary.calls[0][1]["label"] == "http_post"
    request_payload = json.loads(boundary.calls[0][1]["stdin_text"])
    assert request_payload["method"] == "POST"
    assert request_payload["body"] == "aW5wdXQ="


def test_sandbox_is_default_and_trusted_local_is_explicit(tmp_path):
    from vulnclaw.sandbox import DockerBoundary, LocalBoundary
    from vulnclaw.sandbox.runtime import create_execution_boundary

    context, target, _workspace = _run_context(tmp_path)
    config = VulnClawConfig()

    default_boundary = create_execution_boundary(
        config=config, run_context=context, target=target, trusted_local=False
    )
    local_boundary = create_execution_boundary(
        config=config, run_context=context, target=target, trusted_local=True
    )

    assert config.safety.sandbox_mode == "docker"
    assert isinstance(default_boundary, DockerBoundary)
    assert isinstance(local_boundary, LocalBoundary)


@pytest.mark.asyncio
async def test_orchestrator_closes_boundary_when_runner_fails(tmp_path, monkeypatch):
    import vulnclaw.orchestrator as orchestrator
    from vulnclaw.agent.core import AgentCore

    class FakeBoundary:
        mode = "docker"
        python_executable = "/usr/bin/python3"

        def __init__(self) -> None:
            self.closed = False

        def run(self, argv, **kwargs):  # pragma: no cover - runner never invokes it
            raise AssertionError("unexpected execution")

        def close(self) -> None:
            self.closed = True

    boundary = FakeBoundary()
    monkeypatch.setattr(
        orchestrator,
        "create_execution_boundary",
        lambda **kwargs: boundary,
        raising=False,
    )
    agent = AgentCore(VulnClawConfig())

    async def fail(_agent):
        raise RuntimeError("runner failed")

    with pytest.raises(RuntimeError, match="runner failed"):
        await orchestrator.run_agent_task(
            agent=agent,
            command="run",
            target="https://example.com",
            resume=False,
            runs_dir=str(tmp_path / "runs"),
            runner=fail,
        )

    assert boundary.closed is True
    assert agent.execution_boundary is None
