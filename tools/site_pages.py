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
    <img src="hero.png" alt="Cessna 172 Skyhawk in flight over green farmland"
         class="hero-img" width="1408" height="768" loading="eager">
  </div>
  <div class="hero-text">
    <h1 class="hero-h">Your 90-second<br>pre-flight check.</h1>
    <p class="hero-p">Weather, NOTAMs, frequencies, runways and flight planning for every US airport,
    in one place — free, no account. A fast first look before you pull an official briefing,
    not a replacement for one.</p>
    <p class="hero-cta">
      <a class="cta" href="planner.html">Plan a Flight</a>
      <a class="cta ghost" href="airports.html">Look Up an Airport</a>
      <a class="cta ghost" href="catalogue.html">Browse Checklists</a>
    </p>
    <p class="tag">19,426 airports &middot; Live METAR &amp; TAF &middot; NOTAMs &middot; Always verify with an <a href="https://www.1800wxbrief.com/" target="_blank" rel="noopener">official briefing</a></p>
  </div>
</div>

<h2>One page instead of four apps</h2>
<p class="lede">Every airport page pulls together the research you'd otherwise hunt across several sites —
so you can decide in seconds whether it's worth opening ForeFlight and calling for a briefing.</p>

<div class="grid3">
  <div class="feat">
    <h3>🌤 Live weather at every airport</h3>
    <p>METAR, TAF, and winds aloft pulled directly from aviationweather.gov. Airports without
    an ASOS station get Open-Meteo current conditions. VFR/MVFR/IFR badge at a glance.</p>
  </div>
  <div class="feat">
    <h3>📡 Frequencies &amp; NOTAMs</h3>
    <p>Every radio frequency — CTAF, Tower, Ground, ATIS, Approach — sorted by priority.
    Active NOTAMs loaded live. Runway data with surface, lighting, and ILS approach info.</p>
  </div>
  <div class="feat">
    <h3>📞 Airport phone &amp; field data</h3>
    <p>The airport manager's phone number — one tap to call from your phone — plus ownership,
    field elevation, pattern altitude and sectional, straight from the FAA NASR database.</p>
  </div>
  <div class="feat">
    <h3>🗺 Satellite &amp; terrain maps</h3>
    <p>Interactive satellite view defaults to the airport the moment you open the page.
    Switch to terrain for elevation awareness, or street for local area context.</p>
  </div>
  <div class="feat">
    <h3>☀ Sunrise &amp; sunset</h3>
    <p>Exact local sunrise, sunset, and civil twilight times calculated for the airport's
    coordinates — no lookup needed, right on the airport page.</p>
  </div>
  <div class="feat">
    <h3>✈ End-to-end flight planning</h3>
    <p>Enter your aircraft profile, pick your route, review weather at every stop,
    calculate fuel, and generate a complete pre-flight briefing you can print or email
    to yourself for the cockpit.</p>
  </div>
</div>

<div class="feat-row">
  <div class="feat-row-item">
    <strong>Look up any airport</strong>
    <span>Search by name, city, identifier, or state. Every public and private strip in
    the US, from Class B towered airports to grass strips, with full FAA data.</span>
    <a href="airports.html">Search airports &rarr;</a>
  </div>
  <div class="feat-row-item">
    <strong>Plan your route</strong>
    <span>Save your aircraft profile once. Then pick departure, destination, and alternate —
    and get a full weather briefing, fuel calc, and printable cockpit reference in under
    two minutes.</span>
    <a href="planner.html">Open the planner &rarr;</a>
  </div>
  <div class="feat-row-item">
    <strong>Study for your certificate</strong>
    <span>Every FAA handbook — PHAK, Instrument Flying, Aviation Weather, AC&nbsp;43.13 —
    indexed and searchable. Sample tests for every certificate level.</span>
    <a href="training.html">Start studying &rarr;</a>
  </div>
</div>

<h2>Free checklists for every aircraft</h2>
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
    <span class="atype-label">Glider &amp; Sailplane</span>
  </a>
  <a class="atype" href="catalogue.html?q=drone">
    <span class="atype-icon">🚁</span>
    <span class="atype-label">Drone / Part 107</span>
  </a>
</div>

<h2>What this is not</h2>
<p><strong>Not a replacement for official sources.</strong> Every airport page links directly
to aviationweather.gov, the FAA NOTAM system, and 1800wxBrief. Use this to gather and
organize information quickly — then verify critical data from official sources before you fly.</p>
<p>For certificated aircraft, the approved AFM/POH governs. Every checklist on this site
shows where it came from and whether someone has compared it item-by-item against that source.</p>

