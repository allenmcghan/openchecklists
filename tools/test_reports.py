#!/usr/bin/env python3
"""Negative tests for validate_report.py.

Same discipline as test_validate.py: break one thing, assert the tool objects. The
rules under test are the ones that make a report more than a comment — a confirmed
defect has to cost the file its verification badge, and a live safety concern has to
travel inside the file rather than only on a web page.

Run: python3 tools/test_reports.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import content_hash  # noqa: E402
from validate_report import load_corpus, validate_report  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "schema" / "open-checklist-report-1.0.schema.json").read_text())
CHECKLIST_PATHS = sorted((REPO / "examples").glob("*.ocl.json"))
GOOD = json.loads((REPO / "examples" / "report-t34a-0002-omitted-emergency-sections.ocl-report.json").read_text())

TMP = Path(__file__).resolve().parent / ".test-tmp"


def run(report: dict, checklists: list[dict] | None = None):
    TMP.mkdir(exist_ok=True)
    if checklists is None:
        by_hash, by_id = load_corpus(CHECKLIST_PATHS)
    else:
        by_hash = {content_hash(d): d for d in checklists}
        by_id = {d["id"]: d for d in checklists}
    p = TMP / "r.ocl-report.json"
    p.write_text(json.dumps(report, indent=2))
    try:
        return validate_report(p, SCHEMA, by_hash, by_id)
    finally:
        p.unlink(missing_ok=True)
        if not any(TMP.iterdir()):
            TMP.rmdir()


CASES: list[tuple[str, object, str]] = []


def case(label: str, expect: str):
    def deco(fn):
        CASES.append((label, fn, expect))
        return fn

    return deco


def t34() -> dict:
    return json.loads((REPO / "examples" / "beechcraft-t-34a-usaf.ocl.json").read_text())


# --- rules about the report's effect on the targeted file -------------------


@case("confirmed transcription error leaves a reviewed file still claiming review", "not evidence")
def _(r, cls):
    doc = cls[0]
    doc["verification"]["source_fidelity"] = "single_reviewed"
    doc["verification"]["reviews"] = [
        {"type": "source_comparison", "reviewer": "Someone Else", "date": "2026-07-01"}
    ]
    r["target"]["content_hash"] = content_hash(doc)


@case("demotion recorded, so the same situation is accepted", "")
def _(r, cls):
    doc = cls[0]
    doc["verification"]["source_fidelity"] = "single_reviewed"
    doc["verification"]["reviews"] = [
        {"type": "source_comparison", "reviewer": "Someone Else", "date": "2026-07-01"}
    ]
    r["target"]["content_hash"] = content_hash(doc)
    r["resolution"]["demoted_verification"] = True


@case("safety-critical report against a file with no safety_defect issue", "would not travel")
def _(r, cls):
    doc = cls[0]
    doc["verification"]["known_issues"] = [
        {"severity": "content_gap", "description": "something minor", "location": "whole file"}
    ]
    r["target"]["content_hash"] = content_hash(doc)


@case("confirmed newer revision naming the revision already claimed", "same revision")
def _(r, cls):
    r["type"] = "source_revision_available"
    r["evidence"] = {"kind": "newer_source_revision", "document_revision": "10 February 1958"}
    r["severity"] = "minor"
    r["resolution"]["confirmed_severity"] = "minor"


# --- rules about the report itself -----------------------------------------


@case("target section that does not exist", "does not exist")
def _(r, cls):
    r["target"]["section_id"] = "no-such-section"


@case("target item index out of range", "out of range")
def _(r, cls):
    r["target"]["section_id"] = "propeller-failure"
    r["target"]["item_index"] = 99


@case("resolution dated before submission", "precedes submitted")
def _(r, cls):
    r["resolution"]["at"] = "2020-01-01T00:00:00-05:00"


@case("open report carrying a resolution", "must not carry a resolution")
def _(r, cls):
    r["status"] = "open"


@case("closed report with no resolution", "resolution")
def _(r, cls):
    r["status"] = "rejected"
    del r["resolution"]


@case("duplicate without naming the original", "duplicate_of")
def _(r, cls):
    r["status"] = "duplicate"


@case("staleness claim with no supporting document", "evidence")
def _(r, cls):
    r["type"] = "stale_item"
    r["evidence"] = {"kind": "observed_on_aircraft"}


@case("transcription error with nothing quoted", "as_written")
def _(r, cls):
    del r["body"]["as_written"]


@case("airframe variation with no aircraft identified", "aircraft")
def _(r, cls):
    r["type"] = "airframe_variation"


@case("unknown report type", "not one of")
def _(r, cls):
    r["type"] = "vibes"


def main() -> int:
    baseline = run(copy.deepcopy(GOOD))
    if baseline.errors:
        print("BASELINE FAILED:")
        for e in baseline.errors:
            print("   ", e)
        return 1
    print(f"[ok]   baseline: {GOOD['id']} validates cleanly")

    failures = 0
    for label, mutate, expect in CASES:
        rep = copy.deepcopy(GOOD)
        cls = [t34()]
        mutate(rep, cls)
        f = run(rep, cls)
        blob = " | ".join(f.errors)

        if expect == "":
            # A case asserting the tool *accepts* something.
            if f.errors:
                print(f"[FAIL] {label}: expected acceptance, got errors")
                for e in f.errors:
                    print(f"         {e}")
                failures += 1
            else:
                print(f"[ok]   accepted: {label}")
            continue

        if f.errors and any(part in blob for part in expect.split("|")):
            print(f"[ok]   caught: {label}")
        elif f.errors:
            print(f"[FAIL] {label}: rejected for the wrong reason (wanted {expect!r})")
            for e in f.errors:
                print(f"         {e}")
            failures += 1
        else:
            print(f"[FAIL] {label}: accepted, expected an error matching {expect!r}")
            failures += 1

    print(f"\n{len(CASES) - failures}/{len(CASES)} case(s) behaved correctly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
