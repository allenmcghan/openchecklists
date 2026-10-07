"""Analytics snippets added to every generated page at the end of the build.

Three layers, each off unless configured:

- Cloudflare Web Analytics is injected at the edge by Cloudflare (zone setting),
  so nothing is emitted here for it.
- Umami (our own, analytics.keylinkit.net): cookieless page views plus the few
  events that answer "is anyone using this?". `--umami-id` turns it on.
  `data-domains` limits counting to the production host, so local builds,
  previews and test runs never count.
- Microsoft Clarity (session replay / heatmaps): `--clarity-id` turns it on, in
  cookieless mode (consent denied by default), and never on pages where a pilot
  is working a checklist, signing in, or looking at their own data.

`oclTrack(name, data)` is always defined so page scripts can call it whether or
not any analytics is configured.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TRACK_HELPER = ("<script>window.oclTrack=function(n,d){try{if(window.umami&&umami.track)"
                "umami.track(n,d)}catch(e){}};</script>")

# Pages Clarity must never record: checklists in use, the editor, account and
# sign-in pages, and personal plan briefings.
CLARITY_EXCLUDE = re.compile(r"^(c/|checklist/|editor|profile|auth/|plan/|plan-detail)")


def snippet(rel_path: str, umami_id: str, umami_src: str, domain: str, clarity_id: str) -> str:
    parts = [TRACK_HELPER]
    if umami_id:
        parts.append(f'<script defer src="{umami_src}" data-website-id="{umami_id}" '
                     f'data-domains="{domain},www.{domain}"></script>')
    if clarity_id and not CLARITY_EXCLUDE.match(rel_path):
        cid = json.dumps(clarity_id)
        parts.append(
            "<script>(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};"
            "t=l.createElement(r);t.async=1;t.src='https://www.clarity.ms/tag/'+i;"
            "y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})"
            f"(window,document,'clarity','script',{cid});"
            "clarity('consentv2',{ad_Storage:'denied',analytics_Storage:'denied'});</script>")
    return "\n".join(parts) + "\n"


def inject(out: Path, umami_id: str, umami_src: str, domain: str, clarity_id: str) -> int:
    """Insert the snippet before </head> in every generated HTML page."""
    n = 0
    for page in out.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        if "window.oclTrack=" in html or "</head>" not in html:
            continue
        rel = page.relative_to(out).as_posix()
        html = html.replace("</head>", snippet(rel, umami_id, umami_src, domain, clarity_id) + "</head>", 1)
        page.write_text(html, encoding="utf-8")
        n += 1
    return n
