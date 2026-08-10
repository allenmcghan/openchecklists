# The verification and provenance model

The requirement, in your words: *an unreviewed file can never be mistaken for a
verified one, and if that means machine-only files are harder to download, good.*

This document specifies how. It restructures your three states into two axes for
the reason argued in [02-format-decision.md §2.4](02-format-decision.md), then
defines the evidence each state requires, the rules for promotion and automatic
demotion, and the presentation rules that make the state impossible to lose.

---

## 1. Two axes, not one ladder

```
                        source_fidelity  ────────────────────────────────►
                        unreviewed        single_reviewed    dual_reviewed
                     ┌──────────────────┬─────────────────┬─────────────────┐
  operational   none │ machine output   │ checked once    │ checked twice   │
  _review            │ QUARANTINE       │ usable          │ trusted         │
                     ├──────────────────┼─────────────────┼─────────────────┤
     ground_checked  │ QUARANTINE       │ usable          │ trusted         │
                     ├──────────────────┼─────────────────┼─────────────────┤
              flown  │ QUARANTINE       │ usable          │ trusted         │
                     └──────────────────┴─────────────────┴─────────────────┘
```

The shape of that table is the argument. **Operational review never lifts a file
out of quarantine.** No amount of flying behind a machine transcription makes it
trustworthy, because the defect class that matters most — a dropped item — is
undetectable in flight. Nothing prompts you to do the missing check, so the flight
feels entirely normal. Operational review adds confidence on a separate dimension;
it is not a substitute for having compared the file against its source.

That single asymmetry is the most important thing in this document, and it is the
thing your original three-state ladder gets wrong.

### `source_fidelity` — does it match the source?

Catches omissions, transpositions, misread digits, and OCR substitutions.

| State | Meaning | Evidence required |
| --- | --- | --- |
| `unreviewed` | Machine or first-pass output. Nobody has compared it to the source. | none |
| `single_reviewed` | One person, not the transcriber, compared it line by line against the source document. | ≥1 `source_comparison` review record |
| `dual_reviewed` | Two people did so independently, without seeing each other's result. | ≥2 `source_comparison` records from distinct reviewers |
| `not_applicable` | There is no source document. Content is authored. | `provenance.source.kind` must be `none` |

`not_applicable` is not a way to skip review — it is the honest state for Part 103
and much of experimental, where no approved flight manual exists to compare
against (research report §3.5). For those files, fidelity is not measurable and
`operational_review` carries the entire weight. They should be presented
differently from certified-type files, not folded in with them.

### `operational_review` — does it work in the aircraft?

Catches items that are right on paper but reference a control this airframe does
not have, use a name the panel does not use, or sequence in a way that cannot be
flown.

| State | Meaning | Evidence required |
| --- | --- | --- |
| `none` | Never exercised against a real aircraft. | none |
| `ground_checked` | Walked through in the actual cockpit; every control located and matching its name in the file. | ≥1 `ground_check` review record |
| `flown` | Flown behind in this type. | ≥1 `flight_check` review record |

`ground_checked` is the underrated state and the one to push contributors toward.
It is cheap, it needs no flight, and it catches the entire class of "this file is
for a 172N but the aircraft has a different switch layout" — which is more common
in the corpus's target aircraft than any subtle procedural error.

### `completeness` — is any of it missing?

Fidelity says the content present is faithful. It says nothing about content that
was never transcribed. A file can be `dual_reviewed` and still have no emergency
section at all, and a reader has no way to see that absence.

`full`, `normal_only`, `partial`, `excerpt`. A file that is anything other than
`full` must say so wherever it is presented, because **a missing emergency section
is invisible to the person holding the file.** Of the four example files in this
proposal, none is `full`, and all say so.

---

## 2. Evidence, not assertion

The failure mode for any labelling scheme is that the label becomes something
people type. Every state above therefore requires a corresponding record in
`verification.reviews`, and the policy validator enforces it.

