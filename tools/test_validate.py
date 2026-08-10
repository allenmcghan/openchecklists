#!/usr/bin/env python3
"""Negative tests for validate.py.

Each case takes a known-good example, breaks exactly one thing, and asserts the
validator objects. A validator nobody has tried to fool is not evidence of
anything, and the rules being tested here are the ones that stop an unreviewed
file from looking checked.

Run: python3 tools/test_validate.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import Findings, validate_file  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "schema" / "open-checklist-1.0.schema.json").read_text())
GOOD = json.loads((REPO / "examples" / "faa-generic-sep-ground-operations.ocl.json").read_text())

TMP = Path(__file__).resolve().parent / ".test-tmp"


def run(doc: dict, name: str | None = None) -> Findings:
    TMP.mkdir(exist_ok=True)
    path = TMP / (name or f"{doc.get('id', 'x')}.ocl.json")
    path.write_text(json.dumps(doc, indent=2))
    try:
        return validate_file(path, SCHEMA, check_form=False)
    finally:
        path.unlink(missing_ok=True)
        if not any(TMP.iterdir()):
            TMP.rmdir()


CASES: list[tuple[str, callable, str]] = []


def case(label: str, expect: str):
    def deco(fn):
        CASES.append((label, fn, expect))
        return fn

    return deco


@case("a warning marked tickable", "must not be tickable|False was expected")
def _(d):
    d["sections"][3]["items"][0]["tickable"] = True


@case("an action with tickable removed", "tickable must be stated explicitly")
def _(d):
    del d["sections"][1]["items"][3]["tickable"]


@case("a warning given a response", "does not allow|response")
def _(d):
    d["sections"][3]["items"][0]["response"] = "ACKNOWLEDGED"


@case("a warning made a memory item", "memory_item|does not allow|False was expected")
def _(d):
    d["sections"][3]["items"][0]["memory_item"] = True


@case("an action with no response", "'response' is a required property")
def _(d):
    del d["sections"][1]["items"][4]["response"]


@case("fidelity claimed without any review", "requires at least one source_comparison review")
def _(d):
    d["verification"]["source_fidelity"] = "single_reviewed"


@case("dual review claimed with one reviewer", "two distinct reviewers")
def _(d):
    d["verification"]["source_fidelity"] = "dual_reviewed"
    d["verification"]["reviews"] = [
        {"type": "source_comparison", "reviewer": "A. Reviewer", "date": "2026-08-01"}
    ]


@case("transcriber reviewing their own work", "review must be independent")
def _(d):
    d["provenance"]["contributors"] = [{"name": "Sam Transcriber", "role": ["transcriber"]}]
    d["verification"]["source_fidelity"] = "single_reviewed"
    d["verification"]["reviews"] = [
        {"type": "source_comparison", "reviewer": "sam transcriber", "date": "2026-08-01"}
    ]


@case("flown claimed with no flight check", "requires a flight_check review")
def _(d):
    d["verification"]["operational_review"] = "flown"


@case("low-confidence item in a reviewed file", "below the confidence threshold")
def _(d):
    d["sections"][1]["items"][3]["source_confidence"] = 0.4
    d["verification"]["source_fidelity"] = "single_reviewed"
    d["verification"]["reviews"] = [
        {"type": "source_comparison", "reviewer": "A. Reviewer", "date": "2026-08-01"}
    ]


@case("not_applicable fidelity despite a real source", "must be compared against it")
def _(d):
    d["verification"]["source_fidelity"] = "not_applicable"


@case("unresolved rights", "must not be published")
def _(d):
    d["rights"] = {"status": "unresolved"}


@case("upstream_reserved published in the corpus", "cannot license text it does not own")
def _(d):
    d["rights"] = {"status": "upstream_reserved", "redistribution": "no_redistribution"}


@case("upstream_reserved also claiming a corpus licence", "corpus_license|does not allow")
def _(d):
    d["rights"] = {
        "status": "upstream_reserved",
        "redistribution": "no_redistribution",
        "corpus_license": "CC-BY-4.0",
    }


@case("public domain claimed with no basis", "public_domain_basis")
def _(d):
    del d["rights"]["public_domain_basis"]


@case("government-work basis with a manufacturer source", "requires")
def _(d):
    d["provenance"]["source"]["kind"] = "manufacturer_poh"


@case("a simulator manual used as a source", "not an admissible source")
def _(d):
    d["provenance"]["source"]["kind"] = "simulator_product"
    d["rights"] = {"status": "original_expression", "corpus_license": "CC-BY-4.0"}


@case("OCR transcription with no tool recorded", "tool")
def _(d):
    d["provenance"]["transcription"] = {"method": "ocr_raw", "date": "2026-08-10"}


@case("a reference to a section that does not exist", "unknown section id")
def _(d):
    d["sections"][0]["items"][0] = {
        "type": "reference",
        "text": "See the emergency section",
        "tickable": False,
        "reference": {"section_id": "does-not-exist"},
    }


@case("duplicate section ids", "duplicate section id")
def _(d):
    d["sections"][1]["id"] = d["sections"][0]["id"]


@case("phase 'other' with no label", "phase_label")
def _(d):
    d["sections"][0]["phase"] = "other"


@case("an indent level that skips a step", "indent jumps")
def _(d):
    d["sections"][1]["items"][6]["indent"] = 3


@case("an invented phase id", "phase")
def _(d):
    d["sections"][0]["phase"] = "taxiing_out"


@case("filename not matching the id", "does not match id")
def _(d):
    d["id"] = "some-other-id"


@case("an unknown top-level field", "Additional properties")
def _(d):
    d["airworthy"] = True


@case("a future schema version", "'1.0' was expected|const")
def _(d):
    d["open_checklist_version"] = "2.0"


@case("no contributors", "minItems|non-empty|should be non-empty")
def _(d):
    d["provenance"]["contributors"] = []


def main() -> int:
    # The unmodified example must pass, or every negative result below is suspect.
    baseline = run(copy.deepcopy(GOOD))
    if baseline.errors:
        print("BASELINE FAILED - the good example does not validate:")
        for e in baseline.errors:
            print(f"  {e}")
        return 1
    print(f"[ok]   baseline: {GOOD['id']} validates cleanly")

    failures = 0
    for label, mutate, expect in CASES:
        doc = copy.deepcopy(GOOD)
        mutate(doc)
        f = run(doc, name=f"{GOOD['id']}.ocl.json")
        blob = " | ".join(f.errors)
        hit = any(part in blob for part in expect.split("|"))
        if f.errors and hit:
            print(f"[ok]   caught: {label}")
        elif f.errors:
            print(f"[FAIL] {label}: rejected, but not for the expected reason ({expect!r})")
            for e in f.errors:
                print(f"         got: {e}")
            failures += 1
        else:
            print(f"[FAIL] {label}: accepted, expected an error matching {expect!r}")
            failures += 1

    print(f"\n{len(CASES) - failures}/{len(CASES)} negative case(s) caught")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
