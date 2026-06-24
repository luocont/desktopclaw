"""Tests for workspace-sandbox hardening across filesystem + shell tools."""

import pytest

from desktopclaw.agent.tools.filesystem import ReadFileTool, WriteFileTool
from desktopclaw.agent.tools.sandbox import is_within_allowed, normalize_allowed_dirs
from desktopclaw.agent.tools.shell import ExecTool

# --- sandbox helpers ---


def test_normalize_allowed_dirs_dedupes_and_resolves(tmp_path) -> None:
    extra = tmp_path / "extra"
    extra.mkdir()
    dirs = normalize_allowed_dirs(tmp_path, [str(extra), str(tmp_path)])
    assert tmp_path.resolve() in dirs
    assert extra.resolve() in dirs
    # tmp_path passed twice (workspace + allowed_paths) → deduped
    assert dirs.count(tmp_path.resolve()) == 1


def test_is_within_allowed_empty_means_unrestricted(tmp_path) -> None:
    assert is_within_allowed(tmp_path / "anything", []) is True


def test_is_within_allowed_checks_membership(tmp_path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    assert is_within_allowed(root / "a" / "b.txt", [root]) is True
    assert is_within_allowed(tmp_path / "outside.txt", [root]) is False


# --- filesystem tools ---


@pytest.mark.asyncio
async def test_write_blocked_outside_workspace(tmp_path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "outside.txt"
    tool = WriteFileTool(workspace=ws, allowed_dir=ws)
    result = await tool.execute(path=str(outside), content="x")
    assert "outside allowed directories" in result
    assert not outside.exists()


@pytest.mark.asyncio
async def test_write_allowed_via_allowed_paths(tmp_path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    extra = tmp_path / "extra"
    extra.mkdir()
    target = extra / "note.txt"
    tool = WriteFileTool(workspace=ws, allowed_dir=ws, allowed_paths=[str(extra)])
    result = await tool.execute(path=str(target), content="hello")
    assert "Successfully wrote" in result
    assert target.read_text() == "hello"


@pytest.mark.asyncio
async def test_read_unrestricted_when_no_allowed_dir(tmp_path) -> None:
    outside = tmp_path / "free.txt"
    outside.write_text("data")
    # allowed_dir=None → legacy unrestricted behaviour
    tool = ReadFileTool(workspace=tmp_path / "ws")
    result = await tool.execute(path=str(outside))
    assert "data" in result


# --- exec working_dir validation ---


@pytest.mark.asyncio
async def test_exec_blocks_working_dir_outside_workspace(tmp_path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    tool = ExecTool(working_dir=str(ws), restrict_to_workspace=True)
    result = await tool.execute(command="echo hi", working_dir=str(outside))
    assert "working_dir outside allowed directories" in result


@pytest.mark.asyncio
async def test_exec_allows_working_dir_in_allowed_paths(tmp_path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    extra = tmp_path / "extra"
    extra.mkdir()
    tool = ExecTool(
        working_dir=str(ws), restrict_to_workspace=True, allowed_paths=[str(extra)]
    )
    # working_dir inside whitelisted extra dir should pass the guard
    result = await tool.execute(command="echo hi", working_dir=str(extra))
    assert "working_dir outside" not in result


def test_exec_guard_allows_absolute_path_in_whitelist(tmp_path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    extra = tmp_path / "extra"
    extra.mkdir()
    tool = ExecTool(
        working_dir=str(ws), restrict_to_workspace=True, allowed_paths=[str(extra)]
    )
    # absolute path pointing into the whitelisted dir is allowed
    assert tool._guard_command(f"cat {extra / 'f.txt'}", str(ws)) is None


def test_exec_guard_blocks_absolute_path_outside_all_roots(tmp_path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    tool = ExecTool(working_dir=str(ws), restrict_to_workspace=True)
    other = tmp_path / "secrets"
    error = tool._guard_command(f"cat {other / 'creds.txt'}", str(ws))
    assert error == "Error: Command blocked by safety guard (path outside allowed directories)"
