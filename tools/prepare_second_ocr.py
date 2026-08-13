#!/usr/bin/env python3
"""Stage the 'needs_ocr' files for the second OCR pass.

Reads convert-manifest.jsonl and copies/extracts every file flagged
`needs_ocr` (zip-contained images + PDFs, top-level .jpg, the trailing-space
PDF) into a flat staging tree that can be tar'd and uploaded to KITDEV003.

Staging layout mirrors checklists/:
    ocr-stage2/<Mfr>/<Model>/<file>                     (top-level files)
    ocr-stage2/<Mfr>/<Model>/<zipname>/<inner-path>     (zip contents)

Also writes ocr-stage2/manifest.jsonl — one line per staged file with the
source provenance (which zip it came from, or "top-level").

Usage:
    python3 tools/prepare_second_ocr.py [--archive PATH] [--staging PATH]
"""
import argparse
import json
import shutil
import zipfile
from pathlib import Path

ARCHIVE = Path("/home/node/workspace/openchecklists/freechecklists-archive")
CHECKLISTS = ARCHIVE / "checklists"
MANIFEST = ARCHIVE / "convert-manifest.jsonl"
STAGING = ARCHIVE / "ocr-stage2"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path, default=ARCHIVE)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--staging", type=Path, default=STAGING)
    args = ap.parse_args()

    checklists = args.archive / "checklists"
    if args.staging.exists():
        shutil.rmtree(args.staging)
    args.staging.mkdir(parents=True, exist_ok=True)

    # Dedupe: convert-manifest.jsonl is append-only, so re-runs repeat entries.
    needs = {}
    for line in args.manifest.read_text().splitlines():
        e = json.loads(line)
        if e.get("status") == "needs_ocr":
            needs[e["file"]] = e

    staged = 0
    missing = 0
    out = []
    for f, e in sorted(needs.items()):
        kind = e.get("type")
        if "::" in f:
            zip_rel, inner = f.split("::", 1)
            zip_path = checklists / zip_rel
            dest = args.staging / zip_rel.removesuffix(".zip") / inner
            if not zip_path.exists():
                missing += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path) as zf, zf.open(inner) as src_f, open(dest, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)
                staged += 1
                out.append({"file": str(dest.relative_to(args.staging)), "type": kind,
                            "source_zip": zip_rel, "inner": inner})
            except Exception as exc:
                print(f"ERROR extracting {zip_rel}::{inner}: {exc}")
        else:
            src = checklists / f
            dest = args.staging / f
            if not src.exists():
                missing += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            staged += 1
            out.append({"file": f, "type": kind, "source": "top-level"})

    manifest_out = args.staging / "manifest.jsonl"
    manifest_out.write_text("\n".join(json.dumps(x) for x in out) + "\n", encoding="utf-8")

    n_img = sum(1 for x in out if x["type"] == "image")
    n_pdf = sum(1 for x in out if x["type"] == "pdf")
    print(f"staged {staged} files ({n_img} images, {n_pdf} pdfs), {missing} missing")
    print(f"manifest: {manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
