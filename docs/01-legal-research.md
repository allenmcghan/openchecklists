# Research: rights, liability, and the existing landscape

Status: research report for project kickoff. Not legal advice; I am not a lawyer.
Everything here needs a review by counsel licensed in your jurisdiction before it
becomes policy. Where I could not find support for a proposition, I say so rather
than rounding it up to a conclusion.

---

## Bottom line

Four findings, in order of how much they should change the plan.

1. **The biggest legal risk in this project is not copyright. It is product
   liability.** US courts have repeatedly treated aeronautical charts as
   *products* subject to strict liability, and have distinguished them from books
   precisely because a chart is a tool used in flight rather than an expression of
   ideas. A checklist is closer to a chart than to a book. This risk is not
   addressed by a licence, a disclaimer, or a verification badge, and it is not
   mentioned anywhere in the kickoff. It is the reason to form an entity before
   the corpus grows, not after.

2. **A blanket CC-BY-4.0 licence on the whole corpus would be a false statement**
   for any file derived from a manufacturer's POH. You cannot license text you do
   not own. This is the single most dangerous line in the kickoff document, and it
   is dangerous in a way that grows silently: by the time there are five hundred
   files, a repo-wide `LICENSE` has made five hundred untrue assertions. Rights
   must be per file, which is why the schema has a `rights` block and the
   validator refuses to publish a file whose rights are unresolved.

3. **The copyright line is real but narrower than "checklists are procedures, so
   they are free."** The doctrine supports copying *what to do* as fact. It does
   not support reproducing a manufacturer's *wording, selection, and arrangement*.
   The operative rule for this project: **transcribe the facts; do not clone the
   document.** There is no case law on aircraft checklists specifically — the
   closest authority is about recipes, and the counterweight is about medical and
   dental procedure taxonomies.

4. **There is a clean public-domain seed corpus available immediately, and the
   kickoff does not mention it.** FAA handbooks and US military flight manuals are
   works of the US Government and carry no copyright at all. Seeding from those
   first gets real content into the repo with zero rights exposure, and builds the
   pipeline against documents nobody can complain about. One of the four example
   files in this proposal is built this way.

---

## 1. Copyright

### 1.1 The doctrine that helps

**17 U.S.C. § 102(b)** excludes from copyright any "idea, procedure, process,
system, method of operation" regardless of the form in which it is described. This
codifies **Baker v. Selden**, 101 U.S. 99 (1879), where the Supreme Court held
that copyright in a book explaining a bookkeeping system did not give its owner
the exclusive right to use that system or to make account books on its plan.
Baker is also the origin of the **blank forms rule**, now at **37 C.F.R.
§ 202.1(c)**: blank forms "designed for recording information [that] do not in
themselves convey information" are not copyrightable subject matter.

A checklist sits awkwardly across that line. It is partly a blank form — a thing
you tick — and partly a document that conveys information. The regulation's own
carve-out is the problem: where forms "convey information in a creative manner,"
or where a form is integrated with instructions into a unified work, there is
protection for the original elements. A printed checklist card is closer to that
carve-out than to graph paper.

The **merger doctrine** helps more. Where there is only one, or a very limited
number, of ways to express something functional, the expression merges with the
idea and neither is protected. "Fuel selector — BOTH" is close to the only way to
say that. There is very little authorial room in a challenge/response pair, and
that is the strongest argument this project has for item-level text.

The closest real authority is about **recipes**. In **Publications
International, Ltd. v. Meredith Corp.**, 88 F.3d 473 (7th Cir. 1996), the Seventh
Circuit vacated an injunction against a cookbook that copied recipes, holding that
a functional list of ingredients is a statement of fact and that recipe
directions are functional directions excluded by § 102(b). Copyright in the
cookbook protected the compilation, not the individual recipes.

The parallel to a checklist is close and useful. A recipe is: a list of things,
plus an ordered sequence of imperative steps, aimed at a physical outcome. So is a
checklist. If a recipe's ingredient list and steps are unprotected facts and
functional directions, a checklist's items and their order are on the same footing.

