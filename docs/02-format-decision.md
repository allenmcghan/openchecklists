# Format, architecture, and licensing: recommendation

You asked to be argued with rather than agreed with. I agree with your headline
conclusion — **canonical JSON with a published JSON Schema** — but I think you
reached it partly for the wrong reasons, and four of the supporting decisions need
changing. The disagreements are in §2.

---

## 1. The recommendation

| Layer | Recommendation |
| --- | --- |
| Canonical corpus format | **JSON**, one file per aircraft type or variant, `*.ocl.json` |
| Validation | **JSON Schema 2020-12** *plus a published policy rule set with a reference implementation* |
| Source of truth | **Static files in git.** Your instinct is right; see §3 for where it breaks and what to do about it |
| Generated artifacts | PDF, HTML, CSV, XML, and the six vendor formats — via a harness over efis-editor's format layer, not a reimplementation |
| Corpus licence | **Per file, not repo-wide.** `CC0-1.0` for public-domain-sourced, `CC-BY-4.0` for original expression. No blanket LICENSE over the corpus |
| Schema and spec licence | **`CC0-1.0`** |
| Site and tooling licence | **`Apache-2.0`** — see §4, this one has a real constraint behind it |

### Why JSON, briefly

Your stated reasons — best tooling, easiest to consume, diffable with stable key
order — are all true but none is decisive. XML with an XSD would also give you
validation and tooling, and would give you better native support for mixed content
and for namespaced extension.

The decisive reason is narrower: **the consumers of this corpus include embedded
software, and JSON is the only one of the three that every one of them can already
parse without adding a dependency.** Junco is a flight computer. A microcontroller
firmware can consume JSON with a few kilobytes of parser; an XML parser with
schema support is not something you put on that device. CSV it could parse
trivially but cannot represent the data. When the primary consumer is a
resource-constrained device and the secondary consumers are web and mobile apps,
JSON wins on the union of those constraints, not on tooling quality.

Your CSV and XML analysis is right and I have nothing to add to it, except the
important caveat in §2.3 about what a CSV export is allowed to drop.

### On TOML and Junco's `spec/checklist.md`

**That file does not exist in the Junco repository.** It is not on `main`, not on
any branch, and `git log --all --diff-filter=A` finds no commit that ever added it.
So I could not read the prior reasoning, and this proposal was developed without
it. If it exists in a working tree somewhere, it is worth diffing against this
proposal specifically on the provenance and item-type questions, where you said
its reasoning was already worked through.

On the format decision itself I agree with your own assessment: TOML is the wrong
choice for a corpus consumed primarily by software. But your framing gives away
something you should keep. TOML's advantage was hand-editability, and that is a
real advantage for a project whose contributors are pilots rather than
programmers. The right resolution is not to accept JSON's editing ergonomics as
the cost of doing business — it is to **make canonical JSON the wire and storage
format, and provide an authoring path that is not raw JSON**: a converter from a
simple line-oriented text form, and eventually a web editor that emits canonical
JSON. Hand-editability should be a property of the tooling, not of the corpus
format.

---

## 2. Where I think you are wrong

### 2.1 "Publish a JSON Schema so anyone can validate" — that promise cannot be kept

This is the most important disagreement, because it is the one that quietly
undermines the safety model.

A significant share of the rules that keep this corpus safe **cannot be expressed
in JSON Schema at all**:

- A review is only a review if the reviewer is not the transcriber. That is a
  comparison between two arrays in different parts of the document.
- `source_fidelity: dual_reviewed` must be backed by review records from two
  *distinct* reviewers.
- A review stops covering the content once the content changes — which requires
  hashing the document and comparing.
- A `reference` item pointing at `section_id` must resolve to a section that
  exists.
- An item whose transcription confidence is below threshold must block promotion
  out of `unreviewed`.
- A file whose rights are unresolved must not be published at all.

JSON Schema handles the structural half well, and I have leaned on it hard — the
proposed schema uses `if`/`then` to enforce that an `action` must have a
`response`, that information items can never be `tickable` or `memory_item`, that
a `public_domain` claim must state its basis, and that an `upstream_reserved` file
cannot simultaneously claim a corpus licence. Those are real invariants and it is
good that they live in the portable artifact.

