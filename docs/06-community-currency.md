# Community currency, and the legal premise

Written in response to: *these are checklists, not text that is copyrighted unless
it's actually published in a book — no different from somebody typing this up into
Word for personal use and then sharing it with everyone in their flight club.*

Two of your points are right and change what this project should build. One premise
is wrong in a way that matters. And the flight-club analogy breaks in one specific
place, which is narrower than my earlier documents implied.

---

## 1. Where you are right

**Staleness parity.** You are correct, and my currency argument in
[05-product-and-sourcing.md §4](05-product-and-sourcing.md) overreached if it read
as a claim that freechecklists is stale and you would not be. It is not. That
section was about why *manufacturers* control distribution — their reasoning, not a
comparison against the incumbent. Against freechecklists specifically, a
transcription you make today from the same POH is exactly as current as theirs.
Staleness is not a differentiator between you and them.

**Community reporting is the real differentiator, and it is a good idea.** This is
the strongest thing in your message. A PDF library has no way to learn that one of
its files is wrong. Nobody can tell freechecklists that page 2 of a Cherokee
checklist no longer matches the POH, and if they could, there would be no mechanism
to propagate the fix. A repository where readers can report a stale item, and where
the report is attached to the exact version they were looking at, is better than a
PDF dump in a way that has nothing to do with format elegance.

So I built it — see §4 below. It did not exist in the proposal before your message,
and it should have.

**The empirical enforcement risk is low.** I said this in the research report and it
is worth restating because it cuts your way: I found no reported case about
copyright in an aircraft checklist, and no evidence of any free checklist repository
being taken down by a manufacturer. freechecklists has run for years with 760
resources. That is real evidence about practical risk, and it would be dishonest of
me to keep flagging legal exposure without saying that the observed enforcement rate
is approximately zero.

"Someone else does it" is not a legal defence. But "this activity has gone on
publicly for two decades without enforcement" is genuine information about how
likely you are to have a problem. Both things are true at once.

---

## 2. The premise that is wrong

> these are checklists, not text that is copyrighted unless it's actually published
> in a book

This one I have to correct plainly, because it points the wrong way on exactly the
question that matters.

**Copyright attaches automatically on fixation.** Since 1 January 1978, a work is
protected the moment it is written down in tangible form. No publication, no
registration, no copyright notice, and no book required. A manufacturer's POH is
copyrighted from the moment it exists, whether it is a printed book, a PDF, or a
Word file on an engineer's laptop.

The "book" intuition inverts the actual rule. Publication formalities mattered under
the *old* law: before 1978, publishing *without* a notice could forfeit copyright,
and before 1964 you had to renew. That is why
[01-legal-research.md §1.4](01-legal-research.md) treats those as public-domain
lanes. Formal publication is where old copyrights were *lost*, not where copyright
is gained.

None of that defeats your underlying point, which has a better foundation available.
The real argument is not "it was never copyrighted." It is:

- §102(b) excludes procedures, processes and methods of operation from protection.
- Under the recipe cases, a functional list and its imperative steps are facts and
  functional directions, not protected expression.
- The merger doctrine means "Fuel selector — BOTH" has almost no authorial room in
  it, so the expression merges with the idea.

That argument is genuinely strong and it is the one this project should stand on.
The document is copyrighted; much of what you want out of it is not protected by
that copyright. Those are different claims, and the second one survives scrutiny
while the first does not.

The part that stays risky is not the item text. It is the **selection and
arrangement** — which checks a manufacturer chose to include and how they grouped
them — because that is what compilation copyright protects, and *ADA v. Delta
Dental* shows a structured taxonomy can be protected even in the circuit that
decided the recipe case. Which is why the operative rule stays: transcribe the
facts, do not clone the document.

---

## 3. Where the flight-club analogy breaks

> no different than somebody having to type this up into Microsoft Word for their
> own personal use and then sharing it with everyone in their flight club

Take this in three steps, because the first two are fine and only the third moves.

**Typing it up yourself is not the problem — it is the recommended posture.** This
is worth being clear about, because it means we agree more than my earlier documents
suggested. A person reading a POH and typing their own checklist is producing
independent expression of unprotected procedure. That is precisely what
`rights.status: original_expression` means in the schema, and what
`examples/cessna-172n-normal.ocl.json` demonstrates. Nothing in this proposal
discourages it. It is the main way the corpus should be built for types whose POH is
still in copyright.

**Personal use is on very strong ground.** Nobody has ever been sued for making
their own checklist.