### 1.2 The doctrine that hurts

Three things cut the other way, and the project should design around them rather
than hope.

**Compilation copyright is real, just thin.** *Feist* establishes that a
compilation of unprotectable facts can still be protected in its *selection,
coordination, and arrangement* where those reflect a modicum of creativity. This
is exactly what a checklist is: a selection of which of the hundreds of possible
checks to include, and an arrangement of them. The recipe case says the same
thing from the other side — the cookbook's compilation *was* protected. So
copying one item from a POH is safe in a way that copying a POH's entire Section 4
in its own order and grouping is not.

**A taxonomy can be copyrightable — decided by the same circuit.** In **American
Dental Association v. Delta Dental Plans Association**, 126 F.3d 977 (7th Cir.
1997), the Seventh Circuit reversed a holding that no taxonomy may be copyrighted,
and found the ADA's Code on Dental Procedures and Nomenclature — numbers, short
descriptions, and long descriptions — to be copyrightable subject matter. The
Ninth Circuit reached a comparable result for the AMA's CPT codes in *Practice
Management Information Corp. v. AMA*.

This is the most important adverse authority for this project, and it is
important because it comes from the *same court* that decided the recipe case a
year earlier. That court's implicit line is: functional directions and factual
lists, no; a structured classification of a field of knowledge, yes. A
manufacturer's organisational scheme for its procedures — which phases exist,
what they are called, which checks belong to which — looks more like the ADA Code
than like an ingredient list.

The practical consequence is a design rule, and it is the reason this proposal
defines its **own** phase vocabulary rather than adopting any manufacturer's
sectioning: the project should own its taxonomy, and treat a source document's
arrangement as something to be re-derived rather than imported.

**Nothing here has been litigated on aircraft checklists.** I could not find a
single reported US case about copyright in an aircraft checklist or a POH
procedures section, in either direction. I also could not find evidence of any
free checklist repository being taken down by a manufacturer — the practical
enforcement rate appears to be very low. Absence of reported enforcement is worth
knowing, but it is not a safe harbour and must not be the plan.

### 1.3 The operative rule

Stated so a contributor can apply it without a lawyer:

> **Transcribe the facts. Do not clone the document.**
>
> - Copy *what to do*: which control, which position, which value, in which order.
> - Write the item text yourself where the source's phrasing has any room in it.
> - Do not reproduce the source's prose, cautions and notes verbatim, its section
>   titles, its grouping, or its layout.
> - Do not transcribe explanatory narrative at all. If it takes a paragraph, it
>   is not a checklist item.
> - Numeric limitations are pure fact and should be copied exactly. Getting a
>   V-speed "creatively different" is how this project kills someone.

Two of the four example files in this proposal demonstrate this posture, and both
deliberately omit airspeeds and power settings rather than invent them.

### 1.4 The public-domain lanes, in priority order

These are where the project should spend its first year of transcription effort.

| Lane | Basis | Notes |
| --- | --- | --- |
| **US Government works** | 17 U.S.C. § 105 | No copyright at all, published or not. FAA handbooks, ACs, and the Airplane Flying Handbook. US military flight manuals and technical orders prepared by government employees. **Caveat:** works prepared by *contractors* are not automatically § 105 works, and much military technical data was contractor-authored. Check the authorship statement. |
| **Published pre-1978 without notice** | 1909 Act formalities | Publication without a compliant notice forfeited copyright outright. Many owner's manuals from small manufacturers were published without notice. |
| **Pre-1964, renewal not filed** | 1909 Act renewal | Copyright lapsed if not renewed in the 28th year. Renewal rates were low. Checkable in Copyright Office records. |
| **1978 to 1 March 1989, notice omitted** | 1976 Act as enacted | Public domain *unless* registered within five years of publication and reasonable effort was made to add notice to copies distributed after discovery. Most such works were never registered — but this lane requires an actual records check, not an assumption. |
| **Term expired** | Duration | Reliable only for genuinely old material. |
| **Dedicated by the owner** | Grant | Some kit manufacturers and type clubs will say yes if asked. Nobody has asked. |

