#!/usr/bin/env python3
"""Acquire public-domain source documents for the corpus.

    python3 tools/acquire.py discover "T-34 flight handbook"
    python3 tools/acquire.py fetch --all
    python3 tools/acquire.py fetch faa-afh-ch2

Two subcommands:

  discover  search the Internet Archive for candidate documents and print what
            was found, so a human can assess admissibility before anything is
            downloaded. It does not add anything to the manifest; that is a
            deliberate human decision, per the Stage 0 gate in docs/04-roadmap.md.

  fetch     download the documents listed in sources/public-domain.json, record
            a SHA-256 for each, and write a provenance sidecar. Re-running is
            idempotent and verifies the hash of anything already present.

The host allowlist is the sourcing policy from docs/05-product-and-sourcing.md
expressed as code. A source whose host is not on the list cannot be fetched by
this tool, and freechecklists.net is named in the denylist with its reason so that
nobody has to rediscover the terms. Encoding it here means the policy survives the
memory of the conversation that produced it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "sources" / "public-domain.json"
DOWNLOADS = REPO / "sources" / "documents"

# Hosts that publish US Government works or host public-domain scans. A host
# being here means "the tool may fetch from it", not "everything on it is public
# domain" -- the per-document rights basis in the manifest is still required.
ALLOWED_HOSTS = {
    "www.faa.gov",
    "faa.gov",
    "drs.faa.gov",
    "www.govinfo.gov",
    "govinfo.gov",
    "archive.org",
    "ia600000.us.archive.org",
    "apps.dtic.mil",
    "www.dtic.mil",
    "ntrs.nasa.gov",
    "www.ecfr.gov",
}

# Hosts this project must not harvest, with the reason, so the refusal is
# self-documenting rather than folklore.
DENIED_HOSTS = {
    "freechecklists.net": (
        "Site terms expressly forbid it: 'Copy the material from this page and put it on your "
        "web page. You do not have permission to do this.' Also forbids direct-linking files. "
        "Use it as an index only -- see docs/05-product-and-sourcing.md section 2."
    ),
    "www.freechecklists.net": ("See freechecklists.net."),
    "dauntless-soft.com": ("Operator of freechecklists.net; same terms apply."),
    "www.dauntless-soft.com": ("Operator of freechecklists.net; same terms apply."),
}

UA = "open-checklists-acquire/0.1 (public-domain corpus research; contact via project repository)"


def host_of(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def check_host(url: str) -> None:
    h = host_of(url)
    if h in DENIED_HOSTS:
        raise SystemExit(f"refusing {url}\n  {h}: {DENIED_HOSTS[h]}")
    if h not in ALLOWED_HOSTS:
        raise SystemExit(
            f"refusing {url}\n  host {h!r} is not on the allowlist. If it publishes US "
            "Government works or hosts public-domain scans, add it to ALLOWED_HOSTS with a "
            "note on why, and record the per-document rights basis in the manifest."
        )


def get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def cmd_discover(args: argparse.Namespace) -> int:
    """Search the Internet Archive. Printing only -- no downloads, no manifest edits."""
    params = [
        ("q", f"{args.query} AND mediatype:texts"),
        ("rows", str(args.rows)),
        ("output", "json"),
    ]
    # doseq-style repeated fl[] keys; urlencode with a dict would drop all but one.
    for field in ("identifier", "title", "year", "licenseurl"):
        params.append(("fl[]", field))
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params)

    data = json.loads(get(url, timeout=60))["response"]
    print(f"{data['numFound']} result(s) for {args.query!r}\n")
    for d in data["docs"]:
        ident = d.get("identifier")
        print(f"  {ident}")
        print(f"      title: {str(d.get('title'))[:100]}")
        if d.get("year"):
            print(f"      year:  {d['year']}")
        print(f"      files: https://archive.org/metadata/{ident}")
    if data["docs"]:
        print(
            "\nNothing was downloaded. Assess each candidate for admissibility "
            "(is it a US Government work? contractor-authored? a simulator product?), "
            "then add it to sources/public-domain.json with its rights basis."
        )
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    manifest = json.loads(MANIFEST.read_text())
    docs = manifest["documents"]
    if not args.all:
        wanted = set(args.ids)
        unknown = wanted - {d["id"] for d in docs}
        if unknown:
            raise SystemExit(f"unknown id(s): {', '.join(sorted(unknown))}")
        docs = [d for d in docs if d["id"] in wanted]
    if not docs:
        raise SystemExit("nothing selected; pass ids or --all")

    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    failures = 0

    for d in docs:
        did = d["id"]
        for asset in d["assets"]:
            url = asset["url"]
            check_host(url)
            dest = DOWNLOADS / did / asset["filename"]
            dest.parent.mkdir(parents=True, exist_ok=True)

            if dest.exists():
                actual = sha256(dest.read_bytes())
                if asset.get("sha256") and actual != asset["sha256"]:
                    print(f"[MISMATCH] {did}/{asset['filename']}")
                    print(f"    expected {asset['sha256']}")
                    print(f"    actual   {actual}")
                    failures += 1
                else:
                    print(f"[cached]   {did}/{asset['filename']} ({actual[:12]}…)")
                continue

            try:
                blob = get(url)
            except Exception as exc:  # network, 404, timeout
                print(f"[FAIL]     {did}/{asset['filename']}: {exc}")
                failures += 1
                continue

            digest = sha256(blob)
            if asset.get("sha256") and digest != asset["sha256"]:
                print(f"[MISMATCH] {did}/{asset['filename']} got {digest}")
                failures += 1
                continue

            dest.write_bytes(blob)
            print(f"[fetched]  {did}/{asset['filename']} {len(blob):,}B {digest[:12]}…")
            if not asset.get("sha256"):
                print(f"    record sha256: {digest}")

        # Provenance sidecar: everything a transcriber needs to fill in a
        # provenance block without going back to the manifest.
        side = DOWNLOADS / did / "provenance.json"
        side.write_text(
            json.dumps(
                {
                    "source": d["source"],
                    "rights": d["rights"],
                    "acquired_from": [a["url"] for a in d["assets"]],
                    "notes": d.get("notes", ""),
                },
                indent=2,
            )
            + "\n"
        )

    print(f"\n{len(docs)} document(s) processed, {failures} problem(s)")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="search the Internet Archive for candidates")
    d.add_argument("query")
    d.add_argument("--rows", type=int, default=15)
    d.set_defaults(func=cmd_discover)

    f = sub.add_parser("fetch", help="download documents listed in the manifest")
    f.add_argument("ids", nargs="*")
    f.add_argument("--all", action="store_true")
    f.set_defaults(func=cmd_fetch)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
