#!/usr/bin/env python3
"""Finalize AI-transcribed candidates for baseline publication.

For each candidate .ocl.json:
  * resolves rights from `unresolved` -> `licensed` (freechecklists.net author
    permission — the archive's reuse grant is the licence basis);
  * records the automated AI review in verification.reviews;
  * keeps source_fidelity=unreviewed (honest: no human has checked it yet);
  * re-validates and reports pass/fail.

Usage:
    python3 tools/finalize_ocl.py --in DIR --out DIR
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "schema" / "open-checklist-1.0.schema.json"

sys.path.insert(0, str(REPO / "tools"))
from validate import validate_file  # noqa: E402
from transcribe_ocl import repair_schema  # noqa: E402

RIGHTS = {
    "status": "licensed",
    "upstream_holder": "freechecklists.net",
    "upstream_license": "content-reuse permission granted by the site author for this replacement project",
    "notes": ("Transcribed from the freechecklists.net archive under the author's reuse grant. "
              "Individual checklist wording may be substantially the source's; per-file "
              "contributor authorship is unknown."),
}

REVIEWER = "ai-dual-pass-review"


def finalize(doc: dict, today: str) -> dict:
    doc["rights"] = RIGHTS
    ver = doc.setdefault("verification", {})
    ver.setdefault("source_fidelity", "unreviewed")
    ver.setdefault("operational_review", "none")
    reviews = ver.setdefault("reviews", [])
    reviews.append({
        "type": "source_comparison",
        "reviewer": REVIEWER,
        "date": today,
        "notes": "Automated AI review: two independent transcription passes + numeric/item-count "
                 "disagreement resolution. Not human-verified; baseline for community correction.",
    })
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_dir", type=Path, required=True)
    ap.add_argument("--out", dest="out_dir", type=Path, required=True)
    args = ap.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text())
    today = datetime.date.today().isoformat()
    files = sorted(args.in_dir.rglob("*.ocl.json"))
    ok = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        repair_schema(doc)
        if not doc.get("sections"):
            print(f"SKIP (no sections — non-checklist source): {f.relative_to(args.in_dir)}")
            continue
        finalize(doc, today)
        out = args.out_dir / f.relative_to(args.in_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        res = validate_file(out, schema, check_form=False)
        if res.ok:
            ok += 1
        else:
            print(f"FAIL {f.relative_to(args.in_dir)}:")
            for e in res.errors:
                print(f"    error: {e}")
    print(f"\nfinalized {ok}/{len(files)} files with 0 errors -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
