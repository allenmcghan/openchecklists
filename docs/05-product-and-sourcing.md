# The product, and where the corpus actually comes from

Written after you clarified the goal: a phone you tick off during preflight, a log
that proves you did it, printable at whatever paper size your kneeboard takes, and
a free central repository behind it.

That clarification changes the priorities in [04-roadmap.md](04-roadmap.md), and it
runs into one hard obstacle that needs settling before any transcription starts.

---

## 1. What you described is a different project shape than the brief implied

The kickoff read as a format-and-corpus project. What you actually want is a
**tool with a corpus behind it**. That reordering matters, because
[04-roadmap.md §1](04-roadmap.md) found four prior open-source checklist projects
that all stalled — and every one of them was a format-and-export project with no
end-user product. The thing none of them had is the thing you just described.

The three requirements in your clarification are all things the existing PDF
libraries structurally cannot do, and all three fall out of the format almost for
free:

| What you want | Why PDFs can't | What makes it work |
| --- | --- | --- |
| Tick items on a phone | A PDF is a fixed page image | Items are structured data, so a phone can render one control per row |
| Print at any paper size | Page geometry is baked in | Re-render per paper size from the same source |
| Proof you did the preflight | A PDF has no idea you read it | A separate log format that records what was ticked, when, against which version |

The first two are demonstrated in this proposal by `tools/render.py`. The third
needed a new schema, which is `schema/open-checklist-log-1.0.schema.json`.

### The log is probably the more valuable half

Nobody else is doing it. Vendor checklist features tick boxes but do not produce a
portable, verifiable record; the free PDF libraries produce no record at all. And
the log is where the corpus stops being a nice-to-have: a log is only meaningful if
it says *which* checklist was used, which requires the checklist to have a stable
identity and a content hash. That is an argument for the corpus that has nothing to
do with convenience.

Concretely, `checklist.content_hash` in the log is the load-bearing field. Without
it a log records that somebody ticked twenty-five boxes under a heading. With it,
the log names the exact document, and the document can be fetched and inspected
years later.

### One thing about the log you should decide with your eyes open

**A timestamped log is evidence in both directions.**

Part 91 does not require a preflight log. §91.7 makes the PIC responsible for
determining airworthiness and §91.103 for being familiar with the flight's
information, but neither asks for a record. So the log's real audiences are you,
your club or flight school, your insurer, and — if something goes wrong — an
investigator or an opposing lawyer.

That last audience is the one to think about. A log showing forty items ticked in
nine seconds is worse than no log: it documents that you did not do the inspection.
A log series showing you routinely skip the same item establishes a pattern. Once
you start producing records, the records exist.

I think that argues *for* building it, but it changes how:

- **No "check all" button.** `tools/render.py` deliberately has none, and the
  docstring says why. A log that can be filled in without reading anything looks
  like evidence and is not.
- **Timestamp at the moment of the tick**, not at export.
- **Make the honest path the fast path.** If real logging is slow, people will
  batch-tick at the end and the timestamps become fiction.
- **Record how it was recorded.** `recording.mode` distinguishes `live` from
  `retrospective`. A reconstructed log is a legitimate thing to keep; presenting
  one as if it were live is not.
- **Say when the clock is untrustworthy.** `clock_source: device_clock` is a
  user-settable clock. The validator warns about it.
- **Make skipping expressible.** `state: skipped` requires a `reason`, and
  `not_applicable` exists because "vacuum check on an all-electric panel" is not a
  skip. `outcome: aircraft_rejected` is first-class, because a preflight that finds
  a problem and stops is the system working, and a format that can only record
  success quietly pressures people to record success.
- **Chain the logs.** `previous_log_hash` makes a series append-only in practice:
  removing or backdating one entry breaks every later link. It is the only
  mechanism here that resists after-the-fact tidying, and it costs almost nothing.

`tools/validate_log.py` implements the check that follows from all this: it
computes the implied working rate and refuses to call the log evidence of an
inspection when the rate is physically implausible. It caught my own automated test
run at 0.07 seconds per item, which is exactly what it is for.

---

## 2. The obstacle: freechecklists.net cannot be bulk-scraped

The site was down when I wrote the research report. It is up now, and I read it.
This is the part of your plan I have to push back on hardest, because it is
squarely prohibited rather than merely risky.

### What it actually is

**freechecklists.net is owned and operated by Dauntless Software**, a commercial
aviation software company. The site is a marketing and lead-generation asset for
their paid products — GroundSchool (FAA written test prep), RideReady (checkride
prep), SimPlates, FAR/AIM, and **Safelog, their pilot logbook product**. Every page
carries navigation into the shop.

It holds **760 checklists and other resources** at the time of writing. There are no
direct PDF links on the landing page; content is behind an ASP search interface, so
bulk retrieval means driving their search UI, not walking a directory.

### The terms forbid exactly what you proposed

The site has a two-column **DO / DO NOT** table. Quoting the DO NOT column
verbatim:

> **Direct link to files/checklists (for website owners).** Rather, link to
> www.freechecklists.net or www.dauntless-soft.com ONLY.
>
> **Attempt to in any way sell the resources you find here, claim credit for what
> is not yours.** Do respect copyright.
>
> **Copy the material from this page and put it on your web page. You do not have
> permission to do this.**

And from the DO column:

> Respect the hard work and copyright of the creators of this material.

That last quoted line is the plan — "pull down the entire freechecklists repository
and OCR everything, then publish it" — described and expressly refused. There is no
ambiguity to work with.