The 1985-manual-from-a-1987-dissolved-manufacturer case the kickoff raises is
mostly the **notice and renewal** lanes, not the dissolution. Dissolution of the
company does not extinguish the copyright — it becomes an asset, and orphan-work
status is a practical obstacle to enforcement rather than a legal defence. The
US has no orphan-works exception. The defensible ground is that the *formalities*
failed, and that is a records question with a checkable answer.

A rights research note per file, recording which lane and what was checked, is
worth more than any amount of disclaimer text. That is what `rights.public_domain_basis`
is for, and the validator requires it.

### 1.5 What "fair use" is and is not good for

Fair use is a defence, not a permission, and it is assessed per use. For a project
whose entire purpose is to redistribute complete substitutes for the original,
factor four (market effect) is bad and factor three (amount taken) is bad. Fair
use may well cover *transcribing a POH privately to make a checklist for your own
aircraft*. It is a weak foundation for *publishing a library of them*. Do not
build the posture on it.

---

## 2. The risk the kickoff missed: product liability

This deserves its own heading because it is larger than the copyright question and
is structurally different: it is not solved by provenance, licensing, or takedown
process.

Several US jurisdictions have held that **aeronautical charts are "products"** for
strict product liability purposes, so that a defect in the information can support
liability without proof of negligence. The line runs through *Brocklesby v. United
States*, *Aetna Casualty & Surety Co. v. Jeppesen & Co.*, *Saloomey v. Jeppesen &
Co.*, and *Fluor Corp. v. Jeppesen & Co.*

The important case for this project is the one that went the *other* way.
In **Winter v. G.P. Putnam's Sons**, 938 F.2d 1033 (9th Cir. 1991), mushroom
foragers were poisoned after relying on an encyclopedia. The Ninth Circuit refused
to apply strict liability to the book, holding that products liability is aimed at
tangible items and that ideas and expression are outside it. But it expressly
**distinguished the aeronautical chart cases**, reasoning that a chart is a tool
used in navigation, whereas the book was more like a guide about how to use such
tools.

An aircraft checklist is a tool used in the operation of the aircraft. It is on
the chart side of that line, not the encyclopedia side. And a machine-readable
checklist that loads into a panel and is ticked in flight is further onto the
chart side than a printed card is.

What follows from this:

- **A licence disclaimer does not defeat a strict liability claim by a third
  party.** CC-BY-4.0 disclaims warranties between the project and its licensee. It
  says nothing to the estate of a passenger who was not party to it.
- **Form an entity before the corpus grows.** An LLC does not make the risk
  disappear, but it determines whose house is at stake. Do this before the first
  hundred files, not after.
- **Get a view on insurance early.** Aviation media/publisher liability is a real
  product; the premium quote is also the cheapest expert assessment of this risk
  you will ever get.
- **Structural choices matter more than words.** Never describe a file as
  "approved", "official", "current", or "airworthy". Do not present generated
  panel-loadable files as ready to fly. Keep the verification state attached to
  the artifact itself, not just to the web page, so it survives download. The
  verification model exists partly for this reason.
- **The most dangerous artifact this project can produce is a beautifully
  formatted PDF or a panel file with no visible provenance**, because that is the
  form in which a checklist gets used with no memory of where it came from. This
  is an argument for embedding provenance in every generated output, including the
  vendor binaries where the format allows it.

I want to be careful not to overstate this. Nobody has sued a free checklist
repository that I can find, and the chart cases involved commercial publishers
selling navigation data to professional users. But the doctrinal path from
*Brocklesby* to a machine-readable checklist library is short, and it is not
addressed by anything currently in the plan.

---

## 3. The existing landscape

### 3.1 efis-editor — verified in detail

