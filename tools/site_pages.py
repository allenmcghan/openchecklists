#!/usr/bin/env python3
"""Branding, marketing and policy pages for the site.

Kept out of build_site.py because it is prose, not logic, and because the legal
pages need to be readable and reviewable as text rather than buried in a generator.

The privacy policy is short for a real reason rather than a rhetorical one: the site
is static, stores everything in the visitor's own browser, and has no analytics, no
cookies and no accounts. There is very little to disclose, and saying so plainly is
more useful than a long document that implies otherwise.
"""

from __future__ import annotations

BRAND_NAME = "Open Checklists"
TAGLINE = "Free aircraft checklists that tell you where they came from."

# Geometric, reproducible, and legible at 16px: a checkbox whose tick sweeps up
# like a wing. Uses currentColor so it works in both themes and inside text.
LOGO_SVG = """<svg class="logo" viewBox="0 0 40 40" role="img" aria-label="Open Checklists">
<rect x="2.5" y="2.5" width="35" height="35" rx="8" fill="none" stroke="currentColor" stroke-width="3"/>
<path d="M10 22 L17.5 29 L34 8" fill="none" stroke="currentColor" stroke-width="4.5"
 stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
<rect width="40" height="40" rx="9" fill="#1f4e79"/>
<path d="M10 21 L17.5 28.5 L32 8.5" fill="none" stroke="#fff" stroke-width="5"
 stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def landing_body() -> str:
    return """
<div class="hero">
  <h2 class="hero-h">Every checklist should say where it came from.</h2>
  <p class="hero-p">Open Checklists is a free library of aircraft checklists as
  structured data. Read one on your phone at the aircraft, print it at whatever size
  your kneeboard takes, load it into your own software, or fork somebody else's and
  change what your aeroplane does differently.</p>
  <p class="hero-cta">
    <a class="cta" href="index.html">Browse the catalogue</a>
    <a class="cta ghost" href="editor.html">Make your own</a>
  </p>
  <p class="tag">No account. Nothing to install. Nothing uploaded unless you choose to
  contribute it.</p>
</div>

<div class="grid3">
  <div class="feat">
    <h3>Built for modified aircraft</h3>
    <p>Engine swaps, prop changes and panel rebuilds are the norm in experimental and
    ultralight flying, and everyone ends up writing their own checklist. Here you can
    see what somebody else with your airframe had to change, and why — grouped by
    airframe, with the differences spelled out rather than left for you to spot.</p>
  </div>
  <div class="feat">
    <h3>Honest about what is checked</h3>
    <p>Every file records the document it came from and whether a human has compared
    it against that document. Nothing is dressed up. A machine transcription that
    nobody has reviewed says so, in its filename and on every printed page.</p>
  </div>
  <div class="feat">
    <h3>Yours to take anywhere</h3>
    <p>JSON, CSV, Markdown, plain text, XML, Word, PDF, any paper size. A published
    schema so your own software can read it. No API key, no rate limit, no
    registration, and a hash of every file so you can verify a copy.</p>
  </div>
</div>

<h2>Why not just a PDF library?</h2>
<p>Because a PDF cannot tell you it is out of date, cannot be ticked on a phone,
cannot be reflowed onto a 5×8 kneeboard card, and cannot be loaded into anything. The
free checklist collections that exist are scans and PDFs — useful to a human with a
printer, useless to software, and impossible to correct when somebody spots an error.</p>

<p>Structured data fixes all four. And because each file carries a content hash,
a report of a problem can be tied to the exact version somebody was reading, so a
confirmed error costs that file its verification badge automatically. That is how a
library stays current instead of merely claiming to.</p>

<h2>What this is not</h2>
<p><strong>Not approved data.</strong> Nothing here is an approved flight manual, and
for a type-certificated aircraft nothing here can substitute for one. Your aircraft's
own documentation governs, always. Every file says so and every export repeats it.</p>

<h2>Start somewhere</h2>
<p><a href="index.html">Browse everything</a> &middot;
<a href="editor.html">Write a checklist for your aircraft</a> &middot;
<a href="about.html">How to read a file's verification state</a> &middot;
<a href="contribute.html">Contribute one</a></p>
"""


PRIVACY = """
<h2>Privacy</h2>
<p class="tag">Last updated: 2026-08-10</p>

