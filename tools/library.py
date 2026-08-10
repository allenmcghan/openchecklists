#!/usr/bin/env python3
"""Build a searchable full-text library from public-domain aviation documents.

    python3 tools/library.py ingest sources/documents/*/*.pdf
    python3 tools/library.py search "carburettor icing"
    python3 tools/library.py index-registry

This is the retrieval engine behind the troubleshooting search. Two deliberate
decisions shape it, and both come from the same place as the rest of the project.

**It cites, it does not diagnose.** Every result is a passage with a document, a
revision and a page number. It will tell you that AC 43.13-1B paragraph 8-31 covers
ignition harness inspection; it will not tell you your engine's problem is the
harness. A generated answer would be the only thing on this site with no
provenance, and "your problem is probably X" is exactly the claim that hurts
somebody when it is wrong. Retrieval with citations is more useful anyway, because
it hands over the actual text rather than a paraphrase of it.

If an LLM is added later, this is the correct substrate for it: retrieve first, then
let the model summarise *these passages with these citations*, never answer from
memory. The index is what makes that safe.

**Only admissible sources go in.** A manufacturer's maintenance manual is a
commercial product and full-text hosting it is wholesale reproduction, which is a
different question from transcribing checklist facts. So the library holds
public-domain documents, and for everything else it holds a *registry* — what the
document is, its part number, and where to get it. Facts about which documents exist
are not protected; the documents are.

Index format is plain JSON: an inverted index over stemmed terms plus a passage
store, sharded so a browser can fetch only what a query needs.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "library"

# Words carrying no discriminating power in a corpus that is entirely about
# aircraft. "aircraft" itself is nearly a stop word here.
STOP = set("""
a an and are as at be been but by can could do does for from had has have if in into is it
its may must not of on or shall should so such than that the their then there these they this
those to up was were what when which who will with would you your
""".split())

TOKEN = re.compile(r"[a-z][a-z0-9\-/]{1,}")

# Minimal suffix stripping. A real stemmer is overkill and mangles part numbers,
# which matter more here than recall on plurals.
def stem(w: str) -> str:
    for suf in ("ings", "ing", "ies", "ers", "er", "ed", "es", "s"):
        if len(w) > 4 + len(suf) - 1 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 2]


def extract_pdf(path: Path) -> list[tuple[int, str]]:
    try:
        import pymupdf
    except ImportError:
        raise SystemExit("pymupdf is required to ingest PDFs: pip install pymupdf")
    doc = pymupdf.open(path)
    out = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            out.append((i, text))
    return out


def split_passages(page_text: str, max_chars: int = 900) -> list[str]:
    """Split a page into passages on paragraph boundaries.

    Passage-level retrieval beats page-level: a page of AC 43.13 covers several
    unrelated topics, and returning the whole page makes the reader hunt.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
    out: list[str] = []
    buf = ""
    for p in paras:
        p = re.sub(r"[ \t]+", " ", p)
        if len(buf) + len(p) + 1 <= max_chars:
            buf = f"{buf}\n{p}".strip()
        else:
            if buf:
                out.append(buf)
            while len(p) > max_chars:
                cut = p.rfind(". ", 0, max_chars)
                cut = cut + 1 if cut > max_chars // 2 else max_chars
                out.append(p[:cut].strip())
                p = p[cut:].strip()
            buf = p
    if buf:
        out.append(buf)
    return [o for o in out if len(o) > 60]