But if you publish only the schema and say "anyone can validate," third-party
tools will validate the structure, get a green light, and **silently accept files
that the corpus rules forbid.** A downstream app would happily ingest a file
claiming `dual_reviewed` with no reviews recorded.

So the deliverable is two artifacts, not one:

1. `schema/open-checklist-1.0.schema.json` — structure, portable, authoritative.
2. A written policy rule set with stable rule identifiers, plus a reference
   implementation. `tools/validate.py` in this proposal is that implementation:
   it runs the schema first, then seven policy checks, and `tools/test_validate.py`
   proves they fire with **27 negative cases, all caught**.

Consumers must be told plainly: schema validity is necessary and not sufficient,
and the verification fields must not be trusted unless the policy checks passed.

There is a stronger version of this available later, and it is worth designing
toward: make the *repository* the enforcement point, so that no file can reach the
published corpus without passing policy in CI. Then downstream consumers can trust
files that came from the corpus, and treat files from elsewhere as untrusted
regardless of what their verification block claims.

### 2.2 JSON's diffability is weaker than you are counting on, and the fix is not the format

You are right that pretty-printed JSON with stable key order diffs acceptably, and
a mandated storage form is worth having. The reference tooling implements it as
`--write-stable`: the author's key order preserved, two-space indent, one field per
line, trailing newline.

One refinement on your "stable key order" instinct. There are two different jobs
here and they want opposite things. *Hashing* wants alphabetically sorted keys, so
that any implementation in any language reproduces the same bytes without anyone
having to agree on a key-order specification. *Storage* wants the author's order,
because alphabetical sorting would put `sections` before `title` and scatter the
provenance and verification blocks through the file. The tooling therefore keeps
them separate: sorted-key serialization for `content_hash`, author-order for what
is committed.

But the thing that matters for a safety document is not whether the diff is
*small*. It is whether a reviewer **notices the significant change among the
insignificant ones**. Consider a pull request that changes a rotation speed from
55 to 65 and reflows two notes. In a JSON diff those are three similar-looking
hunks. A reviewer scanning for problems has to reconstruct the meaning of each.

Do not solve this by changing format. Solve it by **rendering the diff
semantically in review**: a CI job that posts a human-readable before/after —
items added, items removed, responses changed, warnings touched, numeric values
changed — with numeric and warning changes called out separately at the top.
Reviewing a checklist change by reading raw JSON is how a transposed digit gets
merged. This is a small bot and it is worth more to safety than anything in the
schema.

### 2.3 A lossy CSV export of a safety document is not merely lossy — it is dangerous

You propose CSV as "a lossy generated export, not the source of truth." Correct as
far as it goes, but "lossy" is doing too much work in that sentence.

There is a difference between losing *structure* and losing *safety content*. If a
CSV export drops indentation and phase grouping, a user gets an uglier checklist.
If it drops the `warning` rows because they do not fit a column layout, a user gets
a checklist that has silently lost the reason an item exists — and it looks
complete.

So I would make this a hard contract on every generated artifact, not a property of
CSV specifically:

> **Safety-preserving export.** An export must reproduce every `warning`,
> `caution`, and `memory_item` in its original position relative to surrounding
> items, or fail. It may degrade layout, indentation, phase grouping, `detail`
> text, and machine-readable `value` fields freely. It may never silently drop an
> item.

For CSV this determines the shape: **one row per item with a `type` column**, so
warnings and cautions occupy rows like everything else. Never phase-as-column or
challenge/response-as-only-columns, which is the layout most people reach for
first and the one that cannot represent a warning.

This contract also has teeth for the vendor formats. Where a target format cannot
express something safety-relevant — and `memory_item` is expressible in *none* of
the six, since efis-editor's `ChecklistItem` has no equivalent — the exporter must
degrade **visibly**, for instance by prefixing the item text, and the export must
report what it could not carry. Silent degradation into a panel file is the worst
outcome available, because the file then lives in an aircraft with no memory of
what was lost.

### 2.4 "Verified — someone flew behind it" is the wrong top of the ladder

Your three states are `machine`, `reviewed`, `verified`, where `verified` means
someone flew behind it in type. I think the ordering is wrong in a way that matters,
and I have restructured it in
[03-verification-model.md](03-verification-model.md). The short argument:

