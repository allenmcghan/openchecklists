# Open Checklists — design proposal

A free, open, machine-readable library of aircraft checklists in a standard format
anyone can consume, reformat, modify, and redistribute.

**Design plus working tooling.** The format, the validators, the phone/print
renderer, the exporters and the static site all run today; the OCR pipeline and the
contribution flow do not exist yet. `python3 tools/build_site.py` produces the whole
site from the corpus in `examples/`.

It lives in the Junco repository because that is where the work was commissioned.
It is intended to be split out into its own repository with `git subtree split`,
preserving history — see [docs/04-roadmap.md](docs/04-roadmap.md) M1.

---

## Read in this order

| Document | What it covers |
| --- | --- |
| [docs/01-legal-research.md](docs/01-legal-research.md) | Copyright doctrine and where the line actually is; **product liability, which is the larger risk and was not in the brief**; the public-domain lanes; what other collections exist and what happened to them |
| [docs/02-format-decision.md](docs/02-format-decision.md) | JSON as canonical, with reasoning; four things in the brief I think are wrong; architecture; licensing |
| [docs/03-verification-model.md](docs/03-verification-model.md) | Two-axis verification, evidence rules, automatic demotion, presentation rules, provenance, contributor warranty, takedown process |
| [docs/04-roadmap.md](docs/04-roadmap.md) | OCR pipeline design, the site, and a first milestone scoped to be finishable |
| [docs/05-product-and-sourcing.md](docs/05-product-and-sourcing.md) | The phone + log product, why freechecklists.net cannot be bulk-scraped, and where the corpus comes from instead |
| [docs/06-community-currency.md](docs/06-community-currency.md) | **Read this one.** Field reports as the way the corpus stays current; what copyright does and does not cover here; where the flight-club analogy holds and where it stops |

## Artifacts

| Path | What it is |
| --- | --- |
| [schema/open-checklist-1.0.schema.json](schema/open-checklist-1.0.schema.json) | JSON Schema 2020-12. Structural validity, including the conditional rules that make a warning untickable |
| [schema/open-checklist-log-1.0.schema.json](schema/open-checklist-log-1.0.schema.json) | Completion log format: what was ticked, when, by whom, against which exact checklist version |
| [tools/acquire.py](tools/acquire.py) | Public-domain acquisition: Internet Archive discovery, manifest fetch with SHA-256, host allowlist that refuses freechecklists by name |
| [sources/public-domain.json](sources/public-domain.json) | Curated PD source manifest with per-document rights basis and discovery recipes |
| [tools/render.py](tools/render.py) | One JSON in, one self-contained HTML out: phone tick-off, any paper size, log export. Zero external requests |
| [tools/validate.py](tools/validate.py) | Reference validator: schema, then the policy rules JSON Schema cannot express |
| [tools/validate_log.py](tools/validate_log.py) | Log validator, including the implied-working-rate check |
| [schema/open-checklist-report-1.0.schema.json](schema/open-checklist-report-1.0.schema.json) | Field report format: stale item, transcription error, airframe variation, newer source revision |
| [tools/validate_report.py](tools/validate_report.py) | Report validator. A confirmed defect must demote the file it targets; a live safety concern must travel inside the file |
| [tools/test_reports.py](tools/test_reports.py) | 14 cases covering the demotion and safety-disclosure rules |
| [tools/export.py](tools/export.py) | Converters to json, csv, tsv, md, txt, xml, docx, html — each verified against the safety-preserving export contract |
| [tools/build_site.py](tools/build_site.py) | Static site generator: filterable catalogue, per-checklist pages, airframe family pages, all download formats, machine catalogue, SHA-256 manifest |
| [tools/site_editor.py](tools/site_editor.py) | The browser editor page: create or fork a checklist, records lineage automatically, downloads valid JSON |
| [tools/diff.py](tools/diff.py) | Semantic diff between two checklists, safety-relevant changes first. `--fork` diffs a file against its recorded parent |
| [tools/test_validate.py](tools/test_validate.py) | 27 negative cases proving the safety rules fire |
| [examples/](examples/) | Five checklist files, a worked completion log, and two field reports |