def load_provenance(pdf: Path) -> dict:
    """Read the provenance sidecar tools/acquire.py wrote beside the document."""
    side = pdf.parent / "provenance.json"
    if side.exists():
        try:
            return json.loads(side.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def ingest(paths: list[Path], out: Path) -> dict:
    docs: dict[str, dict] = {}
    passages: list[dict] = []
    rejected: list[str] = []

    # Group assets by document before extracting anything. A document directory can
    # hold more than one file -- the T-34A has both the scan and an OCR text layer of
    # the same handbook -- and processing them as independent documents both
    # double-counts the content and leaves each document's passage ids
    # non-contiguous, which the per-document search filter depends on.
    by_doc: dict[str, list[Path]] = {}
    for p in paths:
        by_doc.setdefault(p.parent.name, []).append(p)

    for doc_id in sorted(by_doc):
        assets = sorted(by_doc[doc_id])
        prov = load_provenance(assets[0])
        src = prov.get("source", {})
        rights = prov.get("rights", {})

        # Admissibility gate, same rule as the checklist corpus: only publish what
        # the project has the right to publish.
        if rights.get("status") != "public_domain":
            rejected.append(
                f"{doc_id}: rights.status is {rights.get('status') or 'unknown'!r}, not "
                "public_domain — full text will not be indexed. Add it to the registry instead."
            )
            continue
        if src.get("kind") == "simulator_product":
            rejected.append(f"{doc_id}: simulator product, inadmissible")
            continue

        n_before = len(passages)
        # Assets are renderings of one document, so the page count is the longest
        # rendering, not their sum -- adding them would claim the T-34A handbook is
        # twice as long as it is.
        n_pages = 0
        # Two renderings of one document overlap heavily, so deduplicate within the
        # document. Across documents a repeated paragraph is a real second citation
        # and is kept.
        seen: set[str] = set()
        indexed: list[str] = []
        for asset in assets:
            pages = extract_pdf(asset)
            if not pages:
                rejected.append(
                    f"{doc_id}/{asset.name}: no extractable text — needs OCR before indexing"
                )
                continue
            indexed.append(asset.name)
            n_pages = max(n_pages, len(pages))
            for page_no, text in pages:
                for para in split_passages(text):
                    key = re.sub(r"\s+", " ", para).strip().lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    passages.append({
                        "d": doc_id,
                        "p": page_no,
                        "t": para,
                    })

        if not indexed:
            continue

        docs[doc_id] = {
            "id": doc_id,
            "title": src.get("title") or doc_id,
            "publisher": src.get("publisher"),
            "document_number": src.get("document_number"),
            "revision": src.get("revision"),
            "url": src.get("url"),
            "rights": rights.get("status"),
            "basis": rights.get("public_domain_basis"),
            "pages": n_pages,
            "passages": len(passages) - n_before,
            # Passage ids are contiguous per document, so the browser can limit a
            # search to one document with a range test and no extra fetches.
            "first": n_before,
            "last": len(passages) - 1,
            "assets": indexed,
        }

    # Inverted index with BM25-ish scoring precomputed where it can be.
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    lengths: list[int] = []
    for i, ps in enumerate(passages):
        terms = Counter(tokenize(ps["t"]))
        lengths.append(sum(terms.values()) or 1)
        for term, tf in terms.items():
            postings[term].append((i, tf))

    n = len(passages) or 1
    avg_len = sum(lengths) / n if lengths else 1.0
    idf = {t: math.log(1 + (n - len(pl) + 0.5) / (len(pl) + 0.5)) for t, pl in postings.items()}

    out.mkdir(parents=True, exist_ok=True)
    (out / "postings").mkdir(exist_ok=True)

    # Shard postings by first letter so a query fetches only what it needs.
    shards: dict[str, dict] = defaultdict(dict)
    for term, pl in postings.items():
        key = term[0] if term[0].isalnum() else "_"
        shards[key][term] = {"i": round(idf[term], 4), "p": pl}
    for key, group in shards.items():
        (out / "postings" / f"{key}.json").write_text(
            json.dumps(group, separators=(",", ":"), ensure_ascii=False)
        )

    # Shard passages in fixed-size buckets. A query resolves to a handful of
    # passage ids, so the browser fetches two or three buckets rather than the
    # whole 4 MB store.
    (out / "passages").mkdir(exist_ok=True)
    BUCKET = 500
    for start in range(0, max(len(passages), 1), BUCKET):
        (out / "passages" / f"{start // BUCKET}.json").write_text(
            json.dumps(passages[start:start + BUCKET], separators=(",", ":"), ensure_ascii=False)
        )
    meta = {
        "documents": docs,
        "counts": {
            "documents": len(docs),
            "passages": len(passages),
            "terms": len(postings),
            "shards": len(shards),
        },
        "scoring": {"avg_passage_length": round(avg_len, 2), "k1": 1.2, "b": 0.75},
        "passage_bucket": BUCKET,
        "rejected": rejected,
        "notice": (
            "Full text of public-domain documents only. Results are passages with a "
            "document and page citation. Nothing here diagnoses a problem; it shows you "
            "what the source says so you can read it yourself."
        ),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return meta


def search(query: str, out: Path, limit: int = 8) -> int:
    meta_p = out / "meta.json"
    if not meta_p.exists():
        raise SystemExit("no library indexed yet; run: library.py ingest <pdfs>")
    meta = json.loads(meta_p.read_text())
    bucket = meta.get("passage_bucket", 500)
    passages: dict[int, dict] = {}
    for f in sorted((out / "passages").glob("*.json")):
        base = int(f.stem) * bucket
        for off, ps in enumerate(json.loads(f.read_text())):
            passages[base + off] = ps
    avg_len = meta["scoring"]["avg_passage_length"]
    k1, b = meta["scoring"]["k1"], meta["scoring"]["b"]

    terms = tokenize(query)
    if not terms:
        print("no searchable terms in that query")
        return 1

    loaded: dict[str, dict] = {}
    scores: dict[int, float] = defaultdict(float)
    for t in terms:
        key = t[0] if t[0].isalnum() else "_"
        if key not in loaded:
            f = out / "postings" / f"{key}.json"
            loaded[key] = json.loads(f.read_text()) if f.exists() else {}
        entry = loaded[key].get(t)
        if not entry:
            continue
        for i, tf in entry["p"]:
            dl = len(tokenize(passages[i]["t"])) or 1
            scores[i] += entry["i"] * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_len))

    if not scores:
        print(f"nothing found for {query!r}")
        return 1

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    print(f"{len(scores)} passage(s) matched {query!r}; top {len(ranked)}:\n")
    for i, sc in ranked:
        ps = passages[i]
        d = meta["documents"].get(ps["d"], {})
        cite = " ".join(filter(None, [d.get("document_number"), d.get("revision")]))
        print(f"  [{sc:.2f}] {d.get('title', ps['d'])} — page {ps['p']}"
              + (f"  ({cite})" if cite else ""))
        text = re.sub(r"\s+", " ", ps["t"])
        print(f"        {text[:320]}{'…' if len(text) > 320 else ''}\n")
    print("  Citations, not advice. Read the source before acting on it.")
    return 0