**Sharing with your flight club is plausible.** Limited, defined group,
non-commercial, no substitution for a market — the classic fair-use shape.

**Publishing a permanent public library changes the analysis, and the thing that
changes is distribution, not authorship.** Fair use weighs the effect on the market
for the original: a file behind a flight club's door does not displace anything,
while a free, indexed, permanent, machine-readable library of the same content
plausibly does — and Textron does sell publications. Scale and publicness are what
move, not the act of typing.

The parallel: photocopying a book chapter for your own study is fine, and handing
copies to your study group is usually fine. Posting the chapter online for anyone
forever is a different question, and it is a different question even though the
photocopier was the same.

So the honest position is not "your analogy is wrong." It is that the analogy
carries you through the authoring step and stops at the publishing step — and the
publishing step is the whole project.

---

## 4. What I built: field reports

Your differentiator, made concrete. New in this commit:

- `schema/open-checklist-report-1.0.schema.json`
- `tools/validate_report.py`, `tools/test_reports.py` (14 cases, all behaving)
- two worked reports against the T-34A file in `examples/`

A report is structured rather than free text for one reason: **a comment thread
cannot demote a file, and a report can.** That is the entire difference between "we
allow comments" and "the corpus stays current."

Report types: `transcription_error`, `stale_item`, `source_revision_available`,
`airframe_variation`, `procedural_concern`, `rights_concern`, `improvement`.

Three enforced rules give it teeth:

**A report names the exact version it is about.** `target.content_hash` pins the
version the reporter was reading. Without it, "item 4 is wrong" becomes unanswerable
the moment the file changes. It also means a report against a superseded version is
automatically recognised as history rather than a live defect.

**A confirmed defect costs the file its badge.** If a `transcription_error` or
`stale_item` is confirmed against the current version of a file that claims
`single_reviewed` or `dual_reviewed`, the validator errors unless the resolution
records `demoted_verification`. A review of content now known to be wrong is not
evidence of anything, and leaving the badge up is worse than never having reviewed
it. The negative tests prove both directions: the rule fires, and it accepts the
case once the demotion is recorded.

**A live safety concern travels inside the file.** An open or confirmed
`safety_critical` report against the current version requires a matching
`safety_defect` entry in the file's own `known_issues`. Otherwise the concern exists
only on a website and is lost the instant someone downloads the JSON or prints the
PDF — which is exactly the failure mode you are trying to fix.

Plus: a staleness claim must identify what superseded the source; a transcription
error must quote what the file currently says; an airframe variation must identify
the aircraft; and a closed report must say who closed it and why, so concerns cannot
be quietly dismissed.

The reporter's `relationship` field (`owner`, `mechanic`, `instructor`, `type_club`,
`manufacturer`, `reader`) exists because an owner reporting on their own aircraft
carries different weight from an anonymous reader, and a maintainer should be able to
see which they are without asking.

### Why this is worth more than it looks

It changes what the verification model is for. Before, verification was a static
judgement made once at transcription. With reports, it becomes a **live** state that
degrades when someone finds a problem and recovers when the problem is fixed. That
is the thing a PDF library structurally cannot do, and it is a better answer to
"how do you stay current" than anything about file formats.

It is also the honest answer to the manufacturers' revision-control objection in
[05 §4](05-product-and-sourcing.md): not "we will never be stale", but "when we are
stale, anyone can say so, the file's badge drops, and every downstream copy can tell."

---

## 5. Where the disagreement actually sits

Narrower than these documents have made it look. To be explicit about what I am
*not* saying:

- Not that you should not build this.
- Not that transcribing checklists from POHs is off limits. Write the wording
  yourself, copy the facts, and that is `original_expression` — a supported,
  recommended path.
- Not that the corpus cannot end up covering the same aircraft freechecklists
  covers. It can and should. Re-deriving a Cherokee checklist from a Cherokee POH is
  legitimate whether or not somebody else already published one.

The one thing I still will not do is **bulk-copy another site's files**, and that
one is not really a copyright judgement. freechecklists' terms forbid copying their
material onto another web page, in those words. That is their stated condition,
independent of whether the underlying procedures are protectable — and it would
still be their condition if every file on the site were public domain. The refusal is
encoded in `tools/acquire.py`'s denylist with the reason attached.

The practical cost of that position is close to zero, because the same coverage is
reachable by transcribing from source documents, and the result has clean provenance
per file instead of 760 files that all say "found on the internet."