<p class="tag" style="margin-top:2rem">
<a href="catalogue.html">Browse all checklists</a> &middot;
<a href="airports.html">Airport search</a> &middot;
<a href="training.html">Study resources</a> &middot;
<a href="about.html">Verification states</a>
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
<p class="tag">Last updated: 2026-10-07</p>

<p>Open Checklists is run by Allen McGhan (contact details on the
<a href="contact.html">contact</a> page). This page says plainly what the site collects,
why, and who else sees it. If something here is wrong, tell us and we will fix the
site or the page.</p>

<h3>Without an account</h3>
<p>You can use every checklist, airport page, the planner and the training pages
without signing in. In that case:</p>
<ul>
  <li><strong>Your browser keeps your work.</strong> Checklists you write or fork in the
  editor, and the boxes you tick, are saved in your browser's local storage on your own
  device. They are not sent to us unless you choose to publish, email or save them to an
  account. Clear your browser's site data to delete them.</li>
  <li><strong>Flight plans you generate are stored on our server</strong> so the briefing
  link works. Anyone with a plan's link can open it, so do not put anything private in a
  plan. Plan ids are long and random and are not listed anywhere.</li>
  <li><strong>Usage counts.</strong> When you open a checklist we add one to its public
  "uses" counter. To count each visitor once a day we keep a one-way hash of your IP
  address; it stops being used after 24 hours and is deleted by a daily clean-up job.
  The address itself is not stored.</li>
</ul>

<h3>With an account</h3>
<p>Accounts are optional. Sign-in is handled by our identity service at
<code>auth.keylinkit.net</code> (Zitadel), which holds your email address, name and login
factors. Our database then stores, against an internal account id:</p>
<ul>
  <li>the username, display name and leaderboard preference you choose;</li>
  <li>aircraft and favorite airports you save;</li>
  <li>your flight logbook entries, saved flight plans and training progress;</li>
  <li>checklist completion logs (kept for six months, then deleted automatically);</li>
  <li>points earned, and checklists and reviews you publish. <strong>Published
  checklists and reviews are public</strong>, shown with your display name or username.</li>
</ul>

<h3>Checklist requests</h3>
<p>If you request a checklist for your aircraft, we store the aircraft details you enter.
If you also tick "email me when it's available", we keep that email address only for that
purpose and delete it once we have told you (or on request).</p>

<h3>Email</h3>
<p>If you ask the site to email you a briefing, a checklist log or a PDF, we send it to
the verified email address on your account — never to an address typed into the page —
and keep only that account address. To stop abuse, emailing needs an account and is
limited per account and per network; the limit counters store a one-way hash of your
IP address, deleted daily once expired.</p>

<h3>Automated review of published checklists</h3>
<p>When you publish a checklist, its content is sent to Anthropic's Claude API for an
automated safety and copyright check before it appears publicly. The aircraft
registration field is removed automatically when you publish; do not put a registration
or anything else personal in titles or notes.</p>

<h3>Advertising and cookies</h3>
<p>The site is free and is paid for by advertising. We use <strong>Google AdSense</strong>
on some pages (airport, training, search and catalogue pages; never on checklist,
editor, planner or account pages). Google and its partners may use cookies and similar
technologies to show ads based on your visits to this and other websites, and to
measure ad performance.</p>
<ul>
  <li>How Google uses this data:
  <a href="https://policies.google.com/technologies/partner-sites" rel="noopener">policies.google.com/technologies/partner-sites</a>.</li>
  <li>Turn off personalised ads from Google:
  <a href="https://adssettings.google.com/" rel="noopener">adssettings.google.com</a>, or
  for many ad networks at <a href="https://optout.aboutads.info/" rel="noopener">optout.aboutads.info</a>.</li>
  <li>Visitors in the EEA, the UK and Switzerland are asked for consent through a
  Google-certified consent message before any personalised ads or ad cookies are used,
  and can change that choice at any time from the "Privacy and cookie settings" link
  the message adds to the page.</li>