<p>This site is a collection of static files. There is no server-side application, no
database, no user accounts and no login.</p>

<h3>What we collect</h3>
<p><strong>Nothing.</strong> No analytics, no tracking pixels, no advertising, no
cookies, no local or session storage used for identification, no fingerprinting, and
no third-party scripts of any kind. Every page on this site is self-contained: it
makes no requests to any other host, so no other company learns that you visited.</p>

<h3>What stays in your browser</h3>
<p>The checklist editor and the checklist pages save your work using your browser's
own local storage, on your own device. That includes checklists you write or fork,
and completion logs you record. This data:</p>
<ul>
  <li>never leaves your device unless you explicitly download it or choose to
  contribute it;</li>
  <li>is not readable by us, because it is never sent anywhere;</li>
  <li>can be deleted at any time from within the editor, or by clearing site data in
  your browser.</li>
</ul>
<p>Because it lives in your browser, it is not backed up and it is not synced between
devices. Download anything you would be upset to lose.</p>

<h3>Server logs</h3>
<p>Files are served by a static host. Like any web server, that host may record
ordinary request information such as IP address, timestamp and requested path, for
the purpose of serving the site and defending it from abuse. We do not use it for
analytics or profiling, we do not combine it with anything else, and we do not sell
or share it. If the host is GitHub Pages, GitHub's own privacy statement applies to
that layer.</p>

<h3>If you contribute</h3>
<p>Contributions are made through a public pull request. Anything in a contribution
is public and permanent: the file, the name and any contact details you put in it,
and the commit history. Provenance is the point of this project, so contributor
attribution is deliberately not anonymous — but put in only what you are content to
publish. You can use a pseudonym.</p>

<h3>Children</h3>
<p>This site is not directed at children and collects nothing from anyone.</p>

<h3>Changes</h3>
<p>If this policy changes, the date above changes and the previous version stays in
the site's public git history.</p>

<h3>Contact</h3>
<p>Privacy questions, corrections and takedown requests: see
<a href="contact.html">contact</a>.</p>
"""


TERMS = """
<h2>Terms of use</h2>
<p class="tag">Last updated: 2026-08-10</p>

<div class="banner quar"><strong>Safety notice, and the most important thing on this
page.</strong> Nothing on this site is approved aeronautical data. It is not a flight
manual, not an approved checklist, and not a substitute for your aircraft's own
documentation. Verify everything against the approved documentation for your specific
aircraft before flight. You, as pilot in command, are responsible for the aircraft and
for the procedures you use.</div>

<h3>No warranty</h3>
<p>The content is provided "as is", without warranty of any kind, express or implied,
including any warranty of accuracy, completeness, merchantability or fitness for a
particular purpose. Files may contain transcription errors, may be based on superseded
source documents, may describe an aircraft configured differently from yours, and may
be incomplete in ways that are not obvious — a missing emergency procedure is invisible
to the person holding the file. Each file states what is known about it; read that
before relying on it.</p>

<h3>Limitation of liability</h3>
<p>To the maximum extent permitted by law, the project, its maintainers and its
contributors are not liable for any loss, injury or damage arising from use of this
site or its content, including any incidental, consequential or indirect damages. Some
jurisdictions do not allow certain exclusions, in which case the exclusions apply to
the extent permitted.</p>

<h3>Licensing of the content</h3>
<p>Rights are recorded <strong>per file</strong>, not across the site as a whole,
because the project cannot grant a licence in text it does not own. Each file's
<code>rights</code> block states its status and licence:</p>
<ul>
  <li><code>public_domain</code> — the source carries no enforceable copyright, with
  the basis stated. Most are works of the US Government under 17 U.S.C. § 105.</li>
  <li><code>original_expression</code> — the wording is the contributor's own,
  expressing procedure as fact. Normally offered under CC-BY-4.0.</li>
  <li><code>licensed</code> — used with permission, with the permission recorded.</li>
</ul>
<p>Check the file you are using. Do not assume one licence covers everything.</p>

