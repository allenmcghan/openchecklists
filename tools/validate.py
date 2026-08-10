#!/usr/bin/env python3
"""Validate Open Checklist files against the schema and the corpus policy rules.

Two layers, deliberately separate:

  schema  - structural validity. Anything a third-party consumer can rely on.
            Enforced by JSON Schema so that non-Python consumers get the same
            answer from any validator.

  policy  - corpus admission rules that JSON Schema cannot express: cross-field
            consistency, reviewer independence, reference resolution, and the
            rule that an unreviewed file may never look trusted. These are the
            rules that keep a machine transcription from being mistaken for a
            checked one, so they are errors, not warnings.

Exit status is 0 only when every file passes both layers with no errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("jsonschema is required: pip install jsonschema")

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "schema" / "open-checklist-1.0.schema.json"

# An item read with less confidence than this must be resolved by a human
# before the file can leave the unreviewed state.
CONFIDENCE_THRESHOLD = 0.98

INFORMATIONAL_TYPES = {"subtitle", "note", "caution", "warning", "reference", "blank"}
TASK_TYPES = {"action", "challenge"}


class Findings:
    def __init__(self, path: Path):
        self.path = path
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def canonical_bytes(doc: dict) -> bytes:
    """Serialization used for content hashes only.

    Keys are sorted so that any implementation in any language reproduces the
    same bytes, and therefore the same hash, without needing to agree on a key
    order specification.

    This is deliberately NOT the storage form. Sorting keys alphabetically would
    put `sections` before `title` and scatter the provenance and verification
    blocks through the file, which works against the one thing that matters when
    a human reviews a change to a safety document: noticing the significant
    change among the insignificant ones.
    """
    return (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def stable_bytes(doc: dict) -> bytes:
    """Storage form: author's key order, two-space indent, trailing newline.

    Preserving key order keeps files readable top to bottom; fixing the indent
    and newline keeps diffs minimal and free of whitespace noise.
    """
    return (json.dumps(doc, indent=2, sort_keys=False, ensure_ascii=False) + "\n").encode("utf-8")


def content_hash(doc: dict) -> str:
    """Hash of everything except the verification block.

    Verification records claims *about* the content, so including it would make
    every hash self-invalidating. Excluding it lets tooling detect that content
    changed after a review and downgrade the review automatically.
    """
    stripped = {k: v for k, v in doc.items() if k != "verification"}
    return hashlib.sha256(canonical_bytes(stripped)).hexdigest()


def check_schema(doc: dict, schema: dict, f: Findings) -> None:
    validator = Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "(root)"
        f.error(f"schema: {loc}: {err.message}")


def check_tickability(doc: dict, f: Findings) -> None:
    """A warning is not a task. The schema pins the value; policy pins presence.

    tickable is required in practice so that a consumer never has to consult a
    type table to decide whether to draw a checkbox. A missing tickable on an
    information item is the exact failure mode that puts a checkbox next to a
    warning.
    """
    for si, section in enumerate(doc.get("sections", [])):
        for ii, item in enumerate(section.get("items", [])):
            where = f"sections/{si}/items/{ii}"
            itype = item.get("type")
            if itype == "blank":
                continue
            if "tickable" not in item:
                f.error(f"policy: {where}: tickable must be stated explicitly (type={itype})")
                continue
            if itype in INFORMATIONAL_TYPES and item["tickable"]:
                f.error(f"policy: {where}: type={itype} must not be tickable")
            if itype in TASK_TYPES and not item["tickable"]:
                f.error(f"policy: {where}: type={itype} must be tickable")


def check_references(doc: dict, f: Findings) -> None:
    section_ids: set[str] = set()
    for si, section in enumerate(doc.get("sections", [])):
        sid = section.get("id")
        if sid:
            if sid in section_ids:
                f.error(f"policy: sections/{si}: duplicate section id {sid!r}")
            section_ids.add(sid)

    for si, section in enumerate(doc.get("sections", [])):
        item_ids: set[str] = set()
        for ii, item in enumerate(section.get("items", [])):
            where = f"sections/{si}/items/{ii}"
            iid = item.get("id")
            if iid:
                if iid in item_ids:
                    f.error(f"policy: {where}: duplicate item id {iid!r} within section")
                item_ids.add(iid)
            target = (item.get("reference") or {}).get("section_id")
            if target and target not in section_ids:
                f.error(f"policy: {where}: reference to unknown section id {target!r}")


def check_verification_consistency(doc: dict, f: Findings) -> None:
    ver = doc.get("verification", {})
    prov = doc.get("provenance", {})
    fidelity = ver.get("source_fidelity")
    operational = ver.get("operational_review")
    reviews = ver.get("reviews", [])
    method = (prov.get("transcription") or {}).get("method")
    source_kind = (prov.get("source") or {}).get("kind")

    comparisons = [r for r in reviews if r.get("type") == "source_comparison"]
    comparison_reviewers = {r.get("reviewer", "").strip().casefold() for r in comparisons}
    comparison_reviewers.discard("")

    # A fidelity claim has to be backed by recorded review events. Without this,
    # "dual_reviewed" is just a string somebody typed.
    if fidelity == "single_reviewed" and len(comparison_reviewers) < 1:
        f.error("policy: source_fidelity=single_reviewed requires at least one source_comparison review")
    if fidelity == "dual_reviewed" and len(comparison_reviewers) < 2:
        f.error(
            "policy: source_fidelity=dual_reviewed requires source_comparison reviews "
            f"from two distinct reviewers (found {len(comparison_reviewers)})"
        )

    # not_applicable means there is no source document to compare against. If a
    # source was transcribed, that claim is false.
    if fidelity == "not_applicable":
        if source_kind not in ("none", None):
            f.error(
                f"policy: source_fidelity=not_applicable but provenance.source.kind={source_kind!r}; "
                "a file with a source document must be compared against it"
            )
        if method in ("ocr_raw", "ocr_assisted", "manual_transcription", "format_conversion"):
            f.error(
                f"policy: source_fidelity=not_applicable is inconsistent with transcription.method={method!r}"
            )
    elif source_kind in ("none",) and fidelity != "not_applicable":
        f.error("policy: authored content (source.kind=none) must use source_fidelity=not_applicable")

    # Reviewer independence: checking your own transcription is not review.
    transcribers = {
        c.get("name", "").strip().casefold()
        for c in prov.get("contributors", [])
        if "transcriber" in c.get("role", [])
    }
    transcribers.discard("")
    for r in comparisons:
        if r.get("reviewer", "").strip().casefold() in transcribers:
            f.error(
                f"policy: {r.get('reviewer')!r} both transcribed and source-reviewed this file; "
                "review must be independent"
            )

    if operational == "ground_checked" and not any(r.get("type") == "ground_check" for r in reviews):
        f.error("policy: operational_review=ground_checked requires a ground_check review")
    if operational == "flown" and not any(r.get("type") == "flight_check" for r in reviews):
        f.error("policy: operational_review=flown requires a flight_check review")

    # A review is a claim about specific content. If the content moved on, the
    # claim no longer covers it.
    current = content_hash(doc)
    for i, r in enumerate(reviews):
        stated = r.get("content_hash")
        if stated and stated != current:
            f.warn(
                f"verification/reviews/{i}: content changed since this {r.get('type')} review "
                f"by {r.get('reviewer')!r}; the review no longer covers the current content"
            )

    # Low-confidence readings are unresolved questions. They cannot coexist with
    # a claim that a human checked the file.
    low = [
        f"sections/{si}/items/{ii}"
        for si, section in enumerate(doc.get("sections", []))
        for ii, item in enumerate(section.get("items", []))
        if item.get("source_confidence") is not None and item["source_confidence"] < CONFIDENCE_THRESHOLD
    ]
    if low and fidelity not in ("unreviewed", None):
        f.error(
            f"policy: {len(low)} item(s) below the confidence threshold {CONFIDENCE_THRESHOLD} "
            f"but source_fidelity={fidelity}; resolve them first (first: {low[0]})"
        )

    # An unresolved safety defect disqualifies a file from looking trustworthy,
    # regardless of how many people reviewed it.
    defects = [i for i in ver.get("known_issues", []) if i.get("severity") == "safety_defect"]
    if defects and (fidelity == "dual_reviewed" and operational == "flown"):
        f.error(
            "policy: file carries an unresolved safety_defect and must not hold the highest "
            "verification state on both axes"
        )


def check_rights(doc: dict, f: Findings) -> None:
    rights = doc.get("rights", {})
    status = rights.get("status")
    prov_source = doc.get("provenance", {}).get("source", {})

    if status == "unresolved":
        f.error("policy: rights.status=unresolved must not be published; resolve rights before merge")
    if status == "upstream_reserved":
        f.error(
            "policy: rights.status=upstream_reserved must not be published in the corpus; "
            "the project cannot license text it does not own"
        )
    if status == "original_expression" and prov_source.get("kind") not in ("none", None):
        f.warn(
            f"rights.status=original_expression with source.kind={prov_source.get('kind')!r}: "
            "confirm the wording is genuinely the contributor's own and not the source's"
        )
    if status == "public_domain":
        basis = rights.get("public_domain_basis")
        if basis == "us_government_work" and prov_source.get("kind") != "government_publication":
            f.error(
                "policy: public_domain_basis=us_government_work requires "
                "provenance.source.kind=government_publication"
            )
    if prov_source.get("kind") == "simulator_product":
        f.error(
            "policy: flight-simulator product documentation is not an admissible source; "
            "it is vendor-copyrighted and not airworthiness data"
        )


def check_structure_sanity(doc: dict, f: Findings) -> None:
    for si, section in enumerate(doc.get("sections", [])):
        items = section.get("items", [])
        crit = section.get("criticality", "normal")
        memory = [i for i in items if i.get("memory_item")]
        if memory and crit == "normal":
            f.warn(
                f"sections/{si}: memory items in a section marked criticality=normal; "
                "memory items normally belong to abnormal or emergency procedures"
            )
        # Indentation describes subordination, so an item cannot be subordinate
        # to nothing.
        prev = 0
        for ii, item in enumerate(items):
            depth = item.get("indent", 0)
            if depth > prev + 1:
                f.error(
                    f"policy: sections/{si}/items/{ii}: indent jumps from {prev} to {depth}; "
                    "an item can only be one level deeper than the item above it"
                )
            prev = depth
        if all(i.get("type") in INFORMATIONAL_TYPES for i in items):
            f.warn(f"sections/{si}: section contains no actionable item")


def check_file_naming(path: Path, doc: dict, f: Findings) -> None:
    expected = f"{doc.get('id')}.ocl.json"
    if path.name != expected:
        f.error(f"policy: filename {path.name!r} does not match id; expected {expected!r}")


def check_stable_form(path: Path, doc: dict, raw: bytes, f: Findings) -> None:
    """Files should be stored in the stable, diffable form.

    Reported as a warning, not an error: it is a hygiene property, and tooling
    can fix it mechanically with --write-stable.
    """
    if raw != stable_bytes(doc):
        f.warn("not in stable form (2-space indent, trailing newline); run with --write-stable")


def validate_file(path: Path, schema: dict, check_form: bool) -> Findings:
    f = Findings(path)
    raw = path.read_bytes()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        f.error(f"invalid JSON: {exc}")
        return f

    check_schema(doc, schema, f)
    if f.errors:
        # Policy checks assume a structurally valid document; running them on a
        # malformed one produces noise that hides the real problem.
        return f

    check_file_naming(path, doc, f)
    check_tickability(doc, f)
    check_references(doc, f)
    check_verification_consistency(doc, f)
    check_rights(doc, f)
    check_structure_sanity(doc, f)
    if check_form:
        check_stable_form(path, doc, raw, f)
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="files or directories (default: examples/)")
    ap.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--check-form", action="store_true", help="also check the stable storage form")
    ap.add_argument("--write-stable", action="store_true", help="rewrite files in the stable storage form")
    ap.add_argument("--print-hash", action="store_true", help="print each file's content hash")
    args = ap.parse_args()

    schema = json.loads(args.schema.read_text())
    Draft202012Validator.check_schema(schema)

    targets = args.paths or [REPO / "examples"]
    files: list[Path] = []
    for t in targets:
        files.extend(sorted(t.rglob("*.ocl.json")) if t.is_dir() else [t])

    if not files:
        print("no .ocl.json files found", file=sys.stderr)
        return 1

    failed = 0
    for path in files:
        if args.write_stable:
            doc = json.loads(path.read_bytes())
            path.write_bytes(stable_bytes(doc))

        f = validate_file(path, schema, args.check_form or args.write_stable)
        rel = path.relative_to(REPO) if path.is_relative_to(REPO) else path

        if args.print_hash and not f.errors:
            print(f"{content_hash(json.loads(path.read_bytes()))}  {rel}")

        bad = f.errors or (args.strict and f.warnings)
        status = "FAIL" if bad else ("warn" if f.warnings else "ok")
        print(f"[{status}] {rel}")
        for msg in f.errors:
            print(f"    error: {msg}")
        for msg in f.warnings:
            print(f"    warn:  {msg}")
        if bad:
            failed += 1

    print(f"\n{len(files) - failed}/{len(files)} file(s) passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
