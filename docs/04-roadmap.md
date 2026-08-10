# The site, the OCR pipeline, and a first milestone

Deliberately last, per your ordering. The research and the verification model
changed what this plan should be, so it is worth reading them first.

---

## 1. The strategic point that should shape everything below

Research report §3.3 found four prior "one source, many exports" checklist
projects. All four stalled as single-maintainer efforts with a handful of stars.
efis-editor is the one that got traction, and what distinguishes it is not a better
format — it is that it does the tedious work of reading and writing six real vendor
formats.

So: **the format is not the scarce thing, and neither is the site.** The scarce
things are a corpus with trustworthy provenance, and contributors. Every hour spent
on schema elaboration or site polish before there is a corpus is an hour spent on
the thing that has already failed four times.

Three consequences for sequencing:

1. **Build the corpus before the website.** A hundred good files in a git repo with
   no site is a useful project. A beautiful site with nine files is not.
2. **Build the low-friction contribution path early** — earlier than feels
   justified. It is the difference between one maintainer and a community, and it is
   the actual failure mode of the prior attempts.
3. **Do not reimplement the six vendor formats.** You were right about this. Defer
   them entirely until the corpus justifies the effort, then contribute a CLI
   upstream to efis-editor rather than forking its format layer.

---

## 2. The OCR pipeline

### The two failure modes, which need different defences

The kickoff identifies transcription error. Research report §3.4 found a second one
that the verification model as originally described would not catch:

- **Inaccuracy** — the machine misread the source. Defended by review and by the
  confidence mechanism.
- **Inadmissibility** — the machine read the wrong document perfectly. A search for
  a Piper J-3 POH returned a flight-simulator manual containing a plausible
  pre-takeoff checklist, © 2009, marked "not intended for flight." It would have
  transcribed cleanly, and every fidelity check would have passed.

Source screening therefore has to be a **separate gate before transcription**, not
a field filled in afterwards. And it will be the common case, not an edge case:
simulator material dominates search results for exactly the older types whose real
documentation is hardest to find.

### Stages

**Stage 0 — Acquisition and admissibility.** *Human decision, machine-assisted.*

Before a page is read, record: what the document is, who published it, its
revision, and which rights lane it falls in. Reject flight-simulator
documentation, third-party commercial checklist products, and anything whose
provenance cannot be established. A document that cannot be identified cannot be
admitted, because a reviewer would have nothing to compare against.

Output: a source record and a rights determination. No transcription happens until
this exists. `provenance.source.kind: simulator_product` is rejected by the
validator as a backstop, but the real gate is here.

**Stage 1 — Page rendering.** Deterministic. PDF to page images at consistent DPI;
extract any embedded text layer separately. Where a text layer exists it is a free
independent check on the vision pass, and the J-3 document I examined shows both
cases occur — one PDF was pure scanned images, the FAA handbook had extractable
text.

**Stage 2 — Region identification.** Which pages contain procedures, and which
regions on them. Cheap, and it stops the model transcribing narrative prose as
checklist items.

**Stage 3 — Structured transcription.** Model reads page images and emits schema-
conformant JSON directly, constrained by the schema, with per-item
`source_confidence`. Emitting the target structure rather than free text and
parsing it later removes a whole class of parsing error.

**Stage 4 — Independent second pass, and this is the important one.**

Run transcription **twice, independently** — different prompt framing, ideally a
different model — and diff the results. Every disagreement becomes a low
`source_confidence` on that item.

This is the highest-value machine step in the pipeline, and it is not
transcription. A single pass produces output that is uniformly confident and
therefore uninformative about where it is wrong. Two independent passes produce a
**map of where the document is ambiguous**, which is exactly what a human reviewer
needs in order to spend their attention well. It is the machine analogue of the
dual-review requirement, and it works for the same reason: independent readers make
different mistakes.

Two specific rules:

- **Every numeric value must agree across both passes or be flagged.** This is
  double-keying, borrowed from data entry, and numbers are both the highest-risk
  content and the easiest to check mechanically. A transposed airspeed is the defect
  most likely to hurt someone and least likely to look wrong.
- **Item counts per section must agree.** A dropped item is the defect the
  verification model cannot catch downstream, so catch it here. If the two passes
  disagree on how many items a section has, that section is flagged regardless of
  per-item confidence.

**Stage 5 — Deterministic checks.** Schema plus the policy validator, plus
plausibility rules: numeric values within physically sensible ranges for the
category, no section without an actionable item, phases in a coherent order,
warnings not orphaned from the item they qualify.

**Stage 6 — Human review.** A side-by-side of source page and transcription, with
disagreements and low-confidence items surfaced first. Reviewer resolves each,
which raises `source_confidence`; only then can the file leave `unreviewed`.

**Nothing merges automatically.** Stage 5 passing means a file is ready to be
reviewed, not ready to be published.

### Cost note