I cloned it and read the data model rather than relying on the description, because
the whole export strategy depends on what is actually there.

`src/model/proto/checklist.proto` defines:

```
ChecklistFile  → metadata (name, make_and_model, aircraft_info,
                           manufacturer_info, copyright_info, modified_time,
                           default_group_index, default_checklist_index)
               → groups[]
ChecklistGroup → title, category {unknown|normal|abnormal|emergency}, checklists[]
Checklist      → title, completion_action, items[]
ChecklistItem  → prompt, expectation, indent, centered,
                 type {UNKNOWN|CHALLENGE|CHALLENGE_RESPONSE|TITLE|PLAINTEXT|
                       WARNING|CAUTION|NOTE|SPACE}
```

Three conclusions, all of which shaped the schema proposal:

**It is a presentation model, not a semantic one.** Items carry `indent` and
`centered`; groups carry a title. There is no phase identifier, so nothing in the
file tells software that a checklist corresponds to "before takeoff" other than a
human-typed title string. This is the single most important thing Open Checklists
must add, and it is exactly what Junco needs in order to map a checklist to a
moment in flight.

**It has no provenance and no verification.** The only rights-adjacent field is
`copyright_info`, a free-text string. There is nowhere to record what document a
file came from, who transcribed it, or whether anyone checked it. A format with no
verification state cannot distinguish machine output from reviewed content, which
is the project's central safety requirement.

**Its item types match the kickoff's requirement almost exactly.** `WARNING`,
`CAUTION`, `NOTE`, `TITLE`, `PLAINTEXT`, `SPACE`, `CHALLENGE`, and
`CHALLENGE_RESPONSE` map cleanly onto the proposed type set. This is good news for
interoperability and is evidence the kickoff's item-type instinct is right.

**On using it as the export engine — it is viable but it is not free.** I checked:

- The `package.json` has no `bin` and no `main`. It is an Angular application, not
  a published library. There is no CLI and nothing on npm to depend on.
- However, the format layer is clean: **no non-spec file under
  `src/model/formats/` imports `@angular`**. The reader/writer interface is
  `toProto(file: File)` / `fromProto(file): Promise<File>` — Web platform types,
  not DOM.
- The only genuine browser dependency in the format code is `window.crypto` in
  `crypto-utils.ts` and `foreflight-utils.ts`. Node 22 provides `File`, `Blob`,
  and `crypto.subtle` natively, so this is a one-line shim.

So the realistic plan is a small Node harness over a pinned checkout of the format
modules, and the honest estimate is days of work plus ongoing breakage when
upstream refactors, not an afternoon. The best outcome for everyone is to
contribute a CLI entry point upstream so the harness becomes a supported
interface. Ask before building around it; a maintainer who knows you depend on the
format layer is likely to keep it importable.

One legal note on the export path. At least one Garmin Pilot variant is
encrypted, and efis-editor contains the key material to read and write it.
Distributing a tool that decrypts a vendor's protected format raises **DMCA
§ 1201** questions. The § 1201(f) interoperability exemption exists and is a real
defence, but it is drafted narrowly — it covers reverse engineering to achieve
interoperability of an independently created program, by someone who lawfully
obtained the product, and limits what may be shared. Generating an encrypted file
for a user's own use is a better position than shipping a decryptor as a service.
My recommendation: keep vendor-format export as a client-side or local-tool step,
defer the encrypted Garmin Pilot format to last, and put this specific question to
counsel. Do not let it block the other five formats.

### 3.2 Free repositories

**freechecklists.net** — the incumbent. Advertised as the web's largest
collection, Cessna 150 through Boeing 747. PDF only. It returned HTTP 503 on both
attempts while I was writing this, which is itself the argument for static files
in a git repository: a single-host PDF library is one hosting lapse from
disappearing, and nothing in it can be mirrored usefully by machine because
nothing in it is machine-readable. Confirm its terms of use directly before
treating any of it as a source; I could not reach them.

