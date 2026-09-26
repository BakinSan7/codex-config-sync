#!/usr/bin/env python3
"""Read-only context health check for a local Codex session."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TOKEN_EVENT_MARKER = b'"type":"event_msg","payload":{"type":"token_count"'
COMPACTION_EVENT_MARKER = (
    b'"type":"event_msg","payload":{"type":"context_compacted"'
)


@dataclass(frozen=True)
class ContextReport:
    session: str
    context_input_tokens: int
    context_window_tokens: int
    occupancy_percent: float
    cached_input_tokens: int
    cached_share_percent: float
    new_input_tokens: int
    reuse_to_new_ratio: float | None
    output_tokens: int
    reasoning_output_tokens: int
    session_total_tokens: int
    compactions: int
    severity: str
    recommendation: str
    turn_requests: int | None = None
    recent_input_tokens: int = 0
    recent_cached_tokens: int = 0
    cost_review: bool = False


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def find_session(
    explicit_path: str | None = None,
    session_id: str | None = None,
    home: Path | None = None,
) -> Path:
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Session file not found: {path}")
        return path

    root = home or codex_home()
    selected_id = (
        session_id
        or os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("CODEX_THREAD_ID")
    )
    roots = [root / "sessions", root / "archived_sessions"]

    if selected_id:
        matches = [
            path
            for session_root in roots
            if session_root.is_dir()
            for path in session_root.rglob(f"*{selected_id}.jsonl")
        ]
        if matches:
            return max(matches, key=lambda path: path.stat().st_mtime)
        raise FileNotFoundError(f"No Codex session found for id {selected_id}")

    raise ValueError("Pass --session or --session-id: active task identity is unavailable")


def read_session(path: Path) -> tuple[dict[str, Any], int]:
    latest_info: dict[str, Any] | None = None
    compactions: set[str] = set()
    legacy_compactions: set[str] = set()
    responses: dict[str, dict[str, Any]] = {}

    with path.open("rb") as stream:
        for raw_line in stream:
            # Large compacted payloads contain replayed events: only inspect
            # their outer type, never parse/count their embedded transcript.
            head = raw_line[:512]
            match = re.search(rb'"type"\s*:\s*"([^"]+)"', head)
            kind = match.group(1) if match else b""
            if kind == b"compacted":
                stamp = re.search(rb'"timestamp"\s*:\s*"([^"]+)"', head)
                compactions.add(stamp.group(1).decode() if stamp else str(len(compactions)))
                continue
            if kind not in (b"event_msg", b"token_usage_record"):
                continue
            if kind == b"event_msg" and not re.search(
                rb'"type"\s*:\s*"(?:token_count|context_compacted)"', head
            ):
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                if not raw_line.endswith(b"\n"):
                    break  # A running process may still be writing this record.
                raise ValueError(f"Malformed telemetry in {path}: {exc}") from exc
            payload = event.get("payload") or {}
            if kind == b"token_usage_record" and payload.get("usage"):
                key = payload.get("response_id") or f"{event.get('timestamp')}:{event.get('ordinal')}"
                responses[key] = {**payload, "timestamp": event.get("timestamp", "")}
            elif payload.get("type") == "context_compacted":
                legacy_compactions.add(event.get("timestamp", ""))
            elif payload.get("type") == "token_count" and payload.get("info"):
                latest_info = {**payload["info"], "timestamp": event.get("timestamp", "")}

    if responses:
        ordered = sorted(responses.values(), key=lambda r: r["timestamp"])
        last = ordered[-1]
        turn_id = last.get("root_turn_id") or last.get("turn_id")
        turn = [r for r in ordered if (r.get("root_turn_id") or r.get("turn_id")) == turn_id]
        if not latest_info or last["timestamp"] >= latest_info.get("timestamp", ""):
            latest_info = {**(latest_info or {}), "last_token_usage": last["usage"],
                           "total_token_usage": last.get("thread_token_usage", {}),
                           "model_context_window": (latest_info or {}).get("model_context_window", 0)}
        latest_info["watchdog_turn_requests"] = len(turn)
        latest_info["watchdog_recent"] = [r["usage"] for r in turn[-10:]]

    if latest_info is None:
        raise ValueError(f"No token_count events found in {path}")
    return latest_info, len(compactions or legacy_compactions)


def classify(occupancy_percent: float, compactions: int) -> tuple[str, str]:
    if occupancy_percent >= 80.0:
        return (
            "handoff_now",
            "Continue to a safe checkpoint, then transfer the active objective with verified context and no added scope.",
        )
    if occupancy_percent >= 70.0:
        return (
            "handoff_before_large_task",
            "Finish the current bounded work, then prepare a scope-exact continuation before the next large objective.",
        )
    if occupancy_percent >= 55.0:
        return "note", "Continue; recheck after the next major stage."
    return "healthy", "Continue without notifying the user."


def build_report(path: Path, info: dict[str, Any], compactions: int) -> ContextReport:
    last = info["last_token_usage"]
    total = info["total_token_usage"]
    context_input = int(last["input_tokens"])
    context_window = int(info["model_context_window"])
    cached = int(last.get("cached_input_tokens", 0))
    new_input = max(0, context_input - cached)
    occupancy = (context_input / context_window * 100.0) if context_window else 0.0
    cached_share = (cached / context_input * 100.0) if context_input else 0.0
    reuse_ratio = (cached / new_input) if new_input else None
    severity, recommendation = classify(occupancy, compactions)
    recent = info.get("watchdog_recent", [])
    recent_input = sum(r.get("input_tokens", 0) for r in recent)
    recent_cached = sum(r.get("cached_input_tokens", 0) for r in recent)
    cost_review = (len(recent) == 10 and recent_cached >= 2720000 and
                   all(r.get("input_tokens", 0) > 272000 for r in recent) and
                   recent_cached / max(1, recent_input) >= .95)
    if cost_review:
        severity = "handoff_now"
        recommendation = "Checkpoint and review expensive context reuse; hand off removable context on the same model."
    elif not context_window:
        severity = "note"
        recommendation = "Context-window metadata is unavailable; do not interpret zero occupancy as healthy."

    return ContextReport(
        session=str(path),
        context_input_tokens=context_input,
        context_window_tokens=context_window,
        occupancy_percent=round(occupancy, 1),
        cached_input_tokens=cached,
        cached_share_percent=round(cached_share, 1),
        new_input_tokens=new_input,
        reuse_to_new_ratio=round(reuse_ratio, 1) if reuse_ratio is not None else None,
        output_tokens=int(last.get("output_tokens", 0)),
        reasoning_output_tokens=int(last.get("reasoning_output_tokens", 0)),
        session_total_tokens=int(total.get("total_tokens", 0)),
        compactions=compactions,
        severity=severity,
        recommendation=recommendation,
        turn_requests=info.get("watchdog_turn_requests"),
        recent_input_tokens=recent_input,
        recent_cached_tokens=recent_cached,
        cost_review=cost_review,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="Explicit rollout JSONL path")
    parser.add_argument("--session-id", help="Codex session/thread id")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        session = find_session(args.session, args.session_id)
        info, compactions = read_session(session)
        report = build_report(session, info, compactions)
    except (FileNotFoundError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"context-watchdog: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        ratio = (
            "n/a"
            if report.reuse_to_new_ratio is None
            else f"{report.reuse_to_new_ratio:.1f}x"
        )
        print(
            f"severity={report.severity}\n"
            f"context={report.context_input_tokens}/{report.context_window_tokens} "
            f"({report.occupancy_percent:.1f}%)\n"
            f"cached={report.cached_input_tokens} "
            f"({report.cached_share_percent:.1f}%)\n"
            f"new_input={report.new_input_tokens}\n"
            f"reuse_to_new={ratio}\n"
            f"compactions={report.compactions}\n"
            f"recommendation={report.recommendation}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