Two further data points. `freechecklists.net` has **no robots.txt** (404), and
`dauntless-soft.com`'s robots.txt disallows only `/checkrideforum/` and
**`ia_archiver`** — the Internet Archive's crawler. Blocking the Archive
specifically is a deliberate stance against having their content mirrored. Robots
files do not technically forbid a crawler here, but the human-readable terms do
forbid the republication, and the Archive block tells you how they will read it.

### Three independent reasons this fails, not one

**It breaches the site's stated terms.** Covered above.

**Dauntless mostly cannot give you permission even if they wanted to.** Their own
text points at "the creators of this material" — the checklists were contributed by
third parties, who hold whatever thin rights exist in their particular selection
and arrangement, on top of whatever the manufacturer holds in the underlying POH.
Dauntless is a host. So asking them yields, at best, permission to copy the small
share they authored. This is worth understanding before you spend goodwill on the
ask.

**It would poison the corpus.** This is the reason I would refuse even if the terms
were silent. The verification model's whole value is that every file's rights and
provenance are resolved. Ingesting 760 files whose provenance is "found on
freechecklists" produces 760 files with `rights.status: unresolved` and
`source.kind: third_party_checklist` — which the validator refuses to publish, by
design. You would have converted a tractable per-file problem into one
undifferentiated mass, and lost the ability to say anything trustworthy about any
of it.

There is also a practical point worth naming: Dauntless sells logbook software.
A free product that both distributes a corpus scraped from their site *and* logs
flights is maximally adverse to the one party with both standing and motive to act.

---

## 3. Where the corpus actually comes from

The goal is reachable. It just is not reachable by mirroring somebody else's site.

### Use freechecklists as an index, not as a source

**Facts about what exists are not protected.** That an Aeroprakt A-32 Vixxen
checklist exists, that a T-34B has a NATOPS pocket checklist, that 760 resources
span roughly 70 manufacturers — that is information you can use freely to build a
worklist. What you cannot do is take their files.

So: browse it like a card catalogue. Build a coverage map of which types the
community needs. Then obtain each underlying document from its actual source.

Their own listing points straight at the best lane. Among the latest additions I
saw: **"T-34B NATOPS Pilot's Pocket Checklist 1981"** and **"T-34B NATOPS Flight
Manual 1981."** NATOPS is a US Navy publication — a §105 government work with no
copyright at all. That document should be obtained from a government or archival
source, where it is unencumbered, rather than copied from a commercial site that
forbids copying. Same result, clean provenance, no terms breached.

### Priority order for acquisition

1. **US government works** (§105, no copyright): FAA handbooks and ACs; military
   NATOPS, Dash-1 flight manuals, and technical orders. Check authorship, since
   contractor-authored technical data is not automatically a §105 work. This lane
   is large, legitimate, and nobody has systematically converted it to
   machine-readable form.
2. **Owners with the POH in hand.** The highest-value contribution path and the one
   the GitHub App submission flow exists to serve. An owner transcribing their own
   aircraft's checklist, recording the source, is the model contribution — and it is
   the only route that reaches `operational_review: ground_checked`.
3. **Type clubs and kit manufacturers.** Ask. Nobody has. A kit manufacturer whose
   customers are asking for phone checklists has a reason to say yes, and a small
   manufacturer can actually grant permission for its own manual — unlike
   Dauntless.
4. **Formalities-lapsed documents**, per the lanes in
   [01-legal-research.md §1.4](01-legal-research.md). Requires a records check per
   document, so it is slow, but it unlocks the older types.
5. **Authored content for Part 103 and experimental**, where no source document
   exists at all. [01-legal-research.md §3.5](01-legal-research.md).

### Do ask Dauntless — but for the right thing

Not for a bulk dump. Ask whether they would be interested in their contributors
being *offered* a path to publish machine-readable versions, or whether they would
link to the project. They are in the test-prep and logbook business; a
machine-readable checklist corpus does not compete with GroundSchool. Frame it as
sending their contributors somewhere useful, get any permission in writing, and
record it in `rights.permission_evidence_url`.

If they decline, nothing is lost, because the plan above never depended on them.

### The re-expression rule still applies

Even with an admissible source, [01-legal-research.md §1.3](01-legal-research.md)
governs: transcribe the facts, do not clone the document. Copy control names,
positions, values and order exactly; write the surrounding text yourself; skip
narrative entirely. This is what `rights.status: original_expression` means, and
`examples/cessna-172n-normal.ocl.json` shows the posture.

---

## 4. Revised sequencing

The clarification moves the phone renderer forward and pushes vendor formats
further back. Replaces the M1–M5 list in [04-roadmap.md §4](04-roadmap.md):

**M1 — The tool, on ten public-domain files.** The renderer and the log, working end
to end, on FAA-sourced content only. CI enforcing schema and policy. This is
already most of the way there: `render.py` produces the phone view and prints to
any paper size, `validate_log.py` checks the logs. What it needs is real content, a
service worker so it works offline at the aircraft, and log persistence between
sessions.

Deliberately excluded: the website, vendor panel formats, OCR automation, and every
file whose rights are not `public_domain`.

**M2 — Acquisition at scale.** The coverage map built from freechecklists as an
index. Government-source pipeline. Permission letters to type clubs and kit
manufacturers. Entity and insurance before anything manufacturer-derived lands.

**M3 — Contribution flow.** The GitHub App form path, because the owner with the
POH is the scarce resource and will not open a pull request.

**M4 — OCR pipeline.** Per [04-roadmap.md §2](04-roadmap.md), with source
admissibility as a gate ahead of transcription.

**M5 — Site, bundles, signed manifest. M6 — Vendor formats.**

The one thing I would not defer is the **offline** requirement. A checklist app that
needs signal is useless in a metal hangar, and retrofitting offline support into a
web app is much harder than building it that way. `render.py` already emits a
single file with zero external requests, which is the right instinct to preserve.
