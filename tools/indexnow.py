#!/usr/bin/env python3
"""Submit the site's URLs to IndexNow (Bing, Yandex, Seznam, Naver and others).

    python3 tools/indexnow.py            # every URL in the built sitemaps
    python3 tools/indexnow.py URL ...    # just these

IndexNow verifies ownership by fetching https://<host>/<KEY>.txt, which the build
writes (the key is public by design). Google does not take IndexNow; it needs
Search Console. Run after a deploy that adds or changes pages.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

KEY = "91ea0958f9e384b32519a73b16625236"
HOST = "openchecklists.net"
SITE = Path(__file__).resolve().parent.parent / "build" / "site"
BATCH = 10_000  # IndexNow's per-request maximum


def sitemap_urls() -> list[str]:
    urls: list[str] = []
    for f in sorted(SITE.glob("sitemap-*.xml")):
        urls += re.findall(r"<loc>([^<]+)</loc>", f.read_text())
    return urls


def submit(urls: list[str]) -> None:
    for i in range(0, len(urls), BATCH):
        body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt",
                           "urlList": urls[i:i + BATCH]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"batch {i // BATCH + 1}: {len(urls[i:i + BATCH])} urls -> HTTP {r.status}")
        except urllib.error.HTTPError as e:
            print(f"batch {i // BATCH + 1}: HTTP {e.code} {e.read()[:200]!r}")


if __name__ == "__main__":
    submit(sys.argv[1:] or sitemap_urls())