<h3>Licensing of the site and tooling</h3>
<p>The schema and specification are dedicated permissively so anyone can implement
them, including in closed commercial products. The site code and tools are
Apache-2.0.</p>

<h3>If you contribute</h3>
<p>By contributing you confirm the warranty set out on the
<a href="contribute.html">contribute</a> page: that you have the right to submit the
content, that you have accurately stated its source, and that you have not copied
wording, selection or arrangement from a copyrighted source beyond what the file
declares.</p>

<h3>Acceptable use</h3>
<p>Do not use this site to distribute content you have no right to distribute, and do
not present files from here as approved data or as endorsed by any manufacturer or
authority. Manufacturer names appear only to identify aircraft; no affiliation or
endorsement is implied.</p>

<h3>Takedown</h3>
<p>If you believe something here infringes your rights, see
<a href="takedown.html">takedown</a>. Material is unpublished first and argued about
afterwards.</p>
"""


TAKEDOWN = """
<h2>Takedown and corrections</h2>
<p class="tag">Designed before it was needed, which is the only time it can be.</p>

<h3>If you hold rights in something here</h3>
<p>Write to the address on the <a href="contact.html">contact</a> page. Tell us which
file, and what your claim is. You do not need a lawyer and you do not need to use any
particular form of words.</p>

<h4>What happens</h4>
<ol>
  <li><strong>We acknowledge within 72 hours</strong> and tell you what happens next.</li>
  <li><strong>We unpublish first and argue afterwards.</strong> On a good-faith claim
  the file comes off the site and out of the bundles immediately. The cost of a
  checklist being unavailable for two weeks is low; the cost of a contested file
  staying up is not. Nothing is destroyed — the project's history is public, so
  unpublishing is reversible.</li>
  <li><strong>We assess it</strong> against the project's published rights rules.</li>
  <li><strong>We record the outcome publicly</strong>: what was claimed, what was
  decided and why. That log is how the project learns where the line actually is, and
  it makes every later claim cheaper to handle.</li>
  <li><strong>We notify the contributor</strong>, who may respond. Their contributor
  warranty is what makes this a matter between you, the project and them, rather than
  the project alone.</li>
  <li><strong>We fix the class, not just the instance.</strong> If one file was wrong
  about its source, others from the same contributor and the same document are
  suspect too.</li>
  <li><strong>Nothing is restored silently.</strong> A restoration gets its own public
  log entry.</li>
</ol>

<h3>If you have spotted an error</h3>
<p>That is a different and more common thing, and it is the mechanism this project
runs on. Every file has a content hash, so a report can be tied to the exact version
you were reading. File a report saying what the file says, what it should say, and
what you checked against.</p>
<p>A confirmed transcription error or stale item <strong>automatically costs that file
its verification badge</strong> — the tooling refuses to let a file keep a review
claim over content now known to be wrong. You do not have to argue anyone into it.</p>
<p>See <a href="contribute.html">contribute</a> for how to file one.</p>

<h3>If you are a manufacturer or type club</h3>
<p>We would rather work with you than around you. The project can do something your
own PDF distribution cannot: mark every derived copy stale the day you publish a new
revision, and tell anyone holding an old one that it is out of date. Every file
records the revision it came from and links to you as the canonical source. If you
would prefer a file removed, say so and it goes — but the offer to keep your revisions
propagating stands either way.</p>
"""


def contribute_body() -> str:
    return """
<h2>Contribute a checklist</h2>

<p class="lede">The most valuable file in this library is the one written by somebody
who actually owns the aircraft. If you have a heavily modified experimental, or a Part
103 machine that came with no manual at all, nobody else can write your checklist.</p>

<h3>The quickest route</h3>
<ol>
  <li>Open the <a href="editor.html">editor</a>. Start blank, or fork a checklist for
  the same airframe.</li>
  <li>Fill it in. It saves in your browser as you go, so you can come back to it.</li>
  <li>Download the <code>.ocl.json</code> file.</li>
  <li>Open a pull request adding it to <code>examples/</code> in the repository, or
  send it to the address on the <a href="contact.html">contact</a> page.</li>
</ol>
<p>Automated checks run on every pull request: the schema, the corpus policy rules,
and the export contract. You will get told what is wrong rather than left guessing.</p>

