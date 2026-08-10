#!/usr/bin/env python3
"""Validate Open Checklist field reports, and enforce their effect on the corpus.

    python3 tools/validate_report.py examples/reports/*.ocl-report.json

A comment thread is a place to put a concern. A report is a thing that changes the
file's standing. The difference is entirely in the checks below, which is why this
tool exists rather than the reports living as prose in an issue tracker:

  * A confirmed transcription_error or stale_item against the *current* version of a
    file must have demoted that file's verification state. A review of content now
    known to be wrong is not evidence of anything, and leaving the badge up is
    worse than never having reviewed it.
  * An open safety_critical report against the current version must be reflected in
    the file's own known_issues, so that anyone who downloads the file sees it.
    A concern visible only on the website is lost the moment the file is exported.
  * A report must resolve to a real section and item, or it cannot be acted on.

Reports are matched to files by content_hash. A report whose target hash is not the
file's current hash refers to a superseded version: it is history, and the
demotion rules no longer apply to it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("jsonschema is required: pip install jsonschema")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import Findings, content_hash  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORT_SCHEMA = REPO / "schema" / "open-checklist-report-1.0.schema.json"

# Report types that invalidate a prior source comparison when confirmed.
FIDELITY_BREAKING = {"transcription_error", "stale_item"}
REVIEWED_STATES = {"single_reviewed", "dual_reviewed"}


def load_corpus(paths: list[Path]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Returns (by_hash, by_id) for the checklist files."""
    by_hash: dict[str, dict] = {}
    by_id: dict[str, dict] = {}
    for p in paths:
        doc = json.loads(p.read_text())
        by_hash[content_hash(doc)] = doc
        by_id[doc["id"]] = doc
    return by_hash, by_id


def check_target(rep: dict, by_hash: dict, by_id: dict, f: Findings) -> tuple[dict | None, bool]:
    """Resolve the report's target. Returns (checklist doc or None, targets_current_version)."""
    t = rep["target"]
    cid, chash = t["checklist_id"], t["content_hash"]
    doc = by_id.get(cid)

    if doc is None:
        f.warn(f"target checklist {cid!r} is not in the corpus provided; cannot verify")
        return None, False

    current = content_hash(doc)
    is_current = chash == current

    if chash not in by_hash:
        if is_current:
            f.error(f"policy: content_hash does not match any file but equals {cid!r}'s hash; corpus inconsistent")
        else:
            f.warn(
                f"report targets version {chash[:12]}… of {cid!r}, which is not the current "
                f"version ({current[:12]}…). Treated as history: demotion rules do not apply."
            )

    sections = {s.get("id"): s for s in doc.get("sections", []) if s.get("id")}
    sid = t.get("section_id")
    if sid is not None:
        sec = sections.get(sid)
        if sec is None:
            # Only an error against the current version; older versions may have had it.
            (f.error if is_current else f.warn)(
                f"{'policy: ' if is_current else ''}target section {sid!r} does not exist in {cid!r}"
            )
        else:
            idx = t.get("item_index")
            if isinstance(idx, int) and idx >= len(sec.get("items", [])):
                (f.error if is_current else f.warn)(
                    f"{'policy: ' if is_current else ''}target item_index {idx} out of range "
                    f"for section {sid!r}"
                )
            iid = t.get("item_id")
            if iid and not any(i.get("id") == iid for i in sec.get("items", [])):
                (f.error if is_current else f.warn)(
                    f"{'policy: ' if is_current else ''}target item_id {iid!r} not found in section {sid!r}"
                )
    return doc, is_current


def check_effect_on_file(rep: dict, doc: dict | None, is_current: bool, f: Findings) -> None:
    if doc is None or not is_current:
        return

    ver = doc.get("verification", {})
    fidelity = ver.get("source_fidelity")
    issues = ver.get("known_issues", [])
    status = rep["status"]
    rtype = rep["type"]
    res = rep.get("resolution", {})

    # A confirmed defect against reviewed content must have cost the file its badge.
    if status in ("confirmed", "fixed") and rtype in FIDELITY_BREAKING:
        if fidelity in REVIEWED_STATES and not res.get("demoted_verification"):
            f.error(
                f"policy: report is {status} for a {rtype} against the current version, but "
                f"{doc['id']!r} still claims source_fidelity={fidelity} and the resolution does "
                "not record a demotion. A review of content known to be wrong is not evidence."
            )

    # An open safety concern must travel with the file, not just live on a website.
    sev = res.get("confirmed_severity") or rep.get("severity")
    if status in ("open", "confirmed") and sev == "safety_critical":
        if not any(i.get("severity") == "safety_defect" for i in issues):
            f.error(
                f"policy: a safety_critical report is {status} against the current version of "
                f"{doc['id']!r}, but that file records no known_issues entry with "
                "severity=safety_defect. The concern would not travel with the downloaded file."
            )

    # A confirmed newer-revision report means the file's stated source revision is behind.
    if status == "confirmed" and rtype == "source_revision_available":
        newer = rep.get("evidence", {}).get("document_revision")
        stated = doc.get("provenance", {}).get("source", {}).get("revision")
        if newer and stated and newer == stated:
            f.error(
                "policy: report confirms a newer source revision, but it names the same revision "
                f"the file already claims ({stated!r})"
            )
        if not any(i.get("severity") in ("safety_defect", "content_gap") for i in issues):
            f.warn(
                f"{doc['id']!r} has a confirmed newer source revision available but records no "
                "known_issues entry about it; downstream users cannot see that it is behind"
            )


def check_internal(rep: dict, f: Findings) -> None:
    res = rep.get("resolution")
    if res and rep["status"] == "open":
        f.error("policy: status=open must not carry a resolution")
    if rep.get("evidence", {}).get("kind") == "none_stated" and rep["status"] == "confirmed":
        f.warn(
            "report confirmed with evidence.kind=none_stated; record what the maintainer checked, "
            "or the confirmation cannot be audited"
        )
    sub = rep.get("submitted")
    at = (res or {}).get("at")
    if sub and at and at < sub:
        f.error("policy: resolution.at precedes submitted")


def validate_report(path: Path, schema: dict, by_hash: dict, by_id: dict) -> Findings:
    f = Findings(path)
    try:
        rep = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        f.error(f"invalid JSON: {exc}")
        return f

    for err in sorted(Draft202012Validator(schema).iter_errors(rep), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
        f.error(f"schema: {loc}: {err.message}")
    if f.errors:
        return f

    check_internal(rep, f)
    doc, is_current = check_target(rep, by_hash, by_id, f)
    check_effect_on_file(rep, doc, is_current, f)
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="*", type=Path)
    ap.add_argument("--checklist", type=Path, action="append", default=[])
    ap.add_argument("--schema", type=Path, default=REPORT_SCHEMA)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    schema = json.loads(args.schema.read_text())
    Draft202012Validator.check_schema(schema)

    by_hash, by_id = load_corpus(args.checklist or sorted((REPO / "examples").glob("*.ocl.json")))

    reports = args.reports or sorted((REPO / "examples").glob("*.ocl-report.json"))
    if not reports:
        print("no reports found")
        return 0

    failed = 0
    for path in reports:
        f = validate_report(path, schema, by_hash, by_id)
        bad = f.errors or (args.strict and f.warnings)
        print(f"[{'FAIL' if bad else ('warn' if f.warnings else 'ok')}] {path.name}")
        for m in f.errors:
            print(f"    error: {m}")
        for m in f.warnings:
            print(f"    warn:  {m}")
        if bad:
            failed += 1

    print(f"\n{len(reports) - failed}/{len(reports)} report(s) passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
