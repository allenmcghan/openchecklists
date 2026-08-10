#!/usr/bin/env python3
"""Validate Open Checklist completion logs.

    python3 tools/validate_log.py build/*-log-*.json --checklist examples/foo.ocl.json

Schema first, then the policy checks that decide whether a log is worth anything
as a record. The interesting ones are not structural:

  * Does the log point at a checklist version that actually exists? A log whose
    content_hash does not match any known file records that the pilot ticked
    something, but not what.
  * Do the entries refer to items that exist in that checklist, and are any of
    them information items that were never tasks?
  * Is the implied working rate physically possible? A 40-item preflight
    completed in nine seconds is not a record of a preflight.

That last check is the reason this file exists. A log format makes pencil-whipping
*visible*, which cuts both ways: it is what makes an honest log worth keeping, and
it is what makes a dishonest one worse than none at all. Better that the tool says
so before anyone else reads it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("jsonschema is required: pip install jsonschema")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import Findings, content_hash  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LOG_SCHEMA = REPO / "schema" / "open-checklist-log-1.0.schema.json"

# Below this, a tick is faster than a person can plausibly have looked at the
# thing being checked. Not a hard physical constant; a deliberately generous
# floor chosen so that only genuinely implausible runs trip it.
MIN_SECONDS_PER_ITEM = 1.5

INFO_TYPES = {"note", "caution", "warning", "subtitle", "reference", "blank"}


def parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def check_against_checklist(log: dict, checklists: dict[str, dict], f: Findings) -> None:
    ref = log.get("checklist", {})
    want_hash = ref.get("content_hash")
    doc = checklists.get(want_hash)

    if not checklists:
        return
    if doc is None:
        f.warn(
            f"log references checklist content_hash {str(want_hash)[:12]}… which is not among the "
            "checklists provided; entry references cannot be verified"
        )
        return
    if ref.get("id") and ref["id"] != doc.get("id"):
        f.error(
            f"policy: log names checklist id {ref['id']!r} but that content hash belongs to "
            f"{doc.get('id')!r}"
        )

    sections = {s.get("id"): s for s in doc.get("sections", []) if s.get("id")}
    for i, e in enumerate(log.get("entries", [])):
        sid = e.get("section_id")
        sec = sections.get(sid)
        if sec is None:
            f.error(f"policy: entries/{i}: section {sid!r} does not exist in the checklist")
            continue
        items = sec.get("items", [])
        idx = e.get("item_index")
        if not isinstance(idx, int) or idx >= len(items):
            f.error(f"policy: entries/{i}: item_index {idx} out of range for section {sid!r}")
            continue
        item = items[idx]
        if e.get("item_id") and item.get("id") and e["item_id"] != item["id"]:
            f.error(
                f"policy: entries/{i}: item_id {e['item_id']!r} does not match the item at "
                f"index {idx} ({item.get('id')!r}); the checklist may have been edited"
            )
        itype = item.get("type")
        if itype in INFO_TYPES and e.get("state") == "completed":
            f.error(
                f"policy: entries/{i}: item is type={itype}, which is not a task; "
                "an information item can be acknowledged but never completed"
            )


def check_timing(log: dict, f: Findings) -> None:
    entries = log.get("entries", [])
    stamped = [(i, parse_ts(e["at"])) for i, e in enumerate(entries) if e.get("at")]
    stamped = [(i, t) for i, t in stamped if t]
    mode = log.get("recording", {}).get("mode")

    if mode == "live":
        missing = [i for i, e in enumerate(entries) if not e.get("at")]
        if missing:
            f.error(
                f"policy: recording.mode=live but {len(missing)} entry/entries have no timestamp "
                f"(first: entries/{missing[0]})"
            )

    now = datetime.now(timezone.utc)
    for i, t in stamped:
        if t > now:
            f.error(f"policy: entries/{i}: timestamp {t.isoformat()} is in the future")

    started = parse_ts(log.get("session", {}).get("started", ""))
    finished = parse_ts(log.get("session", {}).get("finished", ""))
    if started and finished and finished < started:
        f.error("policy: session.finished is before session.started")
    for i, t in stamped:
        if started and t < started:
            f.error(f"policy: entries/{i}: timestamp precedes session.started")
        if finished and t > finished:
            f.error(f"policy: entries/{i}: timestamp follows session.finished")

    # The pencil-whipping check.
    if mode == "live" and len(stamped) >= 5:
        span = (max(t for _, t in stamped) - min(t for _, t in stamped)).total_seconds()
        rate = span / (len(stamped) - 1) if len(stamped) > 1 else 0
        if rate < MIN_SECONDS_PER_ITEM:
            f.warn(
                f"implied working rate is {rate:.2f}s per item across {len(stamped)} items "
                f"({span:.1f}s total). That is faster than these checks can plausibly have been "
                "performed. Recorded as-is, but this log does not evidence a completed inspection."
            )


def check_integrity(log: dict, f: Findings) -> None:
    rec = log.get("recording", {})
    if rec.get("edited_after_completion"):
        f.warn("recording.edited_after_completion is set: entries changed after the session ended")
    if rec.get("mode") == "retrospective" and log.get("attestation"):
        f.warn(
            "a retrospective log carries an attestation; make sure the statement makes clear the "
            "entries were reconstructed rather than recorded at the time"
        )
    if rec.get("clock_source") == "device_clock":
        f.warn(
            "timestamps come from a user-settable device clock, so they are not a trusted time "
            "source; fine for personal records, weak as evidence"
        )

    entries = log.get("entries", [])
    seen: set[tuple] = set()
    for i, e in enumerate(entries):
        key = (e.get("section_id"), e.get("item_index"))
        if key in seen:
            f.error(f"policy: entries/{i}: duplicate entry for {key[0]!r} item {key[1]}")
        seen.add(key)

    outcome = log.get("session", {}).get("outcome")
    if outcome == "completed" and any(
        e.get("state") in ("skipped", "failed") for e in entries
    ):
        f.error(
            "policy: session.outcome=completed but entries include skipped or failed items; "
            "use completed_with_discrepancies or abandoned"
        )


def validate_log(path: Path, schema: dict, checklists: dict[str, dict]) -> Findings:
    f = Findings(path)
    try:
        log = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        f.error(f"invalid JSON: {exc}")
        return f

    for err in sorted(Draft202012Validator(schema).iter_errors(log), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
        f.error(f"schema: {loc}: {err.message}")
    if f.errors:
        return f

    check_against_checklist(log, checklists, f)
    check_timing(log, f)
    check_integrity(log, f)
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument(
        "--checklist",
        type=Path,
        action="append",
        default=[],
        help="checklist file(s) the logs refer to; enables entry-level verification",
    )
    ap.add_argument("--schema", type=Path, default=LOG_SCHEMA)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    schema = json.loads(args.schema.read_text())
    Draft202012Validator.check_schema(schema)

    checklists: dict[str, dict] = {}
    paths = args.checklist or sorted((REPO / "examples").glob("*.ocl.json"))
    for p in paths:
        doc = json.loads(p.read_text())
        checklists[content_hash(doc)] = doc

    failed = 0
    for path in args.logs:
        f = validate_log(path, schema, checklists)
        bad = f.errors or (args.strict and f.warnings)
        status = "FAIL" if bad else ("warn" if f.warnings else "ok")
        print(f"[{status}] {path.name}")
        for m in f.errors:
            print(f"    error: {m}")
        for m in f.warnings:
            print(f"    warn:  {m}")
        if bad:
            failed += 1

    print(f"\n{len(args.logs) - failed}/{len(args.logs)} log(s) passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