<h3>What makes a contribution useful rather than noise</h3>
<ul>
  <li><strong>Say what your aircraft actually is.</strong> Record the engine, and every
  modification that matters — swaps, prop changes, panel rebuilds, gross weight
  increases. This is what makes your file findable by the next person with the same
  setup, and it is the whole point of the airframe family grouping.</li>
  <li><strong>Say where the content came from.</strong> Your own aircraft? A kit
  manual? A published handbook? "Unknown" is an honest answer and a usable one; a
  wrong answer is not.</li>
  <li><strong>Do not invent numbers.</strong> If you do not know the correct airspeed
  or RPM, leave it out. An omitted limitation is a gap; a confidently wrong one is a
  hazard. Files here deliberately omit values rather than guess them.</li>
  <li><strong>Write the wording yourself.</strong> Copy the facts — which control,
  which position, which value, in which order — but do not reproduce a manufacturer's
  prose, section titles or arrangement.</li>
  <li><strong>Say what you changed, if you forked.</strong> The most useful sentence in
  a derived checklist is the one explaining what the modification forced.</li>
</ul>

<h3>Contributor warranty</h3>
<p>By contributing you confirm that:</p>
<ol>
  <li>you have the right to submit the content, and doing so breaches no agreement
  binding you;</li>
  <li>you have accurately stated the source document and how the content was
  produced;</li>
  <li>where you claim public domain status, you state the basis and what you
  checked;</li>
  <li>you have not copied wording, selection or arrangement from a copyrighted source
  beyond what the file declares;</li>
  <li>you understand the file will be redistributed under the licence it states, and
  that the project makes no warranty of fitness.</li>
</ol>
<p>Your name stays attached to the file. That is deliberate: provenance is the point,
and a file nobody stands behind cannot be assessed. A pseudonym is fine.</p>

<h3>What your file will be marked as</h3>
<p>Everything arrives as <strong>authored, not reviewed, not airworthy</strong> — and
that is not an insult, it is accurate. Verification is earned by somebody else
comparing your file against its source, or walking it through the cockpit. You cannot
claim it by writing it, and neither can anyone else.</p>
<p>Read <a href="about.html">how to read a file</a> for what the states mean.</p>

<h3>Reporting a problem with an existing file</h3>
<p>Include the file's id, its content hash from the bottom of its page, the item you
are talking about, what it says now, what it should say, and what you checked against.
A confirmed error automatically strips the file's verification badge.</p>

<h3>What we cannot accept</h3>
<ul>
  <li>Scans or copies of a manufacturer's manual, or files copied wholesale from
  another checklist site — several forbid it in their terms.</li>
  <li>Flight-simulator documentation. It is copyrighted by the sim vendor and it is
  not airworthiness data, however convincing it looks.</li>
  <li>Files with no stated provenance at all. If nobody can tell where it came from,
  nobody can check it.</li>
</ul>
"""


CONTACT = """
<h2>Contact</h2>

<p>This is a small project. There is no support desk, and answers come from people
doing this in their own time.</p>

<table><tbody>
<tr><td><strong>Errors in a checklist</strong></td>
    <td>Fastest through the repository as a report or pull request — see
    <a href="contribute.html">contribute</a>. Include the file id and its content
    hash.</td></tr>
<tr><td><strong>Rights and takedown</strong></td>
    <td>See <a href="takedown.html">takedown</a>. Material is unpublished first and
    assessed afterwards. Acknowledged within 72 hours.</td></tr>
<tr><td><strong>Privacy</strong></td>
    <td>See <a href="privacy.html">privacy</a>. Short version: the site collects
    nothing, so there is usually nothing to request.</td></tr>
<tr><td><strong>Manufacturers and type clubs</strong></td>
    <td>Very welcome. See the last section of <a href="takedown.html">takedown</a> for
    what the project can offer you.</td></tr>
<tr><td><strong>Everything else</strong></td>
    <td>Open an issue in the repository.</td></tr>
</tbody></table>

<p class="tag">Replace this page's placeholders with a real address and a named
responsible person before launch. A takedown process with no reachable human is not a
process.</p>
"""