</ul>
<h3>Analytics</h3>
<p>To learn which parts of the site pilots actually use, we measure visits without cookies:</p>
<ul>
  <li><strong>Cloudflare Web Analytics</strong> — page views and page-load speed, collected by
  our host without cookies or fingerprinting.</li>
  <li><strong>Umami</strong>, run by us at <code>analytics.keylinkit.net</code> — page views,
  the referring site, browser, device type and country, plus a few anonymous events
  (for example "checklist downloaded" or "plan generated"). No cookies; visitors are
  counted with a one-way hash that is rotated regularly, and IP addresses are not stored.</li>
  <li>If we add <strong>Microsoft Clarity</strong> (heatmaps and anonymised session replay) to
  public pages, it runs without cookies, masks text you type, and never runs on checklist,
  editor, account, sign-in or plan-briefing pages. We will list it here before it is turned on.</li>
</ul>
<p>Our own pages use your browser's session storage only to keep you signed in, and local
storage for your work as described above.</p>

<h3>Other services your browser contacts</h3>
<p>Some pages load live data or libraries straight from other providers, who therefore
see your IP address: aviationweather.gov and the FAA (weather, NOTAMs, charts),
Open-Meteo and RainViewer (forecast and radar), Esri/ArcGIS and OpenStreetMap (map tiles),
Windy (embedded wind map), and unpkg.com and cdnjs (Leaflet map and PDF libraries).
The site is hosted on Cloudflare, which processes ordinary request logs (IP address,
time, page) to serve the site and protect it from abuse.</p>

<h3>Your choices and rights</h3>
<ul>
  <li><strong>See, export or delete your data:</strong> most of it is visible and
  deletable on your profile page. To delete your account and everything stored with it,
  email the address on the <a href="contact.html">contact</a> page; we do it within 30
  days.</li>
  <li><strong>US state privacy rights (including California):</strong> we do not sell
  your personal information for money. Personalised advertising may count as "sharing"
  under California law; you can opt out using the Google settings above, by emailing
  us, or by enabling Global Privacy Control in your browser — when it is on, our pages
  ask Google for non-personalised ads only.</li>
  <li><strong>EEA/UK:</strong> you have rights of access, correction, deletion,
  objection and portability, and may complain to your data protection authority.</li>
</ul>

<h3>Children</h3>
<p>The site is not directed at children under 13 and we do not knowingly collect their
personal information. If you believe a child has created an account, contact us and we
will delete it.</p>

<h3>Changes</h3>
<p>If this policy changes, the date above changes and the previous version stays in the
site's public git history.</p>
"""


TERMS = """
<h2>Terms of use</h2>
<p class="tag">Last updated: 2026-10-04</p>

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

<h3>Accounts</h3>
<p>Accounts are optional and free. Keep your sign-in secure; you are responsible for
what is published from your account. We may remove content or suspend accounts that
abuse the site, publish content you have no right to publish, or try to game points or
ratings.</p>

<h3>Advertising and affiliate links</h3>
<p>The site is supported by advertising served by Google and its partners, and some
links to products or courses are affiliate links: if you buy through them we may earn a
commission, at no extra cost to you. Ads and affiliate links are labelled, are never
placed inside a checklist, and do not influence what a checklist says. An advertiser
appearing here is not an endorsement of its product, and we are not responsible for
third-party sites. See <a href="privacy.html">privacy</a> for how ads use cookies.</p>

<h3 id="affiliate-disclosure">Affiliate disclosure</h3>
<p>Open Checklists is a participant in the Amazon Services LLC Associates Program, an
affiliate advertising program designed to provide a means for sites to earn advertising
fees by advertising and linking to Amazon.com. <strong>As an Amazon Associate I earn from
qualifying purchases.</strong> Gear suggestions are clearly labelled, link to Amazon search
results rather than specific products, never appear inside a checklist, and never print.
Buying through them costs you nothing extra; check any item's fit and approval for your
aircraft before you buy.</p>

<h3>Weather and flight-planning data</h3>
<p>Weather, NOTAMs, frequencies and flight plans on this site are an unofficial,
unverified convenience. They are not an official briefing. 14 CFR 91.103 requires an
official briefing before flight (1800wxbrief.com or 1-800-WX-BRIEF).</p>

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

<p>Open Checklists is run by <strong>Allen McGhan</strong>. Email
<a href="mailto:allen@keylinkit.com">allen@keylinkit.com</a> for anything below; it is
read by a person.</p>

<table><tbody>
<tr><td><strong>Errors in a checklist</strong></td>
    <td>Email, or file a report through the repository — see
    <a href="contribute.html">contribute</a>. Include the file id and its content
    hash.</td></tr>
<tr><td><strong>Rights and takedown</strong></td>
    <td>Email with the subject "Takedown". See <a href="takedown.html">takedown</a>:
    material is unpublished first and assessed afterwards, acknowledged within 72
    hours.</td></tr>
