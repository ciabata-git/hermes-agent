"""Shared helpers for classifying tool result payloads."""

from __future__ import annotations

import json
from typing import Any


FILE_MUTATING_TOOL_NAMES = frozenset({"write_file", "patch"})
TOOL_ERROR_SUFFIX_MAX_LEN = 48


# Tools whose interrupted/dangling execution is safe to discard because they
# cannot mutate either external state or Hermes session state. Unknown/plugin/
# MCP tools stay effect-capable by default.
NO_EFFECT_TOOL_NAMES = frozenset({
    "read_file", "search_files", "session_search", "skill_view", "skills_list",
    "web_extract", "web_search", "vision_analyze", "browser_snapshot",
    "browser_get_images", "browser_console", "read_terminal",
})


def tool_may_have_side_effect(tool_name: str) -> bool:
    return tool_name not in NO_EFFECT_TOOL_NAMES


def trim_tool_error(msg: str) -> str:
    """Shrink a structured tool error for a compact status suffix."""
    msg = msg.strip()
    if "File not found:" in msg:
        _, _, tail = msg.partition("File not found:")
        tail = tail.strip()
        if "/" in tail:
            msg = f"File not found: {tail.rsplit('/', 1)[-1]}"
    if len(msg) > TOOL_ERROR_SUFFIX_MAX_LEN:
        msg = msg[: TOOL_ERROR_SUFFIX_MAX_LEN - 3] + "..."
    return msg


def file_mutation_result_landed(tool_name: str, result: Any) -> bool:
    """Return True when a file mutation result proves the write landed."""
    if tool_name not in FILE_MUTATING_TOOL_NAMES or not isinstance(result, str):
        return False
    try:
        data = json.loads(result.strip())
    except Exception:
        return False
    if not isinstance(data, dict) or data.get("error"):
        return False
    if tool_name == "write_file":
        return "bytes_written" in data
    if tool_name == "patch":
        return data.get("success") is True
    return False


def classify_web_extract_failure(data: Any) -> tuple[bool, str] | None:
    """Classify a canonical web_extract envelope, or return None if unknown.

    A result is useful when at least one item carries extracted content, even
    if another URL failed. Blank items do not count as partial success. Unknown
    item shapes fall back to the caller's generic failure heuristic instead of
    suppressing signals such as ``{"failed": true}``.
    """
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return None

    outer_detail = data.get("error") or data.get("message")
    if outer_detail:
        return True, str(outer_detail)

    failed_signal = data.get("failed")
    if data.get("success") is False or failed_signal:
        if failed_signal and failed_signal is not True:
            return True, str(failed_signal)
        return True, "error"

    results = data["results"]
    if not results:
        return True, "Content was inaccessible or not found"
    if any(
        not isinstance(item, dict)
        or "content" not in item
        or "error" not in item
        or not isinstance(item.get("content"), str)
        for item in results
    ):
        return None

    if any(item["content"].strip() for item in results):
        return False, ""

    errors = [item.get("error") for item in results if item.get("error")]
    if errors:
        return True, str(errors[0])
    return True, "Content was inaccessible or not found"
