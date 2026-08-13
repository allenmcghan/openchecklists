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
TAGLINE = "Free checklists for every type of aircraft and pilot."

# Professional logo: navy rounded square with white wing-sweep checkmark.
# The tick is drawn with a subtle upward sweep on the left arm — like a
# climbing flight path — and a confident long right stroke.
LOGO_SVG = """<svg class="logo" viewBox="0 0 40 40" role="img" aria-label="Open Checklists">
<rect width="40" height="40" rx="10" fill="#1f4e79"/>
<path d="M9 22 L16.5 29.5 L32 9" fill="none" stroke="#fff" stroke-width="4.5"
 stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">
<rect width="40" height="40" rx="10" fill="#1f4e79"/>
<path d="M9 22 L16.5 29.5 L32 9" fill="none" stroke="#fff" stroke-width="4.5"
 stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def landing_body() -> str:
    return """
<div class="hero">
  <div class="hero-img-wrap">
    <img src="hero.svg" alt="Cessna 172 Skyhawk on final approach to a grass-strip runway"
         class="hero-img" width="1024" height="512" loading="eager">
  </div>
  <div class="hero-text">
    <h1 class="hero-h">Your checklist.<br>Every flight.<br>Every aircraft.</h1>
    <p class="hero-p">Free, open checklists for Cessnas, Pipers, Cubs, airliners, gliders,
    ultralights, paramotors, and drones — any aircraft with wings. Read on your phone at
    the aircraft, print at kneeboard size, email yourself a timestamped proof after every
    preflight.</p>
    <p class="hero-cta">
      <a class="cta" href="catalogue.html">Browse checklists</a>
      <a class="cta ghost" href="airports.html">Airport frequencies</a>
      <a class="cta ghost" href="training.html">Study for your certificate</a>
    </p>
    <p class="tag">Free forever &middot; No account &middot; Works offline &middot; Nothing uploaded
    unless you choose to contribute it.</p>
  </div>
</div>

<h2>Every aircraft. Every pilot.</h2>
<div class="aircraft-types">
  <a class="atype" href="catalogue.html?q=general+aviation">
    <span class="atype-icon">✈</span>
    <span class="atype-label">General Aviation</span>
  </a>
  <a class="atype" href="catalogue.html?q=light+sport">
    <span class="atype-icon">🛩</span>
    <span class="atype-label">Sport Pilot / LSA</span>
  </a>
  <a class="atype" href="catalogue.html?q=ultralight">
    <span class="atype-icon">🛸</span>
    <span class="atype-label">Ultralight / Part 103</span>
  </a>
  <a class="atype" href="catalogue.html?q=paramotor">
    <span class="atype-icon">🪂</span>
    <span class="atype-label">Paramotor / PPG</span>
  </a>
  <a class="atype" href="catalogue.html?q=glider">
    <span class="atype-icon">🌤</span>
    <span class="atype-label">Glider &amp;<br>Sailplane</span>
  </a>
  <a class="atype" href="catalogue.html?q=drone">
    <span class="atype-icon">🚁</span>
    <span class="atype-label">Drone / Part 107</span>
  </a>
</div>

<div class="grid3">
  <div class="feat">
    <h3>Your preflight, with proof</h3>
    <p>Tick items on your phone in real time. When you're done, enter your email and
    receive a timestamped log — every item checked, every item skipped, and when each
    one was done. Your own record of every preflight, in your inbox.</p>
  </div>
  <div class="feat">
    <h3>Honest about the source</h3>
    <p>Every checklist shows where it came from and whether someone has
    double-checked it against that source. Nothing is dressed up as "verified" if
    nobody has actually sat down and compared it item by item.</p>
  </div>
  <div class="feat">
    <h3>Works your way</h3>
    <p>Print to any paper size — letter, kneeboard, index card. Export as PDF, Word,
    CSV, or Markdown. Fork any checklist and change what your aircraft does
    differently. No account, no lock-in, no rate limits.</p>
  </div>
</div>

