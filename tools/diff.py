#!/usr/bin/env python3
"""Semantic diff between two checklists.

    python3 tools/diff.py examples/aerolite-103-hirth-f33.ocl.json \
                          examples/aerolite-103-kawasaki-340-n512jm.ocl.json

    python3 tools/diff.py --fork examples/aerolite-103-kawasaki-340-n512jm.ocl.json

This is the payoff for recording lineage. Somebody with the same airframe and a
different engine does not want to read two checklists side by side and spot the
differences; they want to be told what the other builder changed and why. That is
what this prints.

Deliberately not a text diff. A JSON diff of two checklists is dominated by
reordering and whitespace, and buries the one line where a response changed from
2,000 to 2,400 RPM. This matches sections by id and items by id or text, then
sorts the findings so the safety-relevant ones come first:

    1. warnings and cautions added or removed
    2. memory items added or removed
    3. responses changed (the values you set a control to)
    4. everything else

Use --markdown to emit the same thing for the site.
"""

from __future__ import annotations

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import content_hash  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

INFO = {"note", "caution", "warning"}


def item_key(it: dict, idx: int) -> str:
    """Stable-ish identity for matching an item across two files."""
    if it.get("id"):
        return f"id:{it['id']}"
    text = (it.get("text") or "").strip().casefold()
    return f"text:{text}" if text else f"pos:{idx}"


def sections_of(doc: dict) -> dict[str, dict]:
    out = {}
    for i, s in enumerate(doc.get("sections", [])):
        out[s.get("id") or f"__pos{i}"] = s
    return out


def describe(it: dict) -> str:
    t = it.get("type", "")
    if t in INFO:
        return f"{t.upper()}: {it.get('text', '')}"
    if t == "subtitle":
        return f"[{it.get('text', '')}]"
    resp = f" -> {it['response']}" if it.get("response") else ""
    mem = " [MEMORY]" if it.get("memory_item") else ""
    return f"{it.get('text', '')}{resp}{mem}"


class Finding:
    __slots__ = ("rank", "kind", "where", "text")

    def __init__(self, rank: int, kind: str, where: str, text: str):
        self.rank, self.kind, self.where, self.text = rank, kind, where, text


def rank_for(it: dict, changed_response: bool = False) -> int:
    if it.get("type") in ("warning", "caution"):
        return 0
    if it.get("memory_item"):
        return 1
    if changed_response:
        return 2
    return 3


def diff_items(a_items: list[dict], b_items: list[dict], sec: str) -> list[Finding]:
    out: list[Finding] = []
    a_map = {item_key(it, i): it for i, it in enumerate(a_items)}
    b_map = {item_key(it, i): it for i, it in enumerate(b_items)}

    for k, it in b_map.items():
        if k not in a_map:
            out.append(Finding(rank_for(it), "added", sec, describe(it)))
    for k, it in a_map.items():
        if k not in b_map:
            out.append(Finding(rank_for(it), "removed", sec, describe(it)))

    for k in a_map.keys() & b_map.keys():
        a, b = a_map[k], b_map[k]
        label = a.get("text") or b.get("text") or k
        if a.get("response") != b.get("response"):
            out.append(
                Finding(
                    rank_for(b, changed_response=True),
                    "response",
                    sec,
                    f"{label}: {a.get('response') or '(none)'}  ->  {b.get('response') or '(none)'}",
                )
            )
        if a.get("type") != b.get("type"):
            out.append(Finding(rank_for(b), "type", sec, f"{label}: {a.get('type')} -> {b.get('type')}"))
        if bool(a.get("memory_item")) != bool(b.get("memory_item")):
            became = "now a memory item" if b.get("memory_item") else "no longer a memory item"
            out.append(Finding(1, "memory", sec, f"{label}: {became}"))
        if (a.get("text") or "") != (b.get("text") or ""):
            ratio = SequenceMatcher(None, a.get("text") or "", b.get("text") or "").ratio()
            if ratio < 0.999:
                out.append(
                    Finding(rank_for(b), "text", sec, f"{a.get('text')!r}  ->  {b.get('text')!r}")
                )
        if (a.get("detail") or "") != (b.get("detail") or ""):
            out.append(Finding(3, "detail", sec, f"{label}: explanatory detail changed"))
    return out


def diff(a: dict, b: dict) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    notes: list[str] = []

    a_secs, b_secs = sections_of(a), sections_of(b)
    for sid in b_secs.keys() - a_secs.keys():
        s = b_secs[sid]
        n = len(s.get("items", []))
        findings.append(Finding(0 if s.get("criticality") != "normal" else 3, "section-added", sid, f"{s.get('title')} ({n} items)"))
    for sid in a_secs.keys() - b_secs.keys():
        s = a_secs[sid]
        findings.append(Finding(0, "section-removed", sid, f"{s.get('title')} ({len(s.get('items', []))} items)"))

    for sid in a_secs.keys() & b_secs.keys():
        sa, sb = a_secs[sid], b_secs[sid]
        findings += diff_items(sa.get("items", []), sb.get("items", []), sid)
        if sa.get("title") != sb.get("title"):
            notes.append(f"section {sid}: title {sa.get('title')!r} -> {sb.get('title')!r}")
        if sa.get("criticality", "normal") != sb.get("criticality", "normal"):
            findings.append(
                Finding(0, "criticality", sid, f"{sa.get('criticality', 'normal')} -> {sb.get('criticality', 'normal')}")
            )

    # Configuration differences are the reason a fork exists, so surface them.
    aa, ba = a.get("aircraft", {}), b.get("aircraft", {})
    for label, ka in (("make", "make"), ("model", "model"), ("variant", "variant"), ("propeller", "propeller"), ("gear", "gear")):
        if aa.get(ka) != ba.get(ka):
            notes.append(f"aircraft.{label}: {aa.get(ka)} -> {ba.get(ka)}")
    ea = [f"{e.get('make')} {e.get('model')}" for e in aa.get("engine", [])]
    eb = [f"{e.get('make')} {e.get('model')}" for e in ba.get("engine", [])]
    if ea != eb:
        notes.append(f"engine: {', '.join(ea) or '(none)'} -> {', '.join(eb) or '(none)'}")

    return findings, notes