**Other free sources** are simulator-community libraries (AVSIM, SimViation),
generic safety-checklist sites, and PDF-generator tools such as
`checklist.aerobreak.com`. None is machine-readable in a way software can consume,
and see the warning in §3.4 about the simulator material.

### 3.3 Prior open-source projects the kickoff missed

These matter because they are evidence about what happens to this idea.

- **`freerobby/aviation-checklist`** — "maintain aviation checklists in one place,
  while exporting to every format you need." Roughly the same premise as Open
  Checklists. A Vue application, ~47 commits, ~20 stars. Not archived.
- **`mofo/checklist-creator`** — JSON input, ForeFlight output. Metadata plus
  groups plus items: the same shape everyone independently arrives at.
- **`MaggieLeber/checklist`** — renders Garmin Pilot checklists to printable HTML
  and to Garmin ACE, working from the undocumented binary format. Predates
  efis-editor's coverage.
- **`dpwiese/checklists`** — Make plus Pandoc, HTML and CSS to PDF. A build
  pipeline rather than a format.

The pattern is the informative part. **At least four people have independently
built a "one source, many exports" checklist tool, and each stalled as a
single-maintainer project with a handful of stars.** efis-editor is the one that
got traction, and what distinguishes it is not a better format — it is that it
does the tedious, unglamorous work of reading and writing six real vendor formats.

The strategic reading: **the format is not the moat, and it is not the scarce
thing.** The scarce things are (a) a corpus with trustworthy provenance and
(b) format coverage that already exists in efis-editor. A fifth JSON checklist
schema with no corpus behind it is the thing that has already failed four times.
This is an argument for spending the project's effort on the corpus, the
verification model, and the rights work, and for treating the schema as a means
rather than the deliverable.

I did not find a project that died from a copyright complaint, and I did not find
a reported takedown. The observed failure mode is attrition, not enforcement.

### 3.4 A contamination warning for the OCR pipeline

While looking for a Piper J-3 checklist, the top results led me to a 126-page PDF
titled *"WINGS OF SILVER PIPER J-3 Cub OPERATIONS MANUAL & POH"*. It contains a
plausible-looking pre-takeoff checklist. Page ii reads:

> "(this Manual and POH is not intended for flight and is intended only for
> flight simulation use)  Written by Mitchell Glicksman, © 2009"

It is documentation for a flight-simulator add-on. It is copyrighted by its
author, and it is explicitly not airworthiness data — but nothing about the file
name, the title, or the search result says so, and an OCR pipeline pointed at
"free J-3 POH" would have ingested it without hesitating.

This is a distinct failure mode from OCR inaccuracy, and the kickoff's
verification model does not catch it: a perfect transcription of an inadmissible
source is still worthless, and the fidelity states would all read green. **The
pipeline needs source admissibility screening as a separate gate from
transcription accuracy.** The schema carries
`provenance.source.kind: simulator_product` for exactly this, and the validator
rejects any file that declares it.

Simulator material also dominates search results for older types, so this will
not be a rare event. It will be the common case for precisely the aircraft whose
real documentation is hardest to find.

### 3.5 The gap, confirmed

I could not find a freely available Part 103 or ultralight checklist for any type,
including the Aerolite 103, which is among the most common Part 103 aircraft
flying. There is a structural reason: **Part 103 aircraft are not required to have
an approved flight manual at all.** There is frequently no authoritative source
document to transcribe.

This sharpens the kickoff's thesis and changes what the project must do for this
class. For certified types, Open Checklists is a *transcription* project. For Part
103, it is necessarily an *authorship* project — content composed by experienced
operators of the type and validated operationally, because there is no source
document against which fidelity could be measured. Those are different workflows
with different review requirements, and the verification model has to express
both. It is the reason `source_fidelity` includes `not_applicable` as a
first-class state rather than treating a missing source as an error.

---

## Sources

Doctrine and statute:

- [17 U.S.C. § 102(b)](https://www.law.cornell.edu/uscode/text/17/102) via [Stanford CIS on § 102(b)](https://cyberlaw.stanford.edu/blog/2007/08/section-102b-and-negative-categories-copyright-subject-matter/)
- [Baker v. Selden, 101 U.S. 99 (1879)](https://en.wikipedia.org/wiki/Baker_v._Selden)
- [Reconceptualizing Copyright's Merger Doctrine (NYU Law)](https://www.law.nyu.edu/sites/default/files/Reconceptualizing%20Copyrights%20Merger%20Doctrine.pdf)
- [37 C.F.R. § 202.1 — Material not subject to copyright (eCFR)](https://www.ecfr.gov/current/title-37/chapter-II/subchapter-A/part-202/section-202.1) and [Copyright Office text](https://www.copyright.gov/title37/202/37cfr202-1.html)
- [Publications Int'l, Ltd. v. Meredith Corp., 88 F.3d 473 (7th Cir. 1996)](https://cyber.harvard.edu/people/tfisher/IP/1996Publications.pdf) and [commentary](https://copyrightalliance.org/are-recipes-cookbooks-protected-by-copyright/)
- [American Dental Ass'n v. Delta Dental Plans Ass'n, 126 F.3d 977 (7th Cir. 1997)](https://law.justia.com/cases/federal/appellate-courts/F3/126/977/497929/)
- [17 U.S.C. § 105 — US Government works](https://uscode.house.gov/view.xhtml?req=%28title%3A17+section%3A105+edition%3Aprelim%29) and [ARL, Copyright Status of Government Works](https://www.arl.org/wp-content/uploads/2015/06/copyright-status-of-government-works.pdf)
- [Copyright Office Circular 22, How to Investigate the Copyright Status of a Work](https://www.copyright.gov/circs/circ22.pdf)
- [Public domain in the United States — notice and renewal rules](https://en.wikipedia.org/wiki/Public_domain_in_the_United_States)

Liability:

- [Winter v. G.P. Putnam's Sons, 938 F.2d 1033 (9th Cir. 1991)](https://law.justia.com/cases/federal/appellate-courts/F2/938/1033/294363/) — distinguishes the aeronautical chart cases at [full text](https://law.resource.org/pub/us/case/reporter/F2/938/938.F2d.1033.89-16308.html)

DMCA:

- [DMCA § 1201 overview](https://copyrightalliance.org/education/copyright-law-explained/the-digital-millennium-copyright-act-dmca/section-1201-technology-protection/)
- [EFF Coders' Rights Reverse Engineering FAQ](https://www.eff.org/issues/coders/reverse-engineering-faq)
- [CRS, Anticircumvention under the DMCA and Reverse Engineering](https://www.everycrsreport.com/reports/RL32692.html)

Landscape:

- [rdamazio/efis-editor](https://github.com/rdamazio/efis-editor) (Apache-2.0; model read from a local clone at `src/model/proto/checklist.proto`)
- [freechecklists.net](http://freechecklists.net/) (HTTP 503 at time of writing)
- [freerobby/aviation-checklist](https://github.com/freerobby/aviation-checklist)
- [mofo/checklist-creator](https://github.com/mofo/checklist-creator/blob/main/README.md)
- [MaggieLeber/checklist](https://github.com/MaggieLeber/checklist)
- [Generating Aviation Checklists with Make — Daniel Wiese](https://danielwiese.com/posts/makefile-checklists/)
- [checklist.aerobreak.com](https://checklist.aerobreak.com/)

Public-domain source used for the worked example:

- [FAA-H-8083-3C, Airplane Flying Handbook, Chapter 2: Ground Operations](https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/airplane_handbook/03_afh_ch2.pdf)

Contamination example:

- ["Wings of Silver Piper J-3 Cub Operations Manual & POH", Mitchell Glicksman, © 2009](https://www.avsport.org/simulate/A2A_Piper_J3_Pilots_Manual.pdf) — flight-simulator documentation, explicitly not for flight