```json
{
  "type": "source_comparison",
  "reviewer": "A. Reviewer",
  "date": "2026-08-01",
  "source_used": "Cessna 172N POH, revision 3, 1979",
  "content_hash": "3f9a...c17"
}
```

Four rules the reference validator enforces, each with a negative test:

**Reviewer independence.** A contributor listed with role `transcriber` cannot be
the reviewer of their own file. Proof-reading your own transcription reproduces
your own misreadings; this is exactly why dual review in safety-critical
transcription is independent.

**Dual means two distinct people.** `dual_reviewed` with two review records naming
the same person is rejected.

**`source_used` is recorded, and revisions must match.** A reviewer who compared
against a different POH revision than the transcriber used has not confirmed the
file — they have found a discrepancy in the corpus. Recording the document each
party held is what makes that detectable at all.

**Low-confidence items block promotion.** Any item with
`source_confidence` below the threshold (0.98 in the reference implementation) is
an unresolved question, and the file cannot leave `unreviewed` while one exists.
This is the mechanism that makes per-item OCR confidence do real work rather than
being decoration.

### Automatic demotion

`content_hash` on each review is the SHA-256 of the canonical serialization of the
file with the `verification` block removed — excluded because otherwise recording
a review would invalidate the hash it contains.

A review covers the content that existed when it was made. If the content changes,
the review no longer covers it. Tooling compares the stored hash against the
current content and demotes the affected axis automatically.

**This is the mechanism that stops the corpus rotting.** Without it, the natural
lifecycle of a reviewed file is: get reviewed, accumulate small edits, and remain
labelled `dual_reviewed` forever on the strength of a review of content that no
longer exists. Demotion has to be mechanical, because nobody will volunteer to
downgrade their own file.

The reference implementation reports hash mismatch as a warning today. In CI it
should rewrite the state, so that a pull request touching a reviewed file shows the
demotion in its own diff and the reviewer sees the cost of the change.

### Reviews can be withdrawn

A review is a claim by a named person, not a permanent property of the file. If a
reviewer later finds they were wrong, the record must be removable and the state
must fall accordingly. Nothing in the model treats verification as a ratchet.

---

## 3. Presentation rules

State that lives only on a web page is state that is lost the moment the file is
downloaded. These rules are the substance of "can never be mistaken."

### The quarantine rule

A file with `source_fidelity: unreviewed` is **quarantined**:

1. **Not exported to any vendor panel format.** No `.ace`, `.gplt`, `.fmd`, no
   Dynon, AFS or GRT output. This is the sharpest version of your "harder to
   download, good": a quarantined file cannot become a file in an aircraft,
   because a panel file has no room to carry a warning label and the panel UI will
   not show one.
2. **JSON and PDF downloads are available**, because review requires people to be
   able to read the thing, and hiding it prevents the review that would fix it.
3. **Download requires an explicit acknowledgement**, not a passive notice.
4. **Every artifact carries the state in its filename**:
   `cessna-172n-normal.UNREVIEWED.pdf`. The filename is what survives being
   emailed, printed, and found on a hangar computer in two years.
5. **Generated PDFs carry a visible watermark on every page**, plus a header line
   stating the state, the source document, and the generation date. Not a footnote
   on page one — every page, because checklist pages get separated.
6. **Excluded from the default corpus bundle.** The release tarball ships reviewed
   content; quarantined files ship in a separate `unreviewed/` bundle that a
   consumer has to ask for.

### Labelling everywhere else

- Listings, search results, and file pages show both axes, always, with no
  "verified" shorthand that collapses them.
- Avoid the words **approved**, **official**, **current**, and **airworthy**
  anywhere in the site or the generated artifacts. None is true of anything in this
  corpus, and each is the word a court would read back to you.
- `completeness` is displayed next to fidelity, since a `dual_reviewed`
  `normal_only` file is a trap without it.
- An unresolved `safety_defect` in `known_issues` suppresses all export and shows
  above the checklist content, not below it.