ORDER = ["warnings and cautions", "memory items", "responses (control settings)", "other changes"]


def group(findings: list[Finding]) -> dict[int, list[Finding]]:
    out: dict[int, list[Finding]] = {0: [], 1: [], 2: [], 3: []}
    for f in findings:
        out[f.rank].append(f)
    return out


def render_text(a: dict, b: dict, findings: list[Finding], notes: list[str]) -> str:
    L = [
        f"{a['id']}  ->  {b['id']}",
        f"  {a.get('title')}",
        f"  {b.get('title')}",
        "",
    ]
    d = b.get("derived_from")
    if d and d.get("checklist_id") == a["id"]:
        L.append("This is a recorded fork of the first file.")
        if d.get("content_hash") and d["content_hash"] != content_hash(a):
            L.append("  NOTE: the parent has changed since the fork was taken.")
        if d.get("changes_summary"):
            L += ["", "  What the author says changed:", ""]
            L += [f"    {ln}" for ln in _wrap(d["changes_summary"], 76)]
        L.append("")

    mods = b.get("aircraft", {}).get("modifications", [])
    if mods:
        L.append("Modifications recorded on the second aircraft:")
        for m in mods:
            flag = " (affects procedures)" if m.get("affects_procedures") else ""
            L.append(f"  - {m['kind']}{flag}: {m['description']}")
        L.append("")

    if notes:
        L.append("Configuration and titles:")
        L += [f"  - {n}" for n in notes]
        L.append("")

    g = group(findings)
    total = sum(len(v) for v in g.values())
    if not total:
        L.append("No procedural differences found.")
        return "\n".join(L) + "\n"

    L.append(f"{total} procedural difference(s), most safety-relevant first:")
    for rank, heading in enumerate(ORDER):
        if not g[rank]:
            continue
        L += ["", f"  {heading.upper()}"]
        for f in sorted(g[rank], key=lambda x: (x.where, x.kind)):
            L.append(f"    [{f.kind}] {f.where}: {f.text}")
    return "\n".join(L) + "\n"


def _wrap(s: str, w: int) -> list[str]:
    words, line, out = s.split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > w:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def render_markdown(a: dict, b: dict, findings: list[Finding], notes: list[str]) -> str:
    L = [f"## What changed from `{a['id']}` to `{b['id']}`", ""]
    d = b.get("derived_from")
    if d and d.get("changes_summary"):
        L += ["**The author's account:**", "", f"> {d['changes_summary']}", ""]
    mods = b.get("aircraft", {}).get("modifications", [])
    if mods:
        L += ["**Modifications:**", ""]
        for m in mods:
            flag = " *(affects procedures)*" if m.get("affects_procedures") else ""
            L.append(f"- **{m['kind']}**{flag} — {m['description']}")
        L.append("")
    if notes:
        L += ["**Configuration:**", ""] + [f"- {n}" for n in notes] + [""]

    g = group(findings)
    for rank, heading in enumerate(ORDER):
        if not g[rank]:
            continue
        L += [f"### {heading.title()}", ""]
        for f in sorted(g[rank], key=lambda x: (x.where, x.kind)):
            L.append(f"- `{f.kind}` in **{f.where}** — {f.text}")
        L.append("")
    if not sum(len(v) for v in g.values()):
        L.append("_No procedural differences._")
    return "\n".join(L) + "\n"


def resolve_fork(path: Path, corpus_dir: Path) -> tuple[Path, Path]:
    doc = json.loads(path.read_text())
    d = doc.get("derived_from")
    if not d:
        raise SystemExit(f"{path.name} has no derived_from block")
    parent = corpus_dir / f"{d['checklist_id']}.ocl.json"
    if not parent.exists():
        raise SystemExit(f"parent {d['checklist_id']!r} not found in {corpus_dir}")
    return parent, path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path, help="two files, or one with --fork")
    ap.add_argument("--fork", action="store_true", help="diff the given file against its recorded parent")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--corpus", type=Path, default=REPO / "examples")
    args = ap.parse_args()

    if args.fork:
        if len(args.files) != 1:
            raise SystemExit("--fork takes exactly one file")
        pa, pb = resolve_fork(args.files[0], args.corpus)
    else:
        if len(args.files) != 2:
            raise SystemExit("give two files, or one file with --fork")
        pa, pb = args.files

    a, b = json.loads(pa.read_text()), json.loads(pb.read_text())
    findings, notes = diff(a, b)
    out = render_markdown(a, b, findings, notes) if args.markdown else render_text(a, b, findings, notes)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