# Documents the project must not host but should help people find. Facts about
# which documents exist are not protected; the documents are.
REGISTRY = [
    {"category": "engine", "make": "Lycoming", "applies_to": "O-320 series",
     "title": "Operator's Manual", "document_number": "60297-30",
     "availability": "purchase", "publisher": "Lycoming Engines",
     "url": "https://www.lycoming.com/contact/knowledge-base/publications"},
    {"category": "engine", "make": "Lycoming", "applies_to": "all",
     "title": "Service Instructions, Bulletins and Letters", "document_number": "various",
     "availability": "free_registration", "publisher": "Lycoming Engines",
     "url": "https://www.lycoming.com/contact/knowledge-base/publications"},
    {"category": "engine", "make": "Continental", "applies_to": "O-470 / IO-520 series",
     "title": "Operator's and Maintenance Manuals", "document_number": "various",
     "availability": "purchase", "publisher": "Continental Aerospace Technologies",
     "url": "https://www.continental.aero/support/manuals.aspx"},
    {"category": "engine", "make": "Rotax", "applies_to": "912 / 914 series",
     "title": "Operators, Maintenance and Installation Manuals", "document_number": "various",
     "availability": "free_download", "publisher": "BRP-Rotax",
     "url": "https://www.flyrotax.com/services/technical-documentation",
     "notes": "Rotax publishes these without charge. Check their terms before "
              "redistributing anything; linking is always safe."},
    {"category": "engine", "make": "Jabiru", "applies_to": "2200 / 3300",
     "title": "Engine Manuals", "document_number": "various",
     "availability": "free_download", "publisher": "Jabiru Aircraft",
     "url": "https://jabiru.net.au/service-and-technical/"},
    {"category": "airframe", "make": "Textron / Cessna", "applies_to": "single-engine piston",
     "title": "POH / AFM and maintenance manuals", "document_number": "various",
     "availability": "purchase", "publisher": "Textron Aviation",
     "url": "https://www.txtav.com/en/service/publications"},
    {"category": "airframe", "make": "Piper", "applies_to": "all",
     "title": "POH / AFM and service manuals", "document_number": "various",
     "availability": "purchase", "publisher": "Piper Aircraft",
     "url": "https://www.piper.com/technical-publications/"},
    {"category": "airframe", "make": "Cirrus", "applies_to": "SR20 / SR22",
     "title": "POH / AFM", "document_number": "various",
     "availability": "free_download", "publisher": "Cirrus Aircraft",
     "url": "https://servicecenters.cirrusaircraft.com/tech-pubs",
     "notes": "Cirrus publishes current POHs openly."},
    {"category": "propeller", "make": "Hartzell", "applies_to": "all",
     "title": "Owner's Manuals and Service Bulletins", "document_number": "various",
     "availability": "free_download", "publisher": "Hartzell Propeller",
     "url": "https://hartzellprop.com/technical-publications/"},
    {"category": "propeller", "make": "Sensenich", "applies_to": "all",
     "title": "Owner's Manuals", "document_number": "various",
     "availability": "free_download", "publisher": "Sensenich",
     "url": "https://sensenich.com/"},
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest"); i.add_argument("pdfs", nargs="+", type=Path)
    i.add_argument("-o", "--out", type=Path, default=OUT)
    s = sub.add_parser("search"); s.add_argument("query")
    s.add_argument("-o", "--out", type=Path, default=OUT)
    s.add_argument("-n", type=int, default=8)
    r = sub.add_parser("index-registry"); r.add_argument("-o", "--out", type=Path, default=OUT)
    args = ap.parse_args()

    if args.cmd == "ingest":
        meta = ingest(args.pdfs, args.out)
        print(json.dumps({k: meta[k] for k in ("counts", "rejected")}, indent=2))
        for d in meta["documents"].values():
            print(f"  {d['id']}: {d['pages']} pages, {d['passages']} passages — {d['title']}")
        return 0
    if args.cmd == "index-registry":
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "registry.json").write_text(
            json.dumps({
                "notice": ("Where to obtain documents this project cannot host. Listing what "
                           "exists is not reproduction."),
                "documents": REGISTRY,
            }, indent=2) + "\n"
        )
        print(f"wrote registry: {len(REGISTRY)} entries")
        return 0
    return search(args.query, args.out, args.n)


if __name__ == "__main__":
    sys.exit(main())
