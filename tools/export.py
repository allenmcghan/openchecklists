#!/usr/bin/env python3
"""Convert a checklist to every consumable format.

    python3 tools/export.py examples/*.ocl.json --formats all

Formats: csv, tsv, md, txt, docx, xml, html (via render.py), json (the source).
PDF comes from the HTML through a browser's print path, so it is not duplicated
here.

Every converter obeys the safety-preserving export contract from
docs/02-format-decision.md:

    An export must reproduce every warning, caution, and memory_item in its
    original position relative to surrounding items, or fail. It may degrade
    layout, indentation, phase grouping, detail text and machine-readable value
    fields freely. It may never silently drop an item.

That is enforced, not merely intended: `verify_export` re-reads each generated
artifact and fails the build if a warning, caution or memory marker went missing.
A checklist export that quietly drops the reason an item exists is worse than no
export, because it still looks complete.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from pathlib import Path
from html import escape as html_escape
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import render as render_html  # noqa: E402
from validate import content_hash  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

INFO_TYPES = {"note", "caution", "warning"}
FORMATS = ["json", "csv", "tsv", "md", "txt", "xml", "docx", "html"]

TAG = {"note": "NOTE", "caution": "CAUTION", "warning": "WARNING"}


def state_line(doc: dict) -> str:
    v = doc.get("verification", {})
    bits = [
        f"source fidelity: {v.get('source_fidelity')}",
        f"operational review: {v.get('operational_review')}",
    ]
    if v.get("completeness"):
        bits.append(f"completeness: {v['completeness']}")
    defects = sum(1 for i in v.get("known_issues", []) if i.get("severity") == "safety_defect")
    if defects:
        bits.append(f"{defects} unresolved safety defect(s)")
    return " | ".join(bits)


def is_quarantined(doc: dict) -> bool:
    v = doc.get("verification", {})
    return v.get("source_fidelity") == "unreviewed" or any(
        i.get("severity") == "safety_defect" for i in v.get("known_issues", [])
    )


def banner_text(doc: dict) -> str:
    head = "NOT FOR FLIGHT — " if is_quarantined(doc) else ""
    return f"{head}{state_line(doc)}"


def header_lines(doc: dict) -> list[str]:
    src = doc.get("provenance", {}).get("source", {})
    r = doc.get("rights", {})
    return [
        doc.get("title", ""),
        banner_text(doc),
        f"Source: {src.get('title') or 'authored — no source document'}"
        + (f" ({src.get('document_number')})" if src.get("document_number") else "")
        + (f" rev {src.get('revision')}" if src.get("revision") else ""),
        f"Rights: {r.get('status')} {r.get('corpus_license') or ''}".strip(),
        f"Checklist hash: {content_hash(doc)}",
        "Verify against the aircraft's own approved documentation before use.",
    ]


# --------------------------------------------------------------------------- csv


def to_delimited(doc: dict, delimiter: str) -> str:
    """One row per item, with a type column.

    Deliberately not phase-as-column or challenge/response-as-only-columns: those
    shapes cannot represent a warning, which is exactly how a warning gets
    dropped. Every item occupies a row, whatever its type.
    """
    out = io.StringIO()
    w = csv.writer(out, delimiter=delimiter, lineterminator="\n")
    for line in header_lines(doc):
        w.writerow(["#", line])
    w.writerow(
        [
            "section_id",
            "phase",
            "criticality",
            "section_title",
            "item_index",
            "item_id",
            "type",
            "tickable",
            "memory_item",
            "indent",
            "text",
            "response",
            "condition",
            "detail",
        ]
    )
    for sec in doc.get("sections", []):
        for i, it in enumerate(sec.get("items", [])):
            w.writerow(
                [
                    sec.get("id", ""),
                    sec.get("phase_label") or sec.get("phase", ""),
                    sec.get("criticality", "normal"),
                    sec.get("title", ""),
                    i,
                    it.get("id", ""),
                    it.get("type", ""),
                    "yes" if it.get("tickable") else "no",
                    "yes" if it.get("memory_item") else "no",
                    it.get("indent", 0),
                    it.get("text", ""),
                    it.get("response", ""),
                    it.get("condition", ""),
                    it.get("detail", ""),
                ]
            )
    return out.getvalue()


# ---------------------------------------------------------------------- markdown


def to_markdown(doc: dict) -> str:
    L: list[str] = [f"# {doc.get('title')}", ""]
    if is_quarantined(doc):
        L += [f"> **NOT FOR FLIGHT** — {state_line(doc)}", ""]
    else:
        L += [f"> {state_line(doc)}", ""]
    if doc.get("description"):
        L += [doc["description"], ""]

    for issue in doc.get("verification", {}).get("known_issues", []):
        L.append(f"> **{issue['severity']}**: {issue['description']}")
    if doc.get("verification", {}).get("known_issues"):
        L.append("")

    for sec in doc.get("sections", []):
        crit = sec.get("criticality", "normal")
        suffix = "" if crit == "normal" else f" ({crit.upper()})"
        L += [f"## {sec.get('title')}{suffix}", ""]
        if sec.get("condition"):
            L += [f"*{sec['condition']}*", ""]
        for it in sec.get("items", []):
            pad = "    " * it.get("indent", 0)
            t = it.get("type")
            if t == "blank":
                L.append("")
            elif t == "subtitle":
                L.append(f"{pad}**{it['text']}**")
            elif t in INFO_TYPES:
                L.append(f"{pad}> **{TAG[t]}:** {it['text']}")
            elif t == "reference":
                L.append(f"{pad}> **GO TO:** {it['text']}")
            else:
                mem = " `MEMORY`" if it.get("memory_item") else ""
                resp = f" — **{it['response']}**" if it.get("response") else ""
                L.append(f"{pad}- [ ] {it['text']}{mem}{resp}")
            if it.get("detail"):
                L.append(f"{pad}  <sub>{it['detail']}</sub>")
        L.append("")

    L += ["---", ""] + [f"{line}  " for line in header_lines(doc)[1:]]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------- plain text


def to_text(doc: dict, width: int = 72) -> str:
    L: list[str] = []
    for line in header_lines(doc):
        L.append(line)
    L += ["=" * width, ""]

    for sec in doc.get("sections", []):
        crit = sec.get("criticality", "normal")
        title = sec.get("title", "").upper()
        if crit != "normal":
            title += f"  [{crit.upper()}]"
        L += [title, "-" * min(len(title), width)]
        if sec.get("condition"):
            L.append(f"  ({sec['condition']})")
        for it in sec.get("items", []):
            pad = "  " * it.get("indent", 0)
            t = it.get("type")
            if t == "blank":
                L.append("")
            elif t == "subtitle":
                L.append(f"{pad}{it['text'].upper()}")
            elif t in INFO_TYPES:
                L.append(f"{pad}** {TAG[t]}: {it['text']}")
            elif t == "reference":
                L.append(f"{pad}** GO TO: {it['text']}")
            else:
                mem = " [MEMORY]" if it.get("memory_item") else ""
                left = f"{pad}[ ] {it['text']}{mem}"
                resp = it.get("response")
                if resp:
                    dots = max(3, width - len(left) - len(resp) - 1)
                    L.append(f"{left} {'.' * dots} {resp}")
                else:
                    L.append(left)
        L.append("")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- xml


def to_xml(doc: dict) -> str:
    def e(v: object) -> str:
        return xml_escape(str(v)) if v is not None else ""

    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<openChecklist version="1.0">']
    L.append(f"  <title>{e(doc.get('title'))}</title>")
    L.append(f"  <contentHash>{content_hash(doc)}</contentHash>")
    ac = doc.get("aircraft", {})
    L.append(
        f'  <aircraft make="{e(ac.get("make"))}" model="{e(ac.get("model"))}" '
        f'variant="{e(ac.get("variant"))}" category="{e(ac.get("category"))}"/>'
    )
    v = doc.get("verification", {})
    L.append(
        f'  <verification sourceFidelity="{e(v.get("source_fidelity"))}" '
        f'operationalReview="{e(v.get("operational_review"))}" '
        f'completeness="{e(v.get("completeness"))}"/>'
    )
    r = doc.get("rights", {})
    L.append(f'  <rights status="{e(r.get("status"))}" license="{e(r.get("corpus_license"))}"/>')
    for issue in v.get("known_issues", []):
        L.append(f'  <knownIssue severity="{e(issue.get("severity"))}">{e(issue.get("description"))}</knownIssue>')

    L.append("  <sections>")
    for sec in doc.get("sections", []):
        L.append(
            f'    <section id="{e(sec.get("id"))}" phase="{e(sec.get("phase"))}" '
            f'criticality="{e(sec.get("criticality", "normal"))}">'
        )
        L.append(f"      <title>{e(sec.get('title'))}</title>")
        for i, it in enumerate(sec.get("items", [])):
            attrs = (
                f'type="{e(it.get("type"))}" index="{i}" '
                f'tickable="{str(bool(it.get("tickable"))).lower()}" '
                f'memoryItem="{str(bool(it.get("memory_item"))).lower()}" '
                f'indent="{it.get("indent", 0)}"'
            )
            if it.get("id"):
                attrs += f' id="{e(it["id"])}"'
            L.append(f"      <item {attrs}>")
            if it.get("text"):
                L.append(f"        <text>{e(it['text'])}</text>")
            if it.get("response"):
                L.append(f"        <response>{e(it['response'])}</response>")
            if it.get("condition"):
                L.append(f"        <condition>{e(it['condition'])}</condition>")
            if it.get("detail"):
                L.append(f"        <detail>{e(it['detail'])}</detail>")
            L.append("      </item>")
        L.append("    </section>")
    L += ["  </sections>", "</openChecklist>"]
    return "\n".join(L) + "\n"


# -------------------------------------------------------------------------- docx


def _docx_paragraph(text: str, *, bold=False, size=None, style=None, color=None, indent=0) -> str:
    runs = (
        f"<w:rPr>"
        f'{"<w:b/>" if bold else ""}'
        f'{f"<w:sz w:val={chr(34)}{size}{chr(34)}/>" if size else ""}'
        f'{f"<w:color w:val={chr(34)}{color}{chr(34)}/>" if color else ""}'
        f"</w:rPr>"
    )
    ppr = "<w:pPr>"
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if indent:
        ppr += f'<w:ind w:left="{indent * 360}"/>'
    ppr += "</w:pPr>"
    return f"<w:p>{ppr}<w:r>{runs}<w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r></w:p>"


def to_docx(doc: dict) -> bytes:
    """Minimal but valid .docx. Written directly as OOXML so there is no dependency.

    Word is where a lot of pilots will want to take a checklist to edit it, which
    is why this is a first-class output rather than an afterthought.
    """
    body: list[str] = [_docx_paragraph(doc.get("title", ""), bold=True, size=32)]
    body.append(_docx_paragraph(banner_text(doc), bold=True, color="B3261E" if is_quarantined(doc) else "1B5E20"))
    for issue in doc.get("verification", {}).get("known_issues", []):
        body.append(_docx_paragraph(f"{issue['severity']}: {issue['description']}", color="B3261E", size=18))
    body.append(_docx_paragraph(""))

    for sec in doc.get("sections", []):
        crit = sec.get("criticality", "normal")
        title = sec.get("title", "") + ("" if crit == "normal" else f"  [{crit.upper()}]")
        body.append(_docx_paragraph(title, bold=True, size=26))
        if sec.get("condition"):
            body.append(_docx_paragraph(sec["condition"], size=18))
        for it in sec.get("items", []):
            t = it.get("type")
            ind = it.get("indent", 0)
            if t == "blank":
                body.append(_docx_paragraph(""))
            elif t == "subtitle":
                body.append(_docx_paragraph(it["text"].upper(), bold=True, size=20, indent=ind))
            elif t in INFO_TYPES:
                col = {"warning": "B3261E", "caution": "8A5A00", "note": "1F4E79"}[t]
                body.append(_docx_paragraph(f"{TAG[t]}: {it['text']}", bold=True, color=col, indent=ind))
            elif t == "reference":
                body.append(_docx_paragraph(f"GO TO: {it['text']}", bold=True, color="1F4E79", indent=ind))
            else:
                mem = " [MEMORY]" if it.get("memory_item") else ""
                resp = f" .... {it['response']}" if it.get("response") else ""
                body.append(_docx_paragraph(f"[ ]  {it['text']}{mem}{resp}", indent=ind))
            if it.get("detail"):
                body.append(_docx_paragraph(it["detail"], size=16, indent=ind + 1))
        body.append(_docx_paragraph(""))

    for line in header_lines(doc)[1:]:
        body.append(_docx_paragraph(line, size=14, color="666666"))

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


# ------------------------------------------------------------------- the contract


def expected_safety_markers(doc: dict) -> tuple[list[str], int]:
    """Text of every warning/caution, and the count of memory items."""
    texts = [
        it["text"]
        for sec in doc.get("sections", [])
        for it in sec.get("items", [])
        if it.get("type") in ("warning", "caution")
    ]
    memory = sum(
        1 for sec in doc.get("sections", []) for it in sec.get("items", []) if it.get("memory_item")
    )
    return texts, memory


# How each format marks a memory item. Every format must mark them somehow; the
# token differs because a machine format spells it as a field and a human format
# spells it as a label. Both count.
MEMORY_TOKEN = {
    "json": '"memory_item": true',
    "xml": 'memoryItem="true"',
    "md": "`MEMORY`",
    "txt": "[MEMORY]",
    "docx": "[MEMORY]",
    "html": 'class="mem"',
    "csv": None,  # column-based; handled below
    "tsv": None,
}


def verify_export(doc: dict, fmt: str, blob: bytes) -> list[str]:
    """Enforce the safety-preserving export contract against a produced artifact."""
    problems: list[str] = []
    texts, memory = expected_safety_markers(doc)

    if fmt == "docx":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            hay = z.read("word/document.xml").decode("utf-8")
        esc = xml_escape
    else:
        hay = blob.decode("utf-8")
        # Each format escapes differently, and comparing raw text against escaped
        # output produces false drops -- an apostrophe alone is enough to do it.
        esc = {"xml": xml_escape, "html": html_escape}.get(fmt, lambda x: x)

    for t in texts:
        needle = esc(t)
        if needle not in hay:
            problems.append(f"{fmt}: dropped a warning/caution: {t[:60]!r}")

    if memory:
        if fmt in ("csv", "tsv"):
            # The memory_item column carries it per row; count the affirmative cells.
            delim = "," if fmt == "csv" else "\t"
            found = sum(
                1
                for row in csv.reader(io.StringIO(hay), delimiter=delim)
                if len(row) > 8 and row[8] == "yes"
            )
        else:
            found = hay.count(MEMORY_TOKEN[fmt])
        if found < memory:
            problems.append(f"{fmt}: memory items not all marked ({found} of {memory})")

    return problems


# ------------------------------------------------------------------------- driver

EXT = {"json": "json", "csv": "csv", "tsv": "tsv", "md": "md", "txt": "txt", "xml": "xml", "docx": "docx", "html": "html"}


def export(doc: dict, fmt: str) -> bytes:
    if fmt == "json":
        return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode()
    if fmt == "csv":
        return to_delimited(doc, ",").encode()
    if fmt == "tsv":
        return to_delimited(doc, "\t").encode()
    if fmt == "md":
        return to_markdown(doc).encode()
    if fmt == "txt":
        return to_text(doc).encode()
    if fmt == "xml":
        return to_xml(doc).encode()
    if fmt == "docx":
        return to_docx(doc)
    if fmt == "html":
        return render_html(doc, "letter").encode()
    raise ValueError(fmt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--formats", default="all", help=f"comma-separated, or 'all': {','.join(FORMATS)}")
    ap.add_argument("-o", "--outdir", type=Path, default=REPO / "build" / "downloads")
    args = ap.parse_args()

    formats = FORMATS if args.formats == "all" else [f.strip() for f in args.formats.split(",")]
    bad = set(formats) - set(FORMATS)
    if bad:
        raise SystemExit(f"unknown format(s): {', '.join(sorted(bad))}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    problems = 0
    for path in args.files:
        doc = json.loads(path.read_text())
        for fmt in formats:
            blob = export(doc, fmt)
            out = args.outdir / f"{doc['id']}.{EXT[fmt]}"
            out.write_bytes(blob)
            issues = verify_export(doc, fmt, blob)
            for msg in issues:
                print(f"  CONTRACT VIOLATION: {msg}")
            problems += len(issues)
        print(f"{doc['id']}: {len(formats)} format(s)")

    print(f"\n{problems} contract violation(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