<tr><td><strong>Privacy and account deletion</strong></td>
    <td>Email from the address on your account. See <a href="privacy.html">privacy</a>.</td></tr>
<tr><td><strong>Advertising and partnerships</strong></td>
    <td>Email with the subject "Advertising".</td></tr>
<tr><td><strong>Manufacturers and type clubs</strong></td>
    <td>Very welcome. See the last section of <a href="takedown.html">takedown</a> for
    what the project can offer you.</td></tr>
</tbody></table>
"""


ABOUT_US = """
<h2>About Open Checklists</h2>

<p class="lede">Free aircraft checklists, airport information and pre-flight tools for
pilots of ultralights, light-sport, experimental and certified aircraft.</p>

<p>Open Checklists started with a ParaPlane PM-2 powered parachute and a simple
problem: the aircraft that most need a good checklist — Part 103 ultralights, kit-built
experimentals, modified airframes — are the ones least likely to have one. The site
collects open, machine-readable checklists that anyone can read on a phone, print,
fork for their own aircraft, and download in any format.</p>

<p>Around the checklists sit the tools a pilot reaches for in the ninety seconds before
a flight: airport facts, runways and frequencies for every public and private US
airport from the FAA's 28-day data, live weather and NOTAMs, a multi-leg flight planner,
a logbook, and the FAA's own training handbooks, searchable.</p>

<h3>Who runs it</h3>
<p>Open Checklists is built and run by Allen McGhan, an aircraft builder and pilot, as
the open data layer alongside the <a href="https://github.com/allenmcghan/junco"
rel="noopener">Junco</a> open-source instrument project. The code and the checklist
format are open source on <a href="https://github.com/allenmcghan/openchecklists"
rel="noopener">GitHub</a>.</p>

<h3>How it is paid for</h3>
<p>The site is free to use and is supported by advertising and affiliate links. Ads are
kept off checklists, the editor, the planner and your account pages. See
<a href="privacy.html">privacy</a> and <a href="terms.html">terms</a>.</p>

<h3>What it is not</h3>
<p>Nothing here is approved aeronautical data or an official weather briefing. Every
checklist says where it came from and whether anyone has checked it; read
<a href="about.html">how to read a file</a> before relying on one.</p>

<p>Questions, corrections or partnership ideas: <a href="contact.html">contact</a>.</p>
"""



REQUEST_CHECKLIST = """
<h2>Request a checklist for your aircraft</h2>
<p class="lede">Don't see your aircraft? Tell us what you fly. Requests decide what gets
written next — ultralights, powered parachutes, kit and experimental aircraft especially.</p>