<div class="feat-row">
  <div class="feat-row-item">
    <strong>19,426 airports</strong>
    <span>Radio frequencies, runways, fuel, pattern altitude — every public and
    private strip in the US, from the FAA&rsquo;s 28-day data.</span>
    <a href="airports.html">Look up any airport &rarr;</a>
  </div>
  <div class="feat-row-item">
    <strong>Free study material</strong>
    <span>Every FAA handbook — PHAK, Instrument Flying, Aviation Weather, AC&nbsp;43.13 —
    indexed and searchable. Plus sample tests for every certificate level.</span>
    <a href="training.html">Start studying &rarr;</a>
  </div>
  <div class="feat-row-item">
    <strong>Open format</strong>
    <span>A documented JSON schema so any app can read these checklists. A hash of
    every file so you can verify what you downloaded is what was published.</span>
    <a href="about.html">How the format works &rarr;</a>
  </div>
</div>

<h2>What this is not</h2>
<p><strong>Not approved data.</strong> Nothing here replaces your aircraft's own flight
manual. For type-certificated aircraft, the approved AFM governs. Every checklist
states its source and verification status — read that before you rely on it.</p>

<p>For certificated aircraft (Cessna, Piper, experimental category, etc.), every checklist
notes whether it was compared item-by-item against the manufacturer's POH. For aircraft
that don't have a required flight manual — paramotors, hang gliders, ultralight Part 103
— a well-sourced community checklist is the best available resource, and being honest
about that is exactly the point.</p>

<h2>Start here</h2>
<p>
<a href="catalogue.html">Browse all checklists</a> &middot;
<a href="airports.html">Airport frequencies and weather</a> &middot;
<a href="training.html">Study for your certificate</a>
</p>
"""


HERO_CSS = """
.hero{display:grid;grid-template-columns:1fr;gap:0;margin:0 -1.15rem 1.4rem;
border-bottom:1px solid var(--line);overflow:hidden}
.hero-img-wrap{position:relative;max-height:300px;overflow:hidden;background:#1a5ba3}
.hero-img{width:100%;height:100%;object-fit:cover;object-position:center 38%;display:block}
.hero-text{padding:1.6rem 1.15rem 1.8rem}
.hero-h{font-size:clamp(2rem,7vw,3rem);line-height:1.06;letter-spacing:-.032em;
margin:.1rem 0 .7rem;font-weight:820}
.hero-p{font-size:1.05rem;color:var(--muted);max-width:42rem;margin:0}
.aircraft-types{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;margin:1rem 0 1.8rem}
.atype{display:flex;flex-direction:column;align-items:center;gap:.35rem;text-align:center;
padding:.8rem .5rem;border:1px solid var(--line);border-radius:14px;
color:var(--fg);text-decoration:none;background:#fff;transition:border-color .15s,transform .15s,box-shadow .15s}
.atype:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 6px 18px rgba(15,24,38,.09);text-decoration:none}
.atype-icon{font-size:1.6rem;line-height:1}
.atype-label{font-size:.75rem;font-weight:600;color:var(--fg);line-height:1.25}
.feat-row{display:grid;gap:1rem;grid-template-columns:1fr;margin:1.6rem 0}
.feat-row-item{border:1px solid var(--line);border-radius:14px;padding:1.1rem;
background:#fff;display:flex;flex-direction:column;gap:.35rem}
.feat-row-item strong{font-size:1.02rem;display:block}
.feat-row-item span{font-size:.9rem;color:var(--muted);flex:1}
.feat-row-item a{font-size:.88rem;font-weight:600;color:var(--accent)}
@media(min-width:600px){.aircraft-types{grid-template-columns:repeat(6,1fr)}}
@media(min-width:800px){
.hero{grid-template-columns:1fr 1fr}
.hero-img-wrap{max-height:none;min-height:340px}
.hero-text{padding:2.2rem 1.5rem 2.2rem}
.feat-row{grid-template-columns:repeat(3,1fr)}}
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