- The `verification` block travels inside every JSON file. It is not site metadata.

### What this model does not do

Worth stating so nobody mistakes its scope:

- It does not make the corpus safe to fly behind. It records what is known about
  each file so a pilot can decide.
- It does not verify credentials. `contributors[].credentials` is free text and the
  project never checks it. A reviewer claiming to be a CFI may not be.
- It does not defend against a determined bad actor. Someone willing to fabricate
  review records with plausible names can raise a file's state. The defences are
  git history, signed commits, and human review of pull requests — not the schema.
- It does not detect a file that is faithful to a **superseded** source revision.
  `source.revision` records what was used; noticing that a newer revision exists is
  a corpus maintenance task with no automated answer.

---

## 4. Provenance

Provenance answers two different questions with one block: *can this be trusted*
and *may this be redistributed*. Both need the same facts.

**`source`** — the document, identified well enough that a reviewer can obtain the
same one: `kind`, `title`, `publisher`, `document_number`, `revision`,
`publication_date`, `pages`, `url`, `retrieved`. `title` is required whenever
`kind` is anything other than `none` or `unknown`, because a source you cannot
name is a source nobody can review against.

`kind` is the field that drives the rights analysis, which is why it is an
enumeration rather than free text. `government_publication` opens the § 105 lane.
`manufacturer_poh` flags the file for the analysis in the research report.
`simulator_product` is **rejected outright** by the validator — see research report
§3.4, where a search for a J-3 POH returned a flight-simulator manual that would
have transcribed cleanly and been entirely wrong to include.

**`transcription`** — `method` (`ocr_raw`, `ocr_assisted`, `manual_transcription`,
`authored`, `format_conversion`), `tool`, `date`. `tool` is required for OCR
methods, and the reason is operational rather than bureaucratic: when a systematic
error in one model version is discovered, you need to know which files to re-run.
Without the tool recorded, the answer is "all of them."

**`contributors`** — at least one, with roles. Presence here asserts the
contributor accepted the warranty below.

**`revision`** — the file's own version, distinct from the source's. `supersedes`
links a replaced file, so a stale copy in circulation can be traced forward.

### Contributor warranty

Every contributor asserts, per submission:

1. They have the right to submit the content, and submitting it does not breach an
   agreement or licence binding them.
2. They have accurately stated the source document and the transcription method.
3. Where they claim public domain status, they state the basis and what they
   checked.
4. They have not copied wording, selection, or arrangement from a copyrighted
   source beyond what is stated in `rights`.
5. They understand the content will be redistributed under the file's stated
   licence and that the project makes no warranty of fitness.

This belongs in `CONTRIBUTING.md` with a Developer Certificate of Origin-style
sign-off in every commit, so the assertion is in git history against a specific
change rather than in an account checkbox somewhere.

### Takedown process

Designed to be usable before it is needed, because the moment it is needed is the
moment you have no time to design it.

1. **A published contact and a named responsible person.** Not a form.
2. **Acknowledge within 72 hours**, stating what happens next.
3. **Unpublish first, argue second.** Remove from the site and the bundles
   immediately on a good-faith claim. The cost of unpublishing a checklist for two
   weeks is low; the cost of a contested takedown while it stays up is not. This is
   only tolerable because git preserves the history — nothing is destroyed by
   unpublishing.
4. **Assess against the rules in the research report**, and record the outcome in
   a public log: what was claimed, what was decided, why.
5. **Notify the contributor**, who may respond. Their warranty is what makes this
   a matter between the claimant, the project, and the contributor rather than the
   project alone.
6. **Fix the class, not the instance.** If one file was wrong about its source, the
   others transcribed by the same contributor from the same document are suspect.
7. **Never restore silently.** A restoration gets its own log entry.

The public log matters more than it looks. It is how the project accumulates a
record of where the line actually is, and it makes each subsequent claim cheaper
to handle.