## The four examples

**None of these is airworthy. Do not fly behind any of them.** Each states this in
its own `verification.known_issues`.

| File | Why it exists |
| --- | --- |
| `faa-generic-sep-ground-operations` | The only one grounded in a source document that was actually read: FAA-H-8083-3C Ch. 2, a US Government work in the public domain. Demonstrates the clean-rights lane |
| `cessna-172n-normal` | The hard copyright case. Demonstrates the recommended posture for a type whose POH is still protected: procedure as fact, wording the contributor's own, limitations deliberately omitted rather than recalled |
| `aerolite-103-hirth-f33` | Part 103, the gap in the brief. Authored rather than transcribed, because Part 103 aircraft are not required to have a flight manual at all. Exercises memory items, warnings, and an emergency section |
| `beechcraft-t-34a-usaf` | **The first real type-specific transcription.** From USAF T.O. 1T-34A-1 (1958), a US Government work with no copyright, for a type civilians still fly. 117 tickable items, 27 memory items, `unreviewed` |
| `aerolite-103-kawasaki-340-n512jm` | **The lineage case.** Same airframe as the Aerolite baseline with a different engine, forked with `derived_from`, showing exactly what the swap forced |
| `schweizer-sgs-2-33a` | A glider. No engine, a launch phase with no powered equivalent, and emergencies that are entirely about the tow |

There is deliberately **no example with `rights.status: upstream_reserved`**,
because the recommendation is that such files must never be published — and the
validator enforces it.

## Running the tools

```sh
pip install jsonschema

python3 tools/validate.py                 # validate examples/
python3 tools/validate.py --strict        # warnings become errors
python3 tools/validate.py --write-stable   # normalise to the stable storage form
python3 tools/test_validate.py            # prove the safety rules fire

python3 tools/render.py examples/*.ocl.json --paper kneeboard   # -> build/*.html
python3 tools/validate_log.py examples/*.ocl-log.json

python3 tools/validate_report.py          # validate field reports
python3 tools/test_reports.py             # prove the demotion rules fire

python3 tools/acquire.py discover "NATOPS flight manual"   # find PD candidates
python3 tools/acquire.py fetch --all                        # -> sources/documents/

python3 tools/export.py examples/*.ocl.json --formats all   # -> build/downloads/
python3 tools/build_site.py --base-url https://openchecklists.net  # -> build/site/

python3 tools/diff.py --fork examples/aerolite-103-kawasaki-340-n512jm.ocl.json
```

Forking in the editor needs to read the parent file, which browsers block for
`file://` pages, so serve the site to use it:

```sh
cd build/site && python3 -m http.server 8000
```

### Variations, which is the point for experimental and ultralight

Engine swaps, prop changes and panel rebuilds are the norm in this class, so one
builder's checklist is most useful to the next when you can see what they changed.
Three pieces make that work:

- **`aircraft.airframe_family`** groups every variation of one airframe regardless of
  what is bolted to the front, and **`aircraft.modifications[]`** records the swaps
  themselves so they are searchable.
- **`derived_from`** records lineage by attribution, not inheritance. A forked file
  stays complete and standalone — a pilot always holds the whole checklist, never a
  composition resolved at render time — while still linking to its parent and the
  parent's hash at the time of the fork.
- **`tools/diff.py`** and the family pages turn that into the thing a builder
  actually wants to read: what changed, warnings and memory items first.

### The site

`build_site.py` emits a complete static site with no server and no database:

| Path | What it is |
| --- | --- |
| `index.html` | Filterable catalogue — search by make, model, category, source; filter by verification state |
| `c/<id>/index.html` | The checklist: tick on a phone, print at any paper size, export a log |
| `c/<id>/<id>.{json,csv,tsv,md,txt,xml,docx}` | Every download format. Quarantined files carry `.UNREVIEWED` in the filename |
| `api/index.json` | Machine catalogue: metadata, verification state and rights per file. No key, no rate limit |
| `api/checklists/<id>.json` | Stable plain-HTTP path to every file |
| `manifest.sha256` | Hash of every published artifact, so a mirror can be verified |
| `reviewed.txt` / `unreviewed.txt` | Bundle listings, kept separate on purpose |
| `editor.html` | Create a checklist or fork any in the catalogue. Client-side, no account. Forking fills in lineage and computes the parent hash in the browser |
| `f/<family>/index.html` | Every variation of one airframe, with each fork's diff from its parent inline |
| `about.html` | What the verification states mean, and why "flown behind it" is not the top one |

Open a rendered file on a phone: tick items, choose a paper size, print, export a
log. It makes no network requests, so it works in a hangar with no signal.

## The four things in the brief I pushed back on

Detail and reasoning in the documents; summarised here so they are not buried.

1. **Product liability is the bigger risk than copyright.** US courts have
   repeatedly treated aeronautical charts as *products* subject to strict liability,
   and *Winter v. G.P. Putnam's Sons* refused to extend that to a book specifically
   because a chart is a tool used in flight. A checklist is on the chart side of
   that line. No licence or disclaimer addresses it. Research report §2.

2. **A repo-wide CC-BY-4.0 over the corpus would assert a licence the project does
   not hold.** You cannot license text you do not own, and the harm compounds
   silently as the corpus grows. Rights must be per file. Research report §1,
   format decision §4.

3. **"Verified — someone flew behind it" is the wrong top state.** Flying behind a
   checklist cannot detect a dropped item, which is the most likely and most
   dangerous transcription defect: nothing prompts you to do the missing check, so
   the flight feels normal. Two independent axes instead of one ladder, and
   operational review never lifts a file out of quarantine. Verification model §1.

4. **"Publish a JSON Schema so anyone can validate" is a promise that cannot be
   kept.** Reviewer independence, dual-review distinctness, hash staleness, and
   reference resolution are not expressible in JSON Schema. Without a published
   policy layer, third-party validators will green-light files the corpus forbids.
   Format decision §2.1.

Plus one finding that changes the pipeline: **a perfect transcription of the wrong
document passes every accuracy check.** Searching for a Piper J-3 POH surfaced a
flight-simulator manual containing a plausible checklist, © 2009, marked "not
intended for flight." Source admissibility has to be a separate gate before
transcription, and for older types it will be the common case. Research report §3.4.

## What was verified rather than assumed

- **efis-editor's data model** was read from a local clone, not from documentation.
  It is a presentation model with no phase ids, no provenance, and no verification;
  its item types map cleanly onto the proposed set. Its format layer imports no
  Angular and depends on `window.crypto` in two files only, so a headless Node
  harness is viable — but it has no `bin` and no `main`, so it is not a library and
  this is days of work, not an afternoon. Research report §3.1.
- **The FAA source** was downloaded and its text extracted directly.
- **Junco's licensing** was read from its `LICENSE` files. `GPL-2.0-or-later` for
  code, `CC-BY-4.0` for specs. The "or later" matters: Apache-2.0 is incompatible
  with GPL-2.0-only, so it is what makes efis-editor's code reachable from Junco at
  all. Format decision §4.
- **The validator's negative cases** were run; all 27 fire.

## What could not be verified

- **No case law on aircraft checklists specifically**, in either direction, and no
  evidence of any free checklist repository being taken down by a manufacturer. The
  observed failure mode of prior projects is attrition, not enforcement. Low
  enforcement is worth knowing and is not a safe harbour.
- **freechecklists.net returned HTTP 503** on both attempts, so its terms of use
  were not read. Confirm before treating anything there as a source.
- **No freely available Part 103 or ultralight checklist was found for any type.**
  This corroborates the gap in the brief and has a structural cause: Part 103
  aircraft need no approved flight manual, so there is often no source document to
  transcribe. Research report §3.5.

## Open questions

In [docs/04-roadmap.md §5](docs/04-roadmap.md). The one that should be answered
first is whether you will form an entity before the corpus grows, because the
liability exposure is personal until you do.