Two independent passes doubles the transcription cost and is worth it. The
expensive resource is not tokens, it is reviewer attention, and a good disagreement
map is what makes an hour of review cover a whole document instead of ten pages.

---

## 3. The site

Static site generated from the repository. No database (see
[02-format-decision.md §3](02-format-decision.md)).

**Build output:** a page per file with the verification state above the content; a
browsable index; a generated JSON metadata index for client-side filtering; per-file
downloads; a release tarball plus a signed SHA-256 manifest; and a separate
`unreviewed/` bundle.

**Non-negotiable UI rules** are in
[03-verification-model.md §3](03-verification-model.md). The one to design in from
the start is that quarantined files are never offered in vendor panel formats, since
retrofitting that means retracting files people already loaded into an aircraft.

**Contribution path.** Start with pull requests. Add the GitHub App form flow —
form in, branch and PR out — as soon as the corpus is real enough to attract people
who do not use git. This is the highest-leverage thing on the whole roadmap and the
easiest to defer forever.

**openchecklists.net today.** Put up one static page now: what the project is, the
verification model in three sentences, and a link to the repository. It costs an
hour, it stops the domain looking abandoned, and it gives you something to point at
when asking a type club for permission.

---

## 4. Milestones

### M0 — Decide (this proposal)

Review the four documents, the schema, the four examples, and the validator. Open
questions that need your answer are in §5.

### M1 — One clean source, end to end

**Small enough to finish. Scope it by what it excludes.**

Goal: prove the schema, the validator, and the review workflow on public-domain
material only, with no website and no OCR automation.

- Extract `open-checklists/` into its own repository. It is here because that is
  where this session's branch lives, and the git history should be a subtree split,
  not a copy-paste.
- `CONTRIBUTING.md` with the contributor warranty and DCO sign-off.
- `TAKEDOWN.md` with the process from the verification model.
- CI running `tools/validate.py --strict --check-form` and `tools/test_validate.py`
  on every pull request. **This is the load-bearing deliverable of M1** — the point
  at which corpus rules stop being a document and start being enforced.
- **Ten files, all from § 105 government sources.** FAA handbooks first, since
  those are text-extractable and unambiguously public domain.
- One exporter: JSON to PDF, with the watermark and per-page state header. Choose
  PDF because it is what people actually print, and because getting the labelling
  right in the artifact form most likely to be separated from its metadata is worth
  doing first.
- One file taken all the way to `single_reviewed` by a real second person, to prove
  the review workflow is something a human will actually do.

**Explicitly not in M1:** the website, vendor format export, OCR automation, the
submission form, and any POH-derived file. Manufacturer-sourced content waits until
CI enforces the rights rules and counsel has reviewed the posture.

**Done when:** ten files pass CI, one is `single_reviewed` by someone other than
the transcriber, and `make pdf` produces a correctly watermarked artifact.

### M2 — Rights posture and first manufacturer-derived content

Counsel review of the research report. Entity formation and an insurance quote
before manufacturer-derived files land, since that is when exposure starts.
Written permission requests to three or four type clubs and kit manufacturers —
nobody has asked, and some will say yes. First `original_expression` files for
common types.

### M3 — Pipeline

Stages 0–6 implemented, dual-pass diffing, the review UI. Target the aircraft with
no coverage anywhere rather than the tenth Cessna 172 variant: Part 103 and
experimental are where this project is the only option, and where the reception
will be warmest.

### M4 — Site and contribution flow

Static site, index, bundles, signed manifest, GitHub App submission flow.

### M5 — Vendor formats

The efis-editor harness. Contribute a CLI upstream rather than forking. Defer the
encrypted Garmin Pilot variant until counsel has looked at the § 1201 question, and
do not let it block the other five.

---

## 5. Open questions for you

1. **Entity and insurance.** Product liability is the largest exposure and it is
   personal until an entity exists. Are you willing to form one before the corpus
   grows? If not, that is a reason to keep the corpus small and § 105-only for
   longer than M1.
2. **`spec/checklist.md` does not exist in the Junco repository** — not on any
   branch, and never committed. If you have it locally, it is worth diffing against
   this proposal on provenance and item types, where you said the reasoning was
   already worked through.
3. **Part 103 content has no source document to verify against** (research report
   §3.5, verification model §1). For that class the project is authoring, not
   transcribing. Is that a role you want it to take? It is a materially different
   liability posture from republishing a manufacturer's procedure, and it is also
   the only way the gap you identified gets filled.
4. **The four example files are not airworthy and say so.** Only the FAA one is
   grounded in a source document I actually read; the other three are authored to
   exercise the schema, and every one omits airspeeds and limitations rather than
   inventing them. If you want examples that could be flown, that requires source
   documents I could not obtain in this environment — which is itself the finding
   in §3.5.
5. **Confidence threshold.** 0.98 in the reference implementation is a guess. It
   should be set by measuring a real dual-pass run against a known-good
   transcription, in M3.
