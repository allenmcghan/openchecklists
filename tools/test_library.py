#!/usr/bin/env python3
"""Prove the library's admissibility gate and passage bookkeeping hold.

    python3 tools/test_library.py

Three properties matter here and none of them is visible by reading a search result:

1. **The admissibility gate rejects rather than flags.** A document that is not
   public domain, or that is a simulator product, must not reach the index at all.
   A perfect index over the wrong document is the failure mode from
   docs/05-product-and-sourcing.md, and it looks identical to a correct one.

2. **One directory is one document.** A document directory can hold more than one
   rendering of the same document -- the T-34A has both the scan and an OCR text
   layer. Treating them as two documents silently double-counts the content and
   breaks property 3.

3. **Each document's passage ids are contiguous.** The per-document search filter
   is a range test on the passage id, so a gap or an overlap would make one
   document's results appear under another's name -- a citation pointing at a
   document the text is not in, which is worse than no result.

Extraction is stubbed. The unit under test is ingest's bookkeeping, not pymupdf,
and stubbing keeps this runnable without a 250 MB corpus on disk.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import library  # noqa: E402

PARA = (
    "This paragraph is comfortably longer than the sixty character minimum that "
    "split_passages enforces, so it survives into the index as a passage."
)
OTHER = (
    "A second distinct paragraph, also long enough to be kept, so that a document "
    "can hold more than one passage and ranges have something to cover."
)
ONLY_OCR = (
    "A paragraph present only in the OCR text layer, which is the whole reason for "
    "indexing both renderings of a scanned document rather than picking one."
)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}{': ' + detail if detail else ''}")
        failures.append(name)


def write_doc(root: Path, doc_id: str, assets: dict[str, list[str]], prov: dict) -> list[Path]:
    """Create a document directory with a provenance sidecar and stub assets."""
    d = root / doc_id
    d.mkdir(parents=True)
    (d / "provenance.json").write_text(json.dumps(prov))
    paths = []
    for name, pages in assets.items():
        (d / name).write_text("stub")
        library_pages[(doc_id, name)] = pages
        paths.append(d / name)
    return paths


PD = {
    "source": {"kind": "government_publication", "title": "Admissible Handbook"},
    "rights": {"status": "public_domain", "public_domain_basis": "us_government_work"},
}
RESERVED = {
    "source": {"kind": "manufacturer_publication", "title": "Reserved Manual"},
    "rights": {"status": "upstream_reserved"},
}
SIM = {
    "source": {"kind": "simulator_product", "title": "Add-on Aircraft Manual"},
    "rights": {"status": "public_domain", "public_domain_basis": "us_government_work"},
}
NO_RIGHTS = {"source": {"title": "Unknown Provenance"}}

# (doc_id, filename) -> list of page texts, consulted by the extraction stub.
library_pages: dict[tuple[str, str], list[str]] = {}


def stub_extract(path: Path) -> list[tuple[int, str]]:
    pages = library_pages.get((path.parent.name, path.name), [])
    return [(i, t) for i, t in enumerate(pages, start=1) if t.strip()]


def main() -> int:
    library.extract_pdf = stub_extract

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "documents"
        out = Path(tmp) / "index"

        # One paragraph per page, because split_passages deliberately merges short
        # paragraphs up to 900 characters -- two paragraphs on one page would arrive
        # as a single passage and this test would be measuring the wrong thing.
        paths: list[Path] = []
        # Two renderings of one document, sharing a paragraph. This is the T-34A case.
        paths += write_doc(
            root, "two-assets",
            {"scan.pdf": [PARA, OTHER], "ocr.txt": [PARA, ONLY_OCR]},
            PD,
        )
        # A second admissible document that repeats the first document's paragraph.
        paths += write_doc(root, "second", {"a.pdf": [PARA, OTHER]}, PD)
        # Inadmissible: rights reserved.
        paths += write_doc(root, "reserved", {"a.pdf": [PARA]}, RESERVED)
        # Inadmissible: simulator product, even though its rights field says PD.
        paths += write_doc(root, "sim", {"a.pdf": [PARA]}, SIM)
        # Inadmissible: no rights recorded at all.
        paths += write_doc(root, "unknown", {"a.pdf": [PARA]}, NO_RIGHTS)
        # Admissible but yields no text: must be reported, not silently absent.
        paths += write_doc(root, "empty", {"a.pdf": ["", "   "]}, PD)

        meta = library.ingest(paths, out)
        docs = meta["documents"]
        rejected = " ".join(meta["rejected"])

        print("admissibility gate")
        check("rights reserved is not indexed", "reserved" not in docs)
        check("rights reserved is reported", "reserved" in rejected)
        check("simulator product is not indexed", "sim" not in docs)
        check("simulator product is reported", "sim" in rejected)
        check("missing rights is not indexed", "unknown" not in docs)
        check("no-text document is not indexed", "empty" not in docs)
        check("no-text document is reported as needing OCR", "needs OCR" in rejected)
        check("admissible documents are indexed", set(docs) == {"two-assets", "second"},
              f"got {sorted(docs)}")

        print("one directory is one document")
        check("two assets collapse into one document", len(docs) == 2, f"got {len(docs)}")
        check("both assets are recorded", docs["two-assets"]["assets"] == ["ocr.txt", "scan.pdf"],
              f"got {docs['two-assets'].get('assets')}")
        # Two renderings of two pages each: the sum would be 4, the document is 2.
        check("page count is the longest rendering, not the sum",
              docs["two-assets"]["pages"] == 2, f"got {docs['two-assets']['pages']}")

        print("deduplication")
        check("a paragraph repeated within a document is indexed once",
              docs["two-assets"]["passages"] == 3, f"got {docs['two-assets']['passages']}")
        check("the same paragraph in another document is kept",
              docs["second"]["passages"] == 2, f"got {docs['second']['passages']}")

        print("passage id ranges")
        spans = sorted((d["first"], d["last"], k) for k, d in docs.items())
        prev = -1
        contiguous = True
        for lo, hi, _k in spans:
            if lo != prev + 1:
                contiguous = False
            prev = hi
        check("ranges are contiguous from zero", contiguous, f"spans {spans}")
        check("ranges end at the last passage", prev == meta["counts"]["passages"] - 1,
              f"last id {prev}, total {meta['counts']['passages']}")
        check("each range length matches the document's passage count",
              all(d["last"] - d["first"] + 1 == d["passages"] for d in docs.values()))
        check("counts sum to the total",
              sum(d["passages"] for d in docs.values()) == meta["counts"]["passages"])

        # The property the browser filter actually relies on: every passage inside a
        # document's span belongs to that document.
        bucket = meta["passage_bucket"]
        store: list[dict] = []
        for start in range(0, meta["counts"]["passages"], bucket):
            store.extend(json.loads((out / "passages" / f"{start // bucket}.json").read_text()))
        misfiled = sum(
            1 for lo, hi, k in spans for i in range(lo, hi + 1) if store[i]["d"] != k
        )
        check("every passage falls inside its own document's span", misfiled == 0,
              f"{misfiled} misfiled")

        # Postings must only reference passages that exist, or the browser fetches a
        # bucket and finds nothing there.
        max_id = -1
        for shard in (out / "postings").glob("*.json"):
            for entry in json.loads(shard.read_text()).values():
                for pid, _tf in entry["p"]:
                    max_id = max(max_id, pid)
        check("no posting references a passage past the end of the store",
              max_id == meta["counts"]["passages"] - 1, f"max posting id {max_id}")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all library checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
