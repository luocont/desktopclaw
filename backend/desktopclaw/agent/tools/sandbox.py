"""Shared workspace-sandbox path helpers.

Centralizes the logic that decides whether a filesystem path is allowed when
``restrict_to_workspace`` is enabled. The workspace plus any explicitly
whitelisted ``allowed_paths`` form the set of permitted root directories.

When the allowed-dir set is empty the sandbox is *disabled* (unrestricted
access), preserving the previous behaviour of ``allowed_dir=None``.
"""

from __future__ import annotations

from pathlib import Path


def normalize_allowed_dirs(
    workspace: Path | str | None,
    allowed_paths: list[str] | None = None,
) -> list[Path]:
    """Resolve the workspace + extra whitelist into a list of absolute roots.

    Invalid / unresolvable entries are skipped rather than raising, so a bad
    config line never crashes the agent at tool-call time.
    """
    dirs: list[Path] = []
    if workspace:
        try:
            dirs.append(Path(workspace).expanduser().resolve())
        except Exception:
            pass
    for raw in allowed_paths or []:
        if not raw:
            continue
        try:
            dirs.append(Path(raw).expanduser().resolve())
        except Exception:
            continue
    # De-duplicate while keeping order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def is_within_allowed(resolved: Path, allowed_dirs: list[Path]) -> bool:
    """Return True if ``resolved`` lives inside any allowed root.

    An empty ``allowed_dirs`` means the sandbox is disabled → everything is
    allowed.
    """
    if not allowed_dirs:
        return True
    for root in allowed_dirs:
        if resolved == root:
            return True
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False