**Flying behind a checklist cannot detect an omission.** If the transcription
dropped an item — the most likely and most dangerous OCR failure — then flying
behind it feels completely normal. The missing item is invisible precisely because
nothing prompts you to do it. You would only discover it on the day the omitted
check was the one that mattered.

So "flew behind it" is *weaker* evidence of correctness than "two people compared
it against the source document," while your ladder places it above. Worse, a
single ladder means a file can reach the top state by the route that cannot detect
the most dangerous defect class.

These are two independent questions and the model should say so:

- **Does it match the source?** Catches omissions, transpositions, misreadings.
  Established by comparison, ideally by two independent people.
- **Does it work in the aircraft?** Catches items that are correct on paper but
  reference a control this airframe does not have, or an unflyable sequence.
  Established by ground check or by flying it.

Neither implies the other. A faithful copy of a bad checklist passes the first and
fails the second; a well-flown checklist that has drifted from a revised source
passes the second and fails the first. Hence two axes, `source_fidelity` and
`operational_review`, and a `completeness` field because "faithful to its source"
says nothing about whether the file covers the emergency section at all.

---

## 3. Architecture: git, and where git actually breaks

I agree with static files in git, and your reasoning is sound: history,
attribution, review before merge, forking a file you disagree with, and full
function if the site disappears. A database behind a web form gives none of that,
and for a corpus whose central problem is *provenance*, git's audit trail is not a
nice-to-have — it is the primary mechanism. Every claim in a `verification` block
is backed by a signed commit and a reviewable diff. That is very hard to
reconstruct from a database with an admin UI.

I would not argue for a database. I would argue that two problems are real and
neither is solved by choosing git, so both need a plan:

**Search and faceting.** "All Part 103 aircraft with a two-stroke engine and a
reviewed emergency section" is a query, and grep over a thousand files is not an
answer for a website visitor. Solve it with a **generated static index** — a build
step that emits a JSON index of every file's metadata, small enough for the
browser to filter client-side. This keeps git as the only source of truth and
keeps the site static. If the corpus ever outgrows client-side filtering, the index
becomes a search service built *from* git, never a database that git is synced to.

**Contributor friction, which is the real risk to this project.** The person most
likely to have a POH for an unusual type is a pilot or an owner, and that person
will not open a pull request. §3.3 of the research report found four prior projects
that stalled as single-maintainer efforts. Nothing about this project's format or
schema fixes that.

The fix is a web submission path that **opens a pull request on the contributor's
behalf** via a GitHub App — form in, branch and PR out, review in the normal
place. The contributor never sees git; the corpus never leaves it. Build this
earlier than feels necessary. It is more important to the project's survival than
vendor format coverage.

On distribution, I agree that bulk download and a plain HTTP path to every file
matter more than an API, and I would go slightly further: publish a **signed
manifest** listing every file with its SHA-256, and a single tarball of the corpus
per release. That gives downstream consumers — Junco included — a way to verify
they have an unmodified corpus, which matters more than usual when the payload is
safety content and the threat model includes a well-meaning mirror that "fixed"
something.

---

## 4. Licensing

### Corpus: per file, and this is not negotiable

Covered in the research report and repeated here because it is the highest-stakes
recommendation in this document: **a repo-wide CC-BY-4.0 over the corpus would
assert a licence the project does not hold** for every POH-derived file. Rights
live in each file's `rights` block. The validator refuses `unresolved`, and refuses
to publish `upstream_reserved` at all.

- Public-domain-sourced files: `CC0-1.0` on the project's added structure.
- Original-expression files: `CC-BY-4.0`. Your reasoning is right — permissive
  enough that a closed commercial product can adopt it, and a checklist nobody may
  adopt does not get adopted.
- `share-alike` on the corpus would be a mistake for exactly that reason. It would
  keep the corpus out of the panel software people actually fly behind, which is
  the whole point.

### Schema and specification: `CC0-1.0`

The schema needs to be embeddable in anything, including closed products and
firmware, with no attribution obligation attached to a machine-readable artifact
that gets copied into build systems. This matches Junco's own stated reasoning —
"a protocol nobody is allowed to adopt is a protocol nobody adopts" — and Junco
uses CC-BY-4.0 for specifications. I would go one step more permissive for the
schema file itself, because attribution on a JSON file that gets vendored into a
hundred build pipelines is friction with no benefit. CC-BY-4.0 for the prose spec
would be consistent with Junco and is fine.

