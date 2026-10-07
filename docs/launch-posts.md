# Launch posts — drafts for Allen to post

Post these yourself, from your own accounts; communities ban accounts that look like
marketing. Read each community's self-promotion rules first, say plainly that you built it,
and lead with the ask ("what's missing for your aircraft?"), not the link. Space them out
over two or three weeks so each spike can be read on its own in Umami
(`analytics.keylinkit.net`) and on the owner page (`openchecklists.net/admin.html`).

Every link below carries `?utm_source=<place>` so the source shows up in analytics even when the
browser strips the referrer.

---

## 1. r/ultralight (and r/PoweredParachute / r/paramotor where allowed)

**Title:** I built free, printable checklists for ultralights and powered parachutes — what's missing for yours?

I fly a ParaPlane PM-2 and got tired of the fact that the aircraft that most need a good
checklist — Part 103 machines, PPCs, kit-builts — are the ones that never came with one.
So I started openchecklists.net: free checklists you can tick off on your phone, print at
any size, or download (Word/CSV/JSON), and fork for your own airframe and engine.

There's also a Part 103 rules quiz (written straight from the regulation text) and airport
pages for every US strip including the grass ones.

What I'd really like: tell me what you fly and what your manual is missing.
Request form: https://openchecklists.net/request-checklist.html?utm_source=reddit-ultralight

(Disclosure: it's my project. No sign-up needed for any of it.)

---

## 2. r/flying (weekly/self-promo thread if the sub requires it)

**Title:** Free open-source checklists, airport pages and FAA practice questions — feedback welcome

Side project from a pilot/builder: openchecklists.net. 265 checklists you can use on a phone
or print, every US airport with runways/frequencies/live METAR and a crosswind calculator,
161 FAA sample knowledge-test questions with cited explanations (PAR, Sport, Part 107,
Part 103), and a free logbook with currency tracking (61.56/61.57, medical).

Everything is free and works without an account. It's explicitly *not* an official briefing
or approved data — each checklist says where it came from and whether anyone has checked it.

What would make you actually use something like this?
https://openchecklists.net/?utm_source=reddit-flying

---

## 3. Van's Air Force / Kitplanes / EAA chapter newsletter

**Subject:** Free, forkable checklists for homebuilts — and a request

Homebuilt checklists drift away from the aircraft every time you change something — an
engine swap, a new panel, a different prop. openchecklists.net treats a checklist like
code: you fork one for your type, record what you changed and why, and print or load it
anywhere. Each file keeps its source and lineage.

If your chapter has a type with no decent checklist, send me the make/model (or use the
form) and I'll prioritize it: https://openchecklists.net/request-checklist.html?utm_source=vaf

---

## 4. Pilots of America / BeechTalk (in the appropriate "products/projects" forum)

Short intro, link to one concrete page for the forum's typical aircraft
(e.g. `https://openchecklists.net/aircraft/beechcraft-bonanza/?utm_source=poa`), and ask
which checklists people want reviewed against the POH — reviewers who check a file
against its source earn it a "reviewed" badge.

---

## 5. Hacker News — Show HN

**Title:** Show HN: Open Checklists – machine-readable aircraft checklists with provenance

Aircraft checklists are safety data that live in PDFs and laminated cards. I wanted them as
data: a JSON schema where every file carries its source document, revision, and a
two-axis verification state (does it match its source? has anyone flown behind it?), with
exporters to print/CSV/Word/Markdown that are contract-tested never to drop a warning.

The site (static + Cloudflare Workers) renders them for phones and print, server-renders
19k FAA airport pages, and includes a quiz built from the FAA's public-domain sample tests.
Code and format: https://github.com/allenmcghan/openchecklists

Curious what HN thinks of the verification model (docs/03-verification-model.md).
https://openchecklists.net/?utm_source=hn

---

## 6. Flight schools / CFIs (email — only to people you already know, or via their contact form)

Short note offering the free practice questions and printable checklists for their fleet
types; ask which aircraft they'd want checklists for. Link:
`https://openchecklists.net/quiz/?utm_source=cfi`

---

### What to watch after each post
- Umami: visitors, top pages, `utm_source` values (UTM report), events `checklist-download`,
  `plan-generate`, `quiz-finish`, `checklist-request`, `sign-in`.
- `/admin.html`: real accounts, requests (the most-requested aircraft = what to write next).
- Reply to every comment within a day — early communities reward the builder showing up.
