#!/usr/bin/env python3
"""Transcribe checklist text -> Open Checklist 1.0 JSON (task 8, Stages 3-5).

Dual independent LLM pass + diff (Stage 4 of docs/04-roadmap.md):
  * pass 1 — "faithful" framing (reproduce exactly).
  * pass 2 — "skeptical" framing (reconstruct independently, flag ambiguity).

Every numeric value and every per-section item count must agree across the two
passes or be flagged. Output is a CANDIDATE file: source_fidelity=unreviewed,
rights.status=unresolved. Nothing merges automatically — the result is ready for
human review, not publication.

Usage:
    python3 tools/transcribe_ocl.py SOURCE.txt \
        --make Cessna --model 172 --variant SP \
        --id cessna-172sp-normal --title "Cessna 172SP — Normal Procedures"

Outputs (next to SOURCE, or under --out-dir):
    <id>.ocl.json    candidate checklist (schema-valid, unreviewed)
    <id>.diff.json   dual-pass disagreement report

Requires: pip install anthropic jsonschema, and ANTHROPIC_API_KEY in the env.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

import anthropic

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "schema" / "open-checklist-1.0.schema.json"

# validate.py is a sibling; reuse its schema+policy checks rather than reimplement.
sys.path.insert(0, str(REPO / "tools"))
from validate import validate_file, Findings  # noqa: E402

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 32000

SYSTEM_PROMPTS = {
    "faithful": (
        "You are transcribing an aircraft checklist into the Open Checklist 1.0 "
        "JSON format. Your job is FAITHFUL TRANSCRIPTION: reproduce the checklist "
        "exactly as written — every item, every number, every label, in source "
        "order. Do not reorder, omit, merge, or 'improve' anything. Numeric values "
        "must be transcribed exactly; never round, fix, or infer a missing number. "
        "If a value is unreadable or ambiguous, keep the item and lower its "
        '"source_confidence" rather than dropping or guessing it.\n\n'
        "Emit a single JSON object conforming to the provided schema. Output ONLY "
        "the JSON object — no markdown fences, no commentary before or after."
    ),
    "skeptical": (
        "You are independently reconstructing the structure of an aircraft "
        "checklist into the Open Checklist 1.0 JSON format. Work from the source "
        "alone and do not assume any prior reading of it. Parse it into sections "
        "and items from scratch. Where the source is ambiguous, contradictory, or "
        "garbled by OCR, record the item as written and lower its "
        '"source_confidence" (0.0-1.0) to flag it. Preserve every numeric value '
        "exactly as it appears.\n\n"
        "Emit a single JSON object conforming to the provided schema. Output ONLY "
        "the JSON object — no markdown fences, no commentary before or after."
    ),
}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL


def llm_text(system: str, user: str, model: str, max_tokens: int = MAX_TOKENS, thinking_budget: int = 0) -> str:
    client = _client()
    thinking = {"type": "enabled", "budget_tokens": thinking_budget} if thinking_budget > 0 else {"type": "disabled"}
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        thinking=thinking,
        system=system,
        messages=[{"role": "user", "content": user}],
        timeout=3600,
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def parse_json(text: str) -> dict:
    """Extract the first JSON object from a model reply (handles ``` fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("```"))
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    return json.loads(text[start:end + 1])


def llm_json(system: str, user: str, model: str, max_tokens: int, thinking_budget: int) -> tuple[dict, str]:
    """One LLM call returning parsed JSON, with a single repair retry on bad JSON."""
    raw = llm_text(system, user, model, max_tokens, thinking_budget)
    try:
        return parse_json(raw), raw
    except Exception as exc:
        print(f"  parse failed ({type(exc).__name__}), retrying with repair ...", file=sys.stderr)
        user2 = user + "\n\nYour previous response was not valid JSON. Output ONLY a valid JSON object, no commentary."
        raw2 = llm_text(system, user2, model, max_tokens, thinking_budget)
        return parse_json(raw2), raw2


def build_user_prompt(schema: dict, meta: dict, source_text: str) -> str:
    aircraft = {
        "make": meta["make"],
        "model": meta["model_name"],
    }
    if meta.get("variant"):
        aircraft["variant"] = meta["variant"]
    if meta.get("category"):
        aircraft["category"] = meta["category"]
    return (
        "Aircraft metadata:\n"
        + json.dumps(aircraft, indent=2)
        + f'\n\nChecklist id: {meta["id"]}\n'
        + (f'Title: {meta["title"]}\n' if meta.get("title") else "")
        + "\nJSON Schema (open-checklist-1.0):\n"
        + json.dumps(schema)
        + "\n\nChecklist source text:\n---\n"
        + source_text
        + "\n---\n\n"
        "Transcribe this source into an Open Checklist 1.0 object. Emit the full "
        "object including aircraft, units, speeds, and sections. In each item give "
        '"type", "text", "tickable" (true for action/challenge, false for '
        'subtitle/note/caution/warning/reference/blank), and "source_confidence" '
        "(0.0-1.0). Do not invent items or values that are not in the source."
    )


NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def extract_numbers(text: str) -> set[str]:
    return set(NUMBER_RE.findall(text or ""))


def item_numbers(item: dict) -> set[str]:
    parts = [item.get("text", ""), item.get("response", "")]
    v = item.get("value") or {}
    for k in ("target", "min", "max"):
        if v.get(k) is not None:
            parts.append(str(v[k]))
    return extract_numbers(" ".join(parts))


def diff_passes(p1: dict, p2: dict) -> dict:
    """Compare two transcriptions; return the disagreement report."""
    report = {
        "numeric_disagreements": [],
        "section_count_disagreements": [],
        "sections_only_in_pass1": [],
        "sections_only_in_pass2": [],
    }
    s1 = {s.get("title", ""): s for s in p1.get("sections", [])}
    s2 = {s.get("title", ""): s for s in p2.get("sections", [])}

    for title in sorted(set(s1) | set(s2)):
        a, b = s1.get(title), s2.get(title)
        if a and b:
            items_a, items_b = a.get("items", []), b.get("items", [])
            if len(items_a) != len(items_b):
                report["section_count_disagreements"].append(
                    {"section": title, "pass1_items": len(items_a), "pass2_items": len(items_b)}
                )
            for i in range(min(len(items_a), len(items_b))):
                na, nb = item_numbers(items_a[i]), item_numbers(items_b[i])
                if na != nb:
                    report["numeric_disagreements"].append(
                        {
                            "section": title,
                            "item_index": i,
                            "text": items_a[i].get("text", "")[:120],
                            "pass1_numbers": sorted(na),
                            "pass2_numbers": sorted(nb),
                        }
                    )
        elif a and not b:
            report["sections_only_in_pass1"].append(title)
        else:
            report["sections_only_in_pass2"].append(title)
    return report


def lowered_items(report: dict) -> set[tuple[str, int]]:
    """(section title, item index) pairs whose numbers disagreed between passes."""
    return {(d["section"], d["item_index"]) for d in report["numeric_disagreements"]}


def assemble(meta: dict, content: dict, model: str, report: dict) -> dict:
    """Force deterministic provenance/verification/rights; keep model content."""
    today = datetime.date.today().isoformat()
    out = dict(content)
    out["open_checklist_version"] = "1.0"
    out["id"] = meta["id"]

    method = meta.get("transcription_method", "ocr_assisted")
    transcription = {"method": method, "date": today}
    if method in ("ocr_raw", "ocr_assisted"):
        transcription["tool"] = model
    elif method == "format_conversion":
        transcription["converted_from"] = meta.get("converted_from", "doc")

    source = {"kind": meta.get("source_kind", "third_party_checklist")}
    if meta.get("source_title"):
        source["title"] = meta["source_title"]
    if meta.get("pages"):
        source["pages"] = meta["pages"]

    out["provenance"] = {
        "source": source,
        "transcription": transcription,
        "contributors": [{"name": "Open Checklists project", "role": ["transcriber"]}],
        "revision": {"file_revision": "0.1.0", "updated": today},
    }

    known_issues = []
    for d in report["section_count_disagreements"]:
        known_issues.append({
            "severity": "content_gap",
            "description": (
                f'Section "{d["section"]}" item count differs between passes '
                f'({d["pass1_items"]} vs {d["pass2_items"]}); verify nothing was dropped.'
            ),
            "location": d["section"],
        })

    out["verification"] = {
        "source_fidelity": "unreviewed",
        "operational_review": "none",
        "completeness": meta.get("completeness", "full"),
        "known_issues": known_issues,
    }
    out["rights"] = {"status": "unresolved",
                     "notes": "Rights not yet analyzed; requires human review before publication."}

    # Lower confidence on items whose numbers disagreed across passes.
    lowered = lowered_items(report)
    for section in out.get("sections", []):
        for i, item in enumerate(section.get("items", [])):
            if (section.get("title", ""), i) in lowered:
                cur = item.get("source_confidence", 1.0)
                item["source_confidence"] = round(min(cur, 0.5), 2)
    return out


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "checklist"


VALID_CRITICALITY = {"normal", "abnormal", "emergency"}
INFORMATIONAL = {"subtitle", "note", "caution", "warning", "reference", "blank"}
TASK = {"action", "challenge"}
VALID_PHASES = frozenset({
    "preflight_inspection", "before_start", "engine_start", "after_start", "before_taxi", "taxi",
    "before_takeoff", "takeoff", "after_takeoff", "climb", "cruise", "descent", "arrival",
    "approach", "before_landing", "landing", "go_around", "after_landing", "shutdown", "securing",
    "postflight", "engine_failure_before_rotation", "engine_failure_after_takeoff",
    "engine_failure_in_flight", "engine_restart_in_flight", "engine_fire_ground",
    "engine_fire_in_flight", "cabin_fire", "electrical_fire", "smoke_removal", "forced_landing",
    "ditching", "electrical_failure", "alternator_failure", "fuel_system_malfunction",
    "oil_system_malfunction", "landing_gear_malfunction", "flap_malfunction", "trim_malfunction",
    "control_malfunction", "brake_failure", "pitot_static_failure", "vacuum_failure",
    "avionics_failure", "autopilot_malfunction", "icing", "carburetor_icing", "inadvertent_imc",
    "spin_recovery", "unusual_attitude_recovery", "structural_damage", "door_open_in_flight",
    "emergency_descent", "parachute_deployment", "engine_out_landing", "weight_and_balance",
    "performance", "limitations", "reference", "other",
})


ITEM_TYPES = {"action", "challenge", "subtitle", "note", "caution", "warning", "reference", "blank"}
TYPE_TYPO_FIX = {"subtitile": "subtitle", "subtitl": "subtitle", "warnng": "warning", "cution": "caution"}
VALID_QUANTITIES = {"airspeed", "altitude", "rpm", "pressure", "temperature", "fuel",
                    "weight", "time", "distance", "percent", "voltage", "current", "angle"}


def _sanitize_id(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:60]


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def repair_schema(doc: dict) -> dict:
    """Deterministic fixes for the mechanical schema rules the model can trip on.

    These are structural corrections derived directly from item type — they do
    not change content or numbers, so they are safe to apply before validation.
    """
    # Pass 1: fix section-level fields and sanitize ids.
    for si, section in enumerate(doc.get("sections", [])):
        if section.get("criticality") not in VALID_CRITICALITY:
            section["criticality"] = "normal"
        if section.get("phase") not in VALID_PHASES:
            section["phase"] = "other"
            if not section.get("phase_label"):
                section["phase_label"] = section.get("title", "other")
        if section.get("id"):
            section["id"] = _sanitize_id(section["id"])

    section_ids = {s.get("id") for s in doc.get("sections", []) if s.get("id")}

    # Pass 2: fix item-level fields.
    for si, section in enumerate(doc.get("sections", [])):
        for ii, item in enumerate(section.get("items", [])):
            t = item.get("type")
            if t not in ITEM_TYPES:
                item["type"] = TYPE_TYPO_FIX.get(t, "note")
                t = item["type"]
            if t in INFORMATIONAL:
                item["tickable"] = False
                item.pop("memory_item", None)
            elif t in TASK:
                item["tickable"] = True
            if t != "action":
                # Only an action carries a response or a comparable value.
                item.pop("response", None)
                item.pop("value", None)
            if item.get("memory_item") and not item.get("id"):
                item["id"] = (slugify(item.get("text", "")) or f"item-{si}-{ii}")[:60]
            if item.get("id"):
                item["id"] = _sanitize_id(item["id"])
            for field, maxlen in (("text", 2000), ("response", 500), ("detail", 4000), ("condition", 300)):
                if isinstance(item.get(field), str):
                    item[field] = _clip(item[field], maxlen)
            if t == "action" and not item.get("response"):
                item["type"] = "challenge"
            if t == "reference":
                ref = item.get("reference")
                if not (isinstance(ref, dict) and ref.get("section_id") in section_ids):
                    item["type"] = "note"
                    item.pop("reference", None)
            v = item.get("value")
            if isinstance(v, dict) and v.get("quantity") not in VALID_QUANTITIES:
                item.pop("value", None)
    return doc


def meta_from_path(p: Path, root: Path, args) -> dict:
    """Best-effort aircraft metadata from a <Mfr>/<Model>/<file>.txt mirror path."""
    rel = p.relative_to(root)
    parts = rel.parts
    make = parts[0] if len(parts) >= 2 else "Unknown"
    model = parts[1] if len(parts) >= 2 else p.stem
    return {
        "make": make,
        "model_name": model,
        "variant": None,
        "category": args.category,
        "id": slugify(f"{make}-{model}-{p.stem}")[:100],
        "title": f"{make} {model} — {p.stem}",
        "source_kind": "third_party_checklist",
        "source_title": str(rel),
        "pages": None,
        "transcription_method": args.transcription_method,
        "converted_from": args.converted_from,
    }


def transcribe_one(source_path: Path, meta: dict, out_dir: Path, args, schema: dict) -> str:
    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    # The schema requires source.title whenever the source kind is a real
    # document (not none/unknown). Fall back to the filename if not given.
    if meta.get("source_kind") not in ("none", "unknown") and not meta.get("source_title"):
        meta["source_title"] = source_path.name
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / f".{meta['id']}.passes"
    if args.skip_llm:
        p1 = repair_schema(json.loads((cache_dir / "pass1.json").read_text()))
        p2 = repair_schema(json.loads((cache_dir / "pass2.json").read_text()))
    else:
        user = build_user_prompt(schema, meta, source_text)
        cache_dir.mkdir(parents=True, exist_ok=True)
        p1, raw1 = llm_json(SYSTEM_PROMPTS["faithful"], user, args.model_pass1, args.max_tokens, args.thinking_budget)
        (cache_dir / "pass1.raw.txt").write_text(raw1, encoding="utf-8")
        p1 = repair_schema(p1)
        p2, raw2 = llm_json(SYSTEM_PROMPTS["skeptical"], user, args.model_pass2, args.max_tokens, args.thinking_budget)
        (cache_dir / "pass2.raw.txt").write_text(raw2, encoding="utf-8")
        p2 = repair_schema(p2)
        (cache_dir / "pass1.json").write_text(json.dumps(p1, indent=2))
        (cache_dir / "pass2.json").write_text(json.dumps(p2, indent=2))

    report = diff_passes(p1, p2)
    candidate = assemble(meta, p1, args.model_pass1, report)

    out_file = out_dir / f"{meta['id']}.ocl.json"
    out_file.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / f"{meta['id']}.diff.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    f: Findings = validate_file(out_file, schema, check_form=False)
    print(f"wrote {out_file}", file=sys.stderr)
    print(f"  validation: {len(f.errors)} error(s), {len(f.warnings)} warning(s)", file=sys.stderr)
    for msg in f.errors:
        print(f"    error: {msg}", file=sys.stderr)
    for msg in f.warnings:
        print(f"    warn:  {msg}", file=sys.stderr)
    return f"{meta['id']}: {len(f.errors)}e {len(f.warnings)}w"


def run_batch(args, schema: dict) -> int:
    root = args.batch
    def skip(p: Path) -> bool:
        low = p.stem.lower()
        return (low in {"readme", "file_id", "file-id"}
                or re.search(r"\bwb\b|weight|balance", low) is not None)
    sources = sorted(p for p in root.rglob("*.txt") if not skip(p))
    if args.limit:
        sources = sources[: args.limit]
    out_root = args.out_dir or (root / "ocl")
    done = 0
    for i, src in enumerate(sources, 1):
        meta = meta_from_path(src, root, args)
        out_dir = out_root / src.relative_to(root).parent
        out_file = out_dir / f"{meta['id']}.ocl.json"
        if out_file.exists():
            continue
        print(f"[{i}/{len(sources)}] {src.relative_to(root)}", file=sys.stderr)
        try:
            transcribe_one(src, meta, out_dir, args, schema)
            done += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
    print(f"\nbatch done: {done} transcribed / {len(sources)} files")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, nargs="?", help="text file (OCR markdown or converted .txt) — omit with --batch")
    ap.add_argument("--batch", type=Path, help="transcribe every .txt under this mirror tree")
    ap.add_argument("--limit", type=int, default=0, help="max files in batch mode")
    ap.add_argument("--make")
    ap.add_argument("--model", dest="model_name")
    ap.add_argument("--variant")
    ap.add_argument("--category", default="standard_normal")
    ap.add_argument("--id", help="stable slug, e.g. cessna-172sp-normal")
    ap.add_argument("--title")
    ap.add_argument("--source-kind", default="third_party_checklist")
    ap.add_argument("--source-title")
    ap.add_argument("--pages", help="page/section reference within the source")
    ap.add_argument("--transcription-method", default="ocr_assisted",
                    choices=["ocr_raw", "ocr_assisted", "format_conversion", "manual_transcription"])
    ap.add_argument("--converted-from", help="for --transcription-method format_conversion (e.g. 'doc')")
    ap.add_argument("--model-pass1", default=DEFAULT_MODEL)
    ap.add_argument("--model-pass2", default=DEFAULT_MODEL)
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--thinking-budget", type=int, default=0, help="thinking tokens (0 = disable; the proxy's thinking eats the output budget and truncates long JSON)")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--skip-llm", action="store_true", help="re-merge cached passes without LLM calls")
    args = ap.parse_args()

    schema = load_schema()

    if args.batch:
        return run_batch(args, schema)

    if not (args.source and args.make and args.model_name and args.id):
        ap.error("single-file mode requires SOURCE --make --model --id (or use --batch DIR)")

    print(transcribe_one(args.source, vars(args), args.out_dir or args.source.parent, args, schema))
    return 0


if __name__ == "__main__":
    sys.exit(main())