<form id="rq" class="rq" novalidate>
  <div class="f"><label for="rq-make">Make <span class="tag">(required)</span></label>
    <input id="rq-make" maxlength="60" required placeholder="ParaPlane, Kitfox, Cessna…"></div>
  <div class="f"><label for="rq-model">Model <span class="tag">(required)</span></label>
    <input id="rq-model" maxlength="60" required placeholder="PM-2, Series 7, 150…"></div>
  <div class="f"><label for="rq-variant">Engine / variant / year</label>
    <input id="rq-variant" maxlength="80" placeholder="Rotax 582, tri-gear, 1978…"></div>
  <div class="f"><label for="rq-cat">Category</label>
    <select id="rq-cat">
      <option value="">—</option>
      <option>Part 103 ultralight</option><option>Powered parachute</option>
      <option>Weight-shift trike</option><option>Light-sport</option>
      <option>Experimental / kit</option><option>Certified airplane</option>
      <option>Helicopter / gyro</option><option>Glider</option><option>Other</option>
    </select></div>
  <fieldset class="f"><legend>What would help most?</legend>
    <label><input type="checkbox" name="need" value="preflight"> Preflight / walkaround</label>
    <label><input type="checkbox" name="need" value="normal"> Normal procedures</label>
    <label><input type="checkbox" name="need" value="emergency"> Emergency procedures</label>
    <label><input type="checkbox" name="need" value="startup"> Engine start / run-up</label>
    <label><input type="checkbox" name="need" value="postflight"> Postflight / securing</label>
  </fieldset>
  <div class="f"><label for="rq-notes">Anything else? (mods, what's missing, where the manual falls short)</label>
    <textarea id="rq-notes" maxlength="1000" rows="4"></textarea></div>
  <div class="f"><label><input type="checkbox" id="rq-notify"> Email me when a checklist for this aircraft is available</label>
    <input id="rq-email" type="email" maxlength="254" placeholder="you@example.com" style="display:none"></div>
  <p><button class="cta" type="submit">Send request</button> <span id="rq-msg" role="status"></span></p>
  <p class="tag">We only use your email to tell you about this aircraft's checklist. See <a href="/privacy.html">privacy</a>.</p>
</form>
<p>Have the checklist already? <a href="/editor.html">Write it up in the editor</a> and publish it for other pilots.</p>
<style>.rq .f{margin:.7rem 0}.rq label{display:block}.rq input:not([type=checkbox]),.rq select,.rq textarea{width:100%;max-width:32rem;font:inherit;padding:.45rem}
.rq fieldset label{display:block;font-weight:400}#rq-msg{margin-left:.6rem}</style>
<script>
(function(){
  var f = document.getElementById('rq'), msg = document.getElementById('rq-msg');
  var notify = document.getElementById('rq-notify'), email = document.getElementById('rq-email');
  function v(id){ return (document.getElementById(id).value || '').trim(); }
  notify.addEventListener('change', function(){ email.style.display = notify.checked ? 'block' : 'none'; });
  f.addEventListener('submit', async function(ev){
    ev.preventDefault();
    if (!v('rq-make') || !v('rq-model')) { msg.textContent = 'Make and model are required.'; return; }
    var needs = Array.prototype.map.call(f.querySelectorAll('input[name=need]:checked'), function(x){ return x.value; });
    var body = {make: v('rq-make'), model: v('rq-model'), variant: v('rq-variant'), category: v('rq-cat'),
                needs: needs, notes: v('rq-notes'), notify: notify.checked, email: v('rq-email')};
    var headers = {'Content-Type': 'application/json'};
    var tok = sessionStorage.getItem('ocl:token'); if (tok) headers.Authorization = 'Bearer ' + tok;
    msg.textContent = 'Sending…';
    try {
      var r = await fetch('https://app.openchecklists.net/api/requests', {method: 'POST', headers: headers, body: JSON.stringify(body)});
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok) { msg.textContent = d.error || 'Something went wrong — try again.'; return; }
      if (window.oclTrack) oclTrack('checklist-request', {category: body.category || 'unspecified'});
      f.reset(); email.style.display = 'none';
      msg.textContent = '✓ Thanks — request received.';
    } catch (e) { msg.textContent = 'Could not reach the server — check your connection.'; }
  });
})();
</script>
"""


ADMIN = """
<h2>Site numbers</h2>
<p class="tag">Owner-only. Real usage from the database (the automated test account is
excluded). Traffic, referrers and events are in
<a href="https://analytics.keylinkit.net" rel="noopener">Umami</a> and Cloudflare Web Analytics.</p>
<div id="adm"><p>Loading…</p></div>
<style>#adm table{border-collapse:collapse;margin:.4rem 0 1.2rem}#adm td,#adm th{padding:.25rem .6rem;border-bottom:1px solid #e8edf4;text-align:left}</style>
<script>
(function(){
  var root = document.getElementById('adm');
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function table(rows, cols){
    if (!rows || !rows.length) return '<p class="tag">None yet.</p>';
    return '<table><thead><tr>' + cols.map(function(c){ return '<th>' + esc(c) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      rows.map(function(r){ return '<tr>' + cols.map(function(c){ return '<td>' + esc(r[c]) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table>';
  }
  var tok = sessionStorage.getItem('ocl:token');
  if (!tok) { root.innerHTML = '<p><a href="/profile.html">Sign in</a> first.</p>'; return; }
  fetch('https://app.openchecklists.net/api/admin/summary', {headers: {Authorization: 'Bearer ' + tok}})
    .then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function(d){
      var c = d.counts || {};
      root.innerHTML = '<h3>Counts</h3>' + table(Object.keys(c).map(function(k){ return {metric: k.replace(/_/g, ' '), value: c[k]}; }), ['metric', 'value']) +
        '<h3>Most-requested aircraft</h3>' + table(d.wanted, ['aircraft', 'n']) +
        '<h3>Latest checklist requests</h3>' + table(d.requests, ['created_at', 'make', 'model', 'variant', 'category', 'needs', 'notes', 'wants_notice']) +
        '<h3>Most-used checklists (includes bots and tests)</h3>' + table(d.top_used, ['checklist_id', 'uses', 'updated_at']);
    })
    .catch(function(){ root.innerHTML = '<p>Not available for this account.</p>'; });
})();
</script>
"""