### Site and tooling: `Apache-2.0`, and here is the constraint

This one is not a matter of taste. **efis-editor is Apache-2.0.** If the export
pipeline links or vendors its format modules, the tooling's licence has to be
compatible with Apache-2.0.

Apache-2.0 is **incompatible with GPL-2.0-only** — the patent and indemnity terms
are additional restrictions GPL-2.0 does not permit. Junco's code is
`GPL-2.0-or-later`, and the "or later" is what saves you: a downstream combination
can be taken to GPL-3.0, which *is* Apache-2.0 compatible. So:

- Open Checklists tooling as **Apache-2.0** can incorporate efis-editor code, and
  Junco can consume Open Checklists tooling by exercising its "or later" option.
- Open Checklists tooling as **GPL-2.0-only** could not use efis-editor at all.
- If you ever want the export pipeline usable inside closed panel software — and
  you probably do, since that is where adoption lives — Apache-2.0 is the choice
  that permits it.

Recommend Apache-2.0 for all code and tooling in this project, and note the
GPL-2.0/Apache-2.0 interaction in Junco's own docs before anyone tries to vendor
the exporter into Junco firmware.

---

## 5. Schema decisions worth flagging

Detail is in [`schema/open-checklist-1.0.schema.json`](../schema/open-checklist-1.0.schema.json);
these are the choices that were not obvious.

**Phase identifiers are a controlled vocabulary, and the project owns it.** You
asked for stable machine-readable phase ids so software can map a phase to a
moment in flight. The schema has 60-odd, covering normal flow plus named abnormal
and emergency situations. Two consequences worth stating explicitly: values are
**append-only and never renamed**, and consumers **must tolerate unknown values**
by treating them as `other` — otherwise adding a phase breaks every deployed
reader. `other` requires a `phase_label`, so it cannot become an untyped dumping
ground. Owning this taxonomy rather than adopting a manufacturer's is also the
design response to *ADA v. Delta Dental*.

**`tickable` is stored explicitly even though it is derivable from `type`.** This
is deliberate redundancy. The requirement is that a warning can never be ticked,
and the failure mode is a consumer that does not implement the type table
correctly. Storing the boolean means the naive consumer — the one that renders a
checkbox whenever `tickable` is true — is safe by default. The schema pins the
value so it can never contradict the type, and the policy layer requires it to be
present.

**`memory_item` is first-class, and no vendor format can carry it.** Whether an
action is performed from memory before reaching for the checklist is
safety-significant, and none of the six formats represents it. Adding it here is
part of the argument for this project existing: it carries things the vendor
artifacts structurally cannot.

**`value` is separate from `response`.** `response` is the human-readable string
("2,000 RPM"); `value` is the machine-comparable form. Junco can compare a sensed
value against `value` without parsing prose, and the prose stays authoritative for
the pilot.

**`source_confidence` is per item, not per file.** OCR confidence is not uniform
across a document, and a per-file average hides the one line that was ambiguous.
Per-item confidence lets the reviewer's attention be directed, and lets the policy
layer block promotion while any item is below threshold.

**`indent` is structural, not cosmetic.** Bounded to 0–4 and validated as
gap-free, because an item indented under nothing has no meaning. This maps onto
efis-editor's `indent` for export, but the intent here is subordination rather
than layout — the corpus should not carry presentation, and `centered` deliberately
has no equivalent.

**One file per aircraft type or variant, matching `ChecklistFile`'s granularity.**
`aircraft.airframe_specific` exists for the case where a file documents one
individual aircraft, which is the common case in experimental and Part 103 where no
two builds are alike. Type-level files must omit it. Per-airframe overlays that
inherit from a type file are a plausible future need and deliberately out of scope
for 1.0 — inheritance in a safety document is a way to make it unclear what the
pilot is actually holding.

**Round-tripping with efis-editor is deliberately asymmetric.** Open Checklist →
`ChecklistFile` is straightforward, losing provenance, verification, phase ids,
`memory_item`, and `value`. `ChecklistFile` → Open Checklist cannot be fully
automated, because phase ids and provenance are not present in the source and must
not be guessed. Imports should land as `source_fidelity: unreviewed` with
`transcription.method: format_conversion`, phases assigned by a human. Treating an
import as trustworthy because it came from a working panel file would defeat the
verification model on day one.
