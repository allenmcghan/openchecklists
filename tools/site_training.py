#!/usr/bin/env python3
"""Flight training page: the free study library, and progress toward a certificate.

The study section is a catalogue of what the FAA publishes free, which is nearly
everything a student needs and is not obvious to find.

The progress section is the part nothing free does well: it reads a logbook — the one
saved in this browser, or a file — and reports it against the aeronautical experience
requirements in 14 CFR part 61, citing the paragraph for every line. It runs entirely
client-side, so a logbook never leaves the device.

It reports; it does not certify. Requirements a logbook cannot answer are listed and
left unchecked rather than guessed at, because a student who thinks a box is ticked
will stop looking at it.
"""

from __future__ import annotations

TRAINING_CSS = """
.skyace-card{background:#0a1628;border:1px solid #00d4ff33;border-radius:16px;
margin:1.4rem 0 2rem;overflow:hidden}
.skyace-header{display:flex;align-items:center;gap:1rem;padding:1rem 1.2rem;flex-wrap:wrap}
.skyace-logo{flex:none}
.skyace-text{flex:1;min-width:160px}
.skyace-title{font-size:1rem;font-weight:800;color:#00d4ff;margin-bottom:.2rem}
.skyace-desc{font-size:.82rem;color:#6688aa;margin:0;line-height:1.4}
.skyace-btn{flex:none;display:inline-block;background:#00aaff;color:#fff;font-weight:700;
font-size:.85rem;padding:.5rem 1rem;border-radius:8px;white-space:nowrap;
text-decoration:none}
.skyace-btn:hover{background:#0088cc;text-decoration:none}
.skyace-frame{display:block;width:100%;height:520px;border:none;background:#0a1628}
@media(max-width:600px){.skyace-frame{height:340px}}

.certtabs{display:flex;gap:.4rem;flex-wrap:wrap;margin:1rem 0 .6rem}
.certtab{font-size:.82rem;padding:.4rem .7rem;border:1px solid var(--line);border-radius:.35rem;
cursor:pointer;background:var(--bg)}
.certtab[aria-pressed=true]{background:var(--accent);color:#fff;border-color:transparent}
.reqtable{width:100%;border-collapse:collapse;font-size:.9rem}
.reqtable td{padding:.45rem .5rem;border-bottom:1px solid var(--line);vertical-align:top}
.reqtable td.mark{width:4.5rem;white-space:nowrap;font-size:.7rem;font-weight:700;
letter-spacing:.03em}
.m-met{color:var(--ok)}.m-short{color:var(--warn)}.m-unknown{color:var(--caut)}
.m-manual{color:var(--muted)}
.reqtable .cfr{font-size:.74rem;color:var(--muted);font-family:ui-monospace,Menlo,monospace}
.reqtable .note{font-size:.78rem;color:var(--caut);display:block;margin-top:.2rem}
.bar{height:.4rem;background:var(--line);border-radius:1rem;overflow:hidden;margin-top:.25rem;
max-width:14rem}
.bar span{display:block;height:100%;background:var(--ok)}
.bar.short span{background:var(--caut)}
.summary{display:flex;gap:1rem;flex-wrap:wrap;margin:.6rem 0;font-size:.85rem}
.summary b{font-size:1.3rem;display:block;font-variant-numeric:tabular-nums}
.studygrid{display:grid;gap:.6rem;grid-template-columns:repeat(auto-fit,minmax(17rem,1fr));margin:1rem 0}
.study{border:1px solid var(--line);border-radius:.4rem;padding:.6rem .8rem;background:var(--card)}
.study h4{margin:.1rem 0 .3rem;font-size:.95rem}
.study p{margin:0;font-size:.83rem;color:var(--muted)}
.study .num{font-family:ui-monospace,Menlo,monospace;font-size:.75rem}

/* Pilot-type selector grid */
.pilot-types{display:grid;gap:.9rem;grid-template-columns:1fr;margin:1.2rem 0 2rem}
@media(min-width:600px){.pilot-types{grid-template-columns:repeat(2,1fr)}}
@media(min-width:900px){.pilot-types{grid-template-columns:repeat(3,1fr)}}
.ptype{border:1px solid var(--line);border-radius:14px;padding:1.1rem;background:#fff;
display:flex;flex-direction:column;gap:.45rem;
transition:border-color .14s,box-shadow .14s,transform .14s}
.ptype:hover{border-color:var(--accent);box-shadow:0 6px 22px rgba(15,24,38,.09);transform:translateY(-2px)}
.ptype-icon{font-size:1.7rem;line-height:1}
.ptype strong{font-size:1rem;font-weight:700;display:block}
.ptype p{margin:0;font-size:.88rem;color:var(--muted);flex:1}
.ptype-tags{display:flex;flex-wrap:wrap;gap:.35rem}
.ptag{font-size:.7rem;font-weight:600;padding:.2rem .55rem;border-radius:999px;
background:var(--card);color:var(--muted);border:1px solid var(--line)}
.ptype-btn{margin-top:.3rem;padding:.55rem 1rem;border-radius:999px;border:1.5px solid var(--accent);
background:transparent;color:var(--accent);font:inherit;font-size:.88rem;font-weight:600;
cursor:pointer;align-self:flex-start;transition:background .12s,color .12s}
.ptype-btn:hover{background:var(--accent);color:#fff}
.cert-section{padding:1rem 0}

/* Quiz component */
.quiz{margin:1.2rem 0}
.qcard{border:1px solid var(--line);border-radius:14px;padding:1.1rem;background:#fff;margin:.8rem 0}
.qcard .qnum{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:.4rem}
.qcard .qtext{font-size:.97rem;font-weight:600;margin-bottom:.7rem}
.qopts{display:grid;gap:.4rem}
.qopt{padding:.65rem .85rem;border:1.5px solid var(--line);border-radius:10px;
font-size:.9rem;cursor:pointer;background:#fff;text-align:left;font:inherit;
transition:border-color .1s,background .1s;width:100%}
.qopt:hover:not(:disabled){border-color:var(--accent);background:var(--accent-weak)}
.qopt.correct{border-color:var(--ok);background:var(--ok-weak);color:#14521f;font-weight:600}
.qopt.wrong{border-color:var(--warn);background:var(--warn-weak);color:#7c1c16}
.qexplain{margin-top:.6rem;font-size:.85rem;color:var(--muted);padding:.6rem .8rem;
background:var(--card);border-radius:9px;display:none}
.qscore{font-size:.95rem;font-weight:700;margin-top:1rem;padding:.7rem 1rem;
border-radius:12px;background:var(--ok-weak);color:#14521f}
"""

TRAINING_BODY = """
<h1>Training &amp; Study</h1>
<p class="lede">From your first paramotor flight to an ATP certificate — free study
material, sample test questions, and a logbook hours tracker, all in one place.</p>

<h2>What do you want to fly?</h2>

<div class="pilot-types">
  <div class="ptype">
    <div class="ptype-icon">🛩</div>
    <strong>Ultralight &amp; Part 103</strong>
    <p>No certificate or exam required in the US for foot-launched paramotors, powered
    parachutes, and single-seat ultralights. But airspace, weather, and aerodynamics
    still matter. Start here for the essentials every pilot should know.</p>
    <div class="ptype-tags"><span class="ptag">No exam required</span><span class="ptag">No logbook required</span></div>
    <button class="ptype-btn" onclick="showCertSec('part103')">Study resources &rarr;</button>
  </div>
  <div class="ptype">
    <div class="ptype-icon">🚁</div>
    <strong>Remote Pilot &mdash; Part 107 (Drone)</strong>
    <p>Required to fly a drone commercially. One written exam, no flight test, no
    medical. Covers airspace, weather, and FAA regulations. Most people pass in a few
    weeks of focused study.</p>
    <div class="ptype-tags"><span class="ptag">Written exam only</span><span class="ptag">No flight hours</span><span class="ptag">Renewable every 2 years</span></div>
    <button class="ptype-btn" onclick="showCertSec('part107')">Study resources &rarr;</button>
  </div>
  <div class="ptype">
    <div class="ptype-icon">🪂</div>
    <strong>Sport Pilot (LSA)</strong>
    <p>Fly light-sport aircraft (including some powered parachutes and gyroplanes)
    without a medical certificate. Minimum 20 hours, written exam, practical test.</p>
    <div class="ptype-tags"><span class="ptag">Written + flight test</span><span class="ptag">20 hr minimum</span><span class="ptag">No medical</span></div>
    <button class="ptype-btn" onclick="showCertSec('sport')">Study resources &rarr;</button>
  </div>
  <div class="ptype">
    <div class="ptype-icon">✈</div>
    <strong>Private Pilot (PPL)</strong>
    <p>The foundation certificate for general aviation. Fly yourself and passengers,
    day or night, VFR. Minimum 40 hours. The starting point for most GA pilots.</p>
    <div class="ptype-tags"><span class="ptag">Written + flight test</span><span class="ptag">40 hr minimum</span><span class="ptag">3rd class medical</span></div>
    <button class="ptype-btn" onclick="showCertSec('private')">Study resources &rarr;</button>
  </div>
  <div class="ptype">
    <div class="ptype-icon">🌫</div>
    <strong>Instrument Rating (IFR)</strong>
    <p>Fly in clouds and low visibility by reference to instruments. Added on top of
    your PPL. Minimum 50 hours cross-country PIC time plus 40 hours instrument time.</p>
    <div class="ptype-tags"><span class="ptag">Written + flight test</span><span class="ptag">50 hr XC + 40 hr IFR</span></div>
    <button class="ptype-btn" onclick="showCertSec('instrument')">Study resources &rarr;</button>
  </div>
  <div class="ptype">
    <div class="ptype-icon">🛫</div>
    <strong>Commercial Pilot (CPL)</strong>
    <p>Get paid to fly. Minimum 250 hours total time. Higher precision standards than
    private. The commercial practical test is a benchmark many pilots aim for regardless
    of whether they plan a flying career.</p>
    <div class="ptype-tags"><span class="ptag">Written + flight test</span><span class="ptag">250 hr total</span><span class="ptag">2nd class medical</span></div>
    <button class="ptype-btn" onclick="showCertSec('commercial')">Study resources &rarr;</button>
  </div>
</div>

<!-- Per-certificate sections injected by JS based on button click -->
<div id="cert-detail" style="display:none">
  <div id="cert-study-grid" class="studygrid"></div>
  <h3 id="cert-quiz-title" style="margin-top:1.4rem"></h3>
  <p id="cert-quiz-note" class="lede" style="font-size:.88rem"></p>
  <div id="cert-quiz" class="quiz"></div>
</div>

<h2 style="margin-top:2rem">All free study material</h2>
<p class="lede">Almost everything a student pilot needs is published free by the FAA.
Almost none of it is easy to find. This page collects it, and tracks your logbook
hours against the actual CFR requirements.</p>

<div class="skyace-card">
  <div class="skyace-header">
    <div class="skyace-logo">
      <svg width="36" height="36" viewBox="0 0 64 64">
        <rect width="64" height="64" rx="10" fill="#0a1628"/>
        <path d="M32 12 L52 44 L32 38 L12 44 Z" fill="#00d4ff"/>
        <path d="M20 44 L32 42 L44 44 L32 52 Z" fill="#0077aa"/>
      </svg>
    </div>
    <div class="skyace-text">
      <div class="skyace-title">SkyAce — Flight Training Game</div>
      <p class="skyace-desc">Arcade missions: dogfights, ground attacks, carrier landings, guided training.
      Click inside to capture keyboard focus.</p>
    </div>
    <a href="https://skyace.gamercomp.com" class="skyace-btn" target="_blank" rel="noopener">
      Full screen ↗
    </a>
  </div>
  <iframe
    src="https://skyace.gamercomp.com"
    class="skyace-frame"
    allow="fullscreen"
    loading="lazy"
    title="SkyAce flight training game"
  ></iframe>
</div>

<h2 id="progress">Progress toward a certificate</h2>

<div class="banner okb"><strong>This reports, it does not certify.</strong> Every line
cites its CFR paragraph, and requirements a logbook cannot answer — an instructor's
endorsement, whether an airport had an operating tower — are listed and left
unchecked rather than guessed. Eligibility is determined by your instructor and your
examiner. The point is to stop you discovering a missing 0.4 hours the week of your
checkride.</div>

<div class="certtabs" id="certtabs"></div>

<div class="row" style="gap:.5rem;align-items:center;margin:.6rem 0">
  <button class="btn p" id="uselocal">Use my saved logbook</button>
  <button class="btn" id="openlb">Open a logbook file</button>
  <input type="file" id="lbfile" accept=".json,.oclb.json" hidden>
  <span class="hint" id="lbstatus">Nothing loaded yet.</span>
</div>

<div id="progress"></div>

<h2 id="study">Free study material</h2>
<p class="lede">All of it public domain, all of it current, none of it behind a
paywall. The handbooks are the source of the knowledge-test questions; the ACS is the
document your checkride is conducted against, task by task.</p>
<div id="study"></div>

<h2>What to read, in order</h2>
<ol>
  <li><strong>Pilot's Handbook of Aeronautical Knowledge</strong> — the core text.
  Read it once end to end early, then use it as reference.</li>
  <li><strong>The ACS for your certificate</strong> — read this second, not last.
  It tells you exactly what you will be tested on and to what tolerance, which makes
  everything else easier to prioritise.</li>
  <li><strong>Airplane Flying Handbook</strong> — the manoeuvres, and why each one
  is flown the way it is.</li>
  <li><strong>Aviation Weather Handbook</strong> and <strong>Risk Management
  Handbook</strong> — the two areas where accidents actually come from.</li>
  <li><strong>Instrument Flying Handbook</strong> once you start the rating.</li>
  <li><strong>14 CFR part 61 and part 91</strong> — dull, short, and the source of
  more checkride questions than anything else.</li>
</ol>
<p class="hint">Searchable full text of several of these is in the
<a href="search.html">troubleshooting search</a>, which cites document and page.</p>
"""

TRAINING_JS = r"""
(function(){

/* ---- Pilot-type section switcher ---- */
var CERT_STUDY = {
  part103: {
    title: 'Ultralight & Part 103 — Safety fundamentals',
    quizTitle: 'Sample questions — things every pilot should know',
    quizNote: 'Part 103 doesn\'t require an exam, but understanding these basics makes you safer. No trick questions — these are the concepts that matter.',
    docs: ['faa-phak','faa-awh','faa-rmh'],
    quizzes: [
      {q:'Which airspace requires a transponder and ADS-B Out above 10,000 ft MSL?',
       opts:['Class A','Class B, C, and all airspace above 10,000 ft MSL','Class D','Class E only'],
       ans:1, explain:'Transponder and ADS-B Out are required in Class B, C, the Mode C veil (30 nm of Class B airports), and all airspace above 10,000 ft MSL (excluding below 2,500 AGL). §91.215/217.'},
      {q:'What is the standard traffic pattern altitude for ultralights at uncontrolled airports?',
       opts:['500 ft AGL','800 ft AGL','1,000 ft AGL','1,500 ft AGL'],
       ans:2, explain:'The standard traffic pattern altitude is 1,000 ft AGL for most aircraft. Ultralights often use the same pattern at lower altitude — check local NOTAMs and the Chart Supplement.'},
      {q:'When is density altitude a concern for takeoff performance?',
       opts:['Only above 8,000 ft MSL','Any time temperature, humidity, or altitude is higher than standard','Only in summer months','Only for turbine aircraft'],
       ans:1, explain:'Density altitude equals pressure altitude corrected for non-standard temperature. High temperature, high humidity, or high field elevation all reduce air density, requiring longer takeoff rolls and reducing climb rate.'},
      {q:'A METAR shows wind 270/15G22KT. What does this mean?',
       opts:['Wind from 270° at 15 mph, gusting to 22','Wind from 270° at 15 knots, gusting to 22 knots','Wind to 270° at 15 knots','Wind rotating from 15° to 22°'],
       ans:1, explain:'METAR wind format is direction (true)/speed in knots. 270/15G22KT = wind FROM the west at 15 knots, gusting to 22 knots.'},
    ]
  },
  part107: {
    title: 'Remote Pilot Certificate — Part 107',
    quizTitle: 'Sample Part 107 knowledge test questions',
    quizNote: 'These are the types of questions on the FAA Remote Pilot knowledge test. Use the FAA\'s CATS or PSI test prep tools for actual practice questions.',
    docs: ['faa-phak','faa-awh'],
    quizzes: [
      {q:'Under Part 107, the maximum altitude for small UAS operations is:',
       opts:['200 ft AGL','400 ft AGL above the ground or structure','500 ft MSL','1,000 ft AGL'],
       ans:1, explain:'Under 14 CFR §107.51, small UAS may not be operated at an altitude higher than 400 ft above the ground, unless within 400 ft of a structure. Above a structure, operations may extend 400 ft above the structure\'s height.'},
      {q:'A remote pilot must report an accident to the FAA within 10 days if it results in:',
       opts:['Any property damage','Serious injury or property damage over $500 (excluding the sUAS)','Any injury to any person','Only fatalities'],
       ans:1, explain:'§107.9 requires reporting to the FAA within 10 days of an accident that causes serious injury to any person or property damage (other than the small UAS) in excess of $500.'},
      {q:'Which sectional chart symbol indicates Class D airspace?',
       opts:['Solid blue circle','Dashed blue circle','Dashed magenta circle','Solid magenta circle'],
       ans:1, explain:'Class D airspace is depicted on sectional charts with a dashed blue circle. Class C is a solid magenta circle. Class B is a solid blue circle with multiple rings.'},
      {q:'Under Part 107, a NOTAM is required before flying in:',
       opts:['Class G airspace','Controlled airspace (Class B, C, D, E surface area)','Any airspace below 400 ft AGL','Uncontrolled airspace at night'],
       ans:1, explain:'Under Part 107, you need either ATC authorization (via LAANC or DroneZone) or a waiver to fly in Class B, C, D, and E surface area airspace. You do not need authorization for Class G or E above 700 ft AGL.'},
    ]
  },
  sport: {
    title: 'Sport Pilot Certificate',
    quizTitle: 'Sample Sport Pilot knowledge test questions',
    quizNote: 'The Sport Pilot written test covers the same core topics as the Private Pilot written test but with reduced emphasis on instrument flying and complex systems.',
    docs: ['faa-phak','faa-awh','faa-rmh','acs-private-airplane'],
    quizzes: [
      {q:'The minimum visibility for Sport Pilot VFR flight in Class G airspace below 1,200 ft AGL during the day is:',
       opts:['1 SM','3 SM','5 SM','Clear of clouds only'],
       ans:0, explain:'For Class G airspace below 1,200 ft AGL during the day, the minimum visibility is 1 statute mile. At night and at higher altitudes, more visibility and cloud clearance is required. §91.155.'},
      {q:'A sport pilot may NOT fly an LSA in which situation?',
       opts:['At night','Above 10,000 ft MSL','In Class B airspace without ATC authorization','All of the above'],
       ans:3, explain:'Sport pilots operating under the sport pilot rules may not fly at night, above 10,000 ft MSL (or 2,000 ft AGL, whichever is higher), in Class A airspace, or in Class B, C, D airspace without ATC authorization.'},
    ]
  },
  private: {
    title: 'Private Pilot Certificate',
    quizTitle: 'Sample Private Pilot knowledge test questions',
    quizNote: 'The Private Pilot written (knowledge) test has 60 questions with a 2.5-hour time limit. A passing score is 70%.',
    docs: ['faa-phak','faa-awh','faa-rmh','faa-afh-8083-3c-ch2','acs-private-airplane'],
    quizzes: [
      {q:'Under what condition would a pilot be more susceptible to carbon monoxide poisoning?',
       opts:['Using supplemental oxygen above 12,500 ft','Flying with a defective exhaust system and heater on','Flying in cold temperatures','Flying above the cloud layer'],
       ans:1, explain:'Carbon monoxide from engine exhaust can enter the cabin through a defective exhaust system, particularly when the cabin heater is in use. CO is odorless and colorless — symptoms include headache, dizziness, and confusion.'},
      {q:'What is the VFR visibility and cloud clearance requirement in Class C airspace?',
       opts:['1 SM, clear of clouds','3 SM, 500 below / 1,000 above / 2,000 horizontal','5 SM, 1,000 below / 1,000 above / 1 mile horizontal','3 SM, clear of clouds'],
       ans:1, explain:'Class C, D, and E airspace require 3 SM visibility, 500 ft below clouds, 1,000 ft above clouds, and 2,000 ft horizontal from clouds. §91.155.'},
      {q:'The left-turning tendency of an aircraft caused by the corkscrew-shaped slipstream hitting the vertical fin is called:',
       opts:['Gyroscopic precession','Torque','Spiraling slipstream','P-factor'],
       ans:2, explain:'Spiraling slipstream is the rotation of the propeller wash that flows over and around the fuselage, striking the left side of the vertical stabilizer and creating a left-yawing tendency.'},
      {q:'Maximum speed in Class D airspace below 2,500 ft AGL within 4 NM of the primary airport:',
       opts:['156 knots','200 knots','250 knots','No restriction'],
       ans:1, explain:'§91.117 limits airspeed to 200 KIAS below 2,500 ft within 4 NM of a Class C or D primary airport. The general limit below 10,000 ft MSL is 250 KIAS.'},
    ]
  },
  instrument: {
    title: 'Instrument Rating',
    quizTitle: 'Sample Instrument Rating knowledge test questions',
    quizNote: 'The Instrument Rating written test (60 questions, 2.5 hours) emphasizes approach charts, holds, weather, and regulations.',
    docs: ['faa-phak','faa-awh','faa-ifh','acs-instrument-airplane'],
    quizzes: [
      {q:'On an ILS approach, what does it mean when the glideslope needle is above center?',
       opts:['You are above the glideslope; fly down','You are below the glideslope; fly up','You are right of course','The glideslope is inoperative'],
       ans:1, explain:'On a glideslope indicator, the needle shows where the glideslope is relative to you. Needle above center = glideslope is above you = you are below it. Fly up to capture. This is a "fly to" indicator.'},
      {q:'What is the minimum visibility for a CAT I ILS approach?',
       opts:['200 ft and 1/4 SM RVR 1800','200 ft DH and 1/2 SM','300 ft DH and 3/4 SM','100 ft and RVR 600'],
       ans:0, explain:'A standard CAT I ILS has a 200 ft decision height and an RVR of 1800 ft (roughly 1/4 SM). §91.175 and the approach plate govern the actual minimums for a specific procedure.'},
      {q:'During a standard-rate turn, what bank angle is required at 120 knots?',
       opts:['10°','15°','18°','22°'],
       ans:2, explain:'Standard-rate turn (3°/sec) bank angle ≈ (airspeed ÷ 10) + 7 = 12 + 7 = approximately 18°. More precisely, bank = arctan(0.0524 × airspeed). At 120 KIAS this is about 18°.'},
    ]
  },
  commercial: {
    title: 'Commercial Pilot Certificate',
    quizTitle: 'Sample Commercial Pilot knowledge test questions',
    quizNote: 'The Commercial written test builds on Private and Instrument topics, adding complex aircraft systems, high-altitude flight, and commercial operations.',
    docs: ['faa-phak','faa-awh','faa-ifh','faa-wb','acs-commercial-airplane'],
    quizzes: [
      {q:'What action is required when an aircraft is overloaded at takeoff?',
       opts:['Add fuel to restore the proper CG','Reduce the load to within approved limits before flight','Proceed with a reduced-power takeoff','File a weight-and-balance deviation report'],
       ans:1, explain:'Operating in excess of the certificated maximum gross weight violates the aircraft\'s type certificate and creates an airworthiness issue. The load must be reduced before flight.'},
      {q:'The definition of "commercial operator" under 14 CFR Part 1 includes:',
       opts:['Any person who flies for hire','A person who, for compensation or hire, engages in the carriage of persons or property by aircraft','Any person holding a commercial pilot certificate','Any operator of an air carrier'],
       ans:1, explain:'14 CFR §1.1 defines commercial operator as "a person who, for compensation or hire, engages in the carriage of persons or property by aircraft in air commerce." Simply holding a commercial certificate does not make one a commercial operator.'},
    ]
  }
};

function buildQuiz(quizzes, containerId){
  var el=document.getElementById(containerId);
  if(!el||!quizzes||!quizzes.length) return;
  var answered=0, correct=0;
  var html='';
  quizzes.forEach(function(q,i){
    html+='<div class="qcard" id="qcard-'+containerId+'-'+i+'">';
    html+='<div class="qnum">Question '+(i+1)+' of '+quizzes.length+'</div>';
    html+='<div class="qtext">'+q.q+'</div>';
    html+='<div class="qopts">';
    q.opts.forEach(function(opt,j){
      html+='<button class="qopt" onclick="answerQ('+JSON.stringify(containerId)+','+i+','+j+')">'
        +(String.fromCharCode(65+j)+'. ')+opt+'</button>';
    });
    html+='</div>';
    html+='<div class="qexplain" id="qexp-'+containerId+'-'+i+'">'+q.explain+'</div>';
    html+='</div>';
  });
  el.innerHTML=html;
}

window.answerQ=function(containerId,qi,chosen){
  var q=null;
  Object.values(CERT_STUDY).forEach(function(c){
    if(c.quizzes&&c.quizzes[qi]!==undefined&&document.getElementById('cert-quiz')&&
       document.getElementById('cert-quiz').contains(document.getElementById('qcard-'+containerId+'-'+qi)))
      q=c.quizzes[qi];
  });
  if(!q){
    // find quiz in any cert
    for(var k in CERT_STUDY){ if(CERT_STUDY[k].quizzes&&CERT_STUDY[k].quizzes[qi]){q=CERT_STUDY[k].quizzes[qi];break;}}
  }
  if(!q) return;
  var card=document.getElementById('qcard-'+containerId+'-'+qi);
  if(!card) return;
  var btns=card.querySelectorAll('.qopt');
  btns.forEach(function(b){ b.disabled=true; });
  btns[chosen].classList.add(chosen===q.ans?'correct':'wrong');
  if(chosen!==q.ans) btns[q.ans].classList.add('correct');
  var expEl=document.getElementById('qexp-'+containerId+'-'+qi);
  if(expEl) expEl.style.display='block';
  // Award points for correct answers (3 pts each via OCL API)
  if(chosen===q.ans && typeof oclReq==='function'){
    oclReq('POST','/me/quiz',{question:q.q}).catch(function(){});
  }
};

window.showCertSec=function(certKey){
  var cert=CERT_STUDY[certKey];
  if(!cert) return;
  var detail=document.getElementById('cert-detail');
  if(detail){
    detail.style.display='block';
    // Scroll to it
    detail.scrollIntoView({behavior:'smooth',block:'start'});
  }
  var titleEl=document.getElementById('cert-quiz-title');
  if(titleEl) titleEl.textContent=cert.quizTitle||'';
  var noteEl=document.getElementById('cert-quiz-note');
  if(noteEl) noteEl.textContent=cert.quizNote||'';
  // Build study grid
  var grid=document.getElementById('cert-study-grid');
  if(grid){
    grid.innerHTML='';
    if(window.OCL_STUDY_DOCS){
      var docs=window.OCL_STUDY_DOCS.filter(function(d){ return !cert.docs||cert.docs.indexOf(d.id)>=0; });
      if(!docs.length) docs=window.OCL_STUDY_DOCS.slice(0,4);
      docs.forEach(function(d){
        grid.innerHTML+='<div class="study"><h4><a href="'+d.url+'" target="_blank" rel="noopener">'+d.title+'</a></h4>'
          +'<p>'+d.desc+'</p>'
          +(d.pages?'<div class="num">'+d.pages+' pages</div>':'')+'</div>';
      });
    }
  }
  // Build quiz
  buildQuiz(cert.quizzes,'cert-quiz');
};

/* ---- existing cert tracker and study grid ---- */
  var CERTS = null, current = null, BOOK = null;
  var LIB_KEY = 'ocl.logbook.v1';

  function el(id){ return document.getElementById(id); }
  function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  var STUDY = [
    {t:'Pilot’s Handbook of Aeronautical Knowledge', n:'FAA-H-8083-25C',
     d:'The core knowledge text. Basis of the private pilot knowledge test.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak',
     s:'faa-phak'},
    {t:'Airplane Flying Handbook', n:'FAA-H-8083-3C',
     d:'Manoeuvres, procedures and why each is flown the way it is.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/airplane_handbook'},
    {t:'Aviation Weather Handbook', n:'FAA-H-8083-28B',
     d:'Replaced AC 00-6, AC 00-45, AC 00-24, AC 00-30 and AC 00-54. Weather theory plus how to read every product.',
     u:'https://www.faa.gov/sites/faa.gov/files/FAA-H-8083-28B.pdf', s:'faa-awh'},
    {t:'Risk Management Handbook', n:'FAA-H-8083-2A',
     d:'Decision making and hazard identification. Where accidents actually come from.',
     u:'https://www.faa.gov/sites/faa.gov/files/2022-06/risk_management_handbook_2A.pdf', s:'faa-rmh'},
    {t:'Instrument Flying Handbook', n:'FAA-H-8083-15B',
     d:'The instrument rating knowledge text.',
     u:'https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/FAA-H-8083-15B.pdf',
     s:'faa-ifh'},
    {t:'Instrument Procedures Handbook', n:'FAA-H-8083-16B',
     d:'IFR procedures in practice: departures, arrivals, approaches.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Aircraft Weight and Balance Handbook', n:'FAA-H-8083-1',
     d:'Weight and balance theory and computation. Essential for modified aircraft.',
     u:'https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/FAA-H-8083-1.pdf',
     s:'faa-wb'},
    {t:'Aviation Instructor’s Handbook', n:'FAA-H-8083-9B',
     d:'How to teach. Required reading for the CFI, useful for any student.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'Airman Certification Standards', n:'FAA-S-ACS series',
     d:'What your checkride tests, task by task, with tolerances. Read early.',
     u:'https://www.faa.gov/training_testing/testing/acs'},
    {t:'Glider, Helicopter, Balloon and Powered Parachute Flying Handbooks', n:'FAA-H-8083 series',
     d:'Full handbooks for every category, including weight-shift control.',
     u:'https://www.faa.gov/regulations_policies/handbooks_manuals/aviation'},
    {t:'14 CFR (the FARs) and the AIM', n:'part 61, 91',
     d:'The regulations themselves, always current, free on eCFR.',
     u:'https://www.ecfr.gov/current/title-14'},
    {t:'Chart User’s Guide', n:'FAA',
     d:'How to read every symbol on a sectional and an approach plate.',
     u:'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/aero_guide/'},
    {t:'Airman Knowledge Testing Supplements', n:'FAA-CT-8080 series',
     d:'The figure booklets you are given in the test. Practise with the real ones.',
     u:'https://www.faa.gov/training_testing/testing/supplements'},
    {t:'Advisory Circulars', n:'AC series',
     d:'Thousands of them, free. AC 43.13-1B is the maintenance one worth knowing.',
     u:'https://www.faa.gov/regulations_policies/advisory_circulars'},
    {t:'FAA Safety Briefing', n:'magazine',
     d:'Bi-monthly, free, genuinely good on human factors and recurring mistakes.',
     u:'https://www.faa.gov/newsroom/safety-briefing'},
    {t:'WINGS Pilot Proficiency Program', n:'FAASafety.gov',
     d:'Free courses that also satisfy the flight review requirement.',
     u:'https://www.faasafety.gov/'}
  ];

  el('study').innerHTML = '<div class="studygrid">' + STUDY.map(function(s){
    // Cards for documents held in the on-site index also link into it, scoped to
    // that document. The card still links to the FAA original first, because that
    // is the authoritative copy and ours is a search index over it.
    var here = s.s ? ' · <a href="search.html?doc=' + encodeURIComponent(s.s) +
      '">search it here</a>' : '';
    return '<div class="study"><h4><a href="' + esc(s.u) + '" rel="noopener">' + esc(s.t) +
      '</a></h4><p><span class="num">' + esc(s.n) + '</span> — ' + esc(s.d) + here + '</p></div>';
  }).join('') + '</div>';

  async function boot(){
    try {
      CERTS = await (await fetch('data/training/certificates.json')).json();
    } catch (e) {
      el('progress').innerHTML = '<div class="banner quar">Certificate requirement data is ' +
        'not built. Run <code>tools/training.py emit</code> and rebuild. Serving over HTTP ' +
        'is required.</div>';
      return;
    }
    el('certtabs').innerHTML = CERTS.certificates.map(function(c, i){
      return '<span class="certtab" role="button" tabindex="0" data-c="' + esc(c.id) + '" ' +
        'aria-pressed="' + (i === 1 ? 'true' : 'false') + '">' + esc(c.name) + '</span>';
    }).join('');
    current = CERTS.certificates[1] || CERTS.certificates[0];

    Array.prototype.forEach.call(document.querySelectorAll('.certtab'), function(t){
      function pick(){
        Array.prototype.forEach.call(document.querySelectorAll('.certtab'), function(o){
          o.setAttribute('aria-pressed', o === t ? 'true' : 'false');
        });
        current = CERTS.certificates.filter(function(c){ return c.id === t.dataset.c; })[0];
        render();
      }
      t.addEventListener('click', pick);
      t.addEventListener('keydown', function(e){
        if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pick(); }
      });
    });

    el('uselocal').addEventListener('click', function(){
      var saved = null;
      try { saved = JSON.parse(localStorage.getItem(LIB_KEY) || 'null'); } catch (e) {}
      if (!saved){
        el('lbstatus').textContent = 'No logbook saved in this browser yet. Open a file instead.';
        return;
      }
      BOOK = saved;
      el('lbstatus').textContent = 'Using your saved logbook (' +
        (saved.entries || []).length + ' entries).';
      render();
    });
    el('openlb').addEventListener('click', function(){ el('lbfile').click(); });
    el('lbfile').addEventListener('change', function(e){
      var f = e.target.files[0]; if (!f) return;
      var r = new FileReader();
      r.onload = function(){
        try {
          BOOK = JSON.parse(r.result);
          el('lbstatus').textContent = 'Loaded ' + f.name + ' (' +
            (BOOK.entries || []).length + ' entries). It stays in this browser.';
          render();
        } catch (err){ el('lbstatus').textContent = 'Could not read that file: ' + err.message; }
      };
      r.readAsText(f);
    });

    render();
  }

  // Mirrors tools/training.py. Conservative in the same direction: intersected
  // buckets take the smaller of the two per entry, so this understates rather
  // than overstates.
  function hours(bucket, opt){
    opt = opt || {};
    var total = 0;
    (BOOK.entries || []).forEach(function(e){
      var t = e.times || {}, v = t[bucket] || 0;
      if (opt.also) v += t[opt.also] || 0;
      if (opt.pic) v = Math.min(v, t.pilot_in_command || 0);
      if (opt.solo) v = Math.min(v, t.solo || 0);
      total += v;
    });
    var cf = ((BOOK.carried_forward || {}).totals) || {};
    if (!opt.pic && !opt.solo){
      total += cf[bucket] || 0;
      if (opt.also) total += cf[opt.also] || 0;
    }
    return Math.round(total * 10) / 10;
  }
  function dualInstrument(){
    var total = 0;
    (BOOK.entries || []).forEach(function(e){
      var t = e.times || {};
      total += Math.min((t.actual_instrument||0) + (t.simulated_instrument||0), t.dual_received||0);
    });
    return Math.round(total * 10) / 10;
  }

  function flightTests(){
    var E = BOOK.entries || [], out = {};
    function put(k, met, detail, unknown){ out[k] = {met:met, detail:detail, unknown:!!unknown}; }

    var nightXc = E.filter(function(e){ return (e.times||{}).night > 0 && (e.times||{}).cross_country > 0; });
    var withD = nightXc.filter(function(e){ return ((e.route||{}).distance_nm||0) > 0; });
    var over = withD.filter(function(e){ return e.route.distance_nm >= 100; });
    if (over.length) put('night_xc_100nm', true, over[0].date + ', ' + over[0].route.distance_nm + ' nm');
    else if (nightXc.length && !withD.length)
      put('night_xc_100nm', false, nightXc.length + ' night cross-country flight(s) but none records a distance', true);
    else put('night_xc_100nm', false, 'no night cross-country over 100 nm found');

    var nl = E.reduce(function(a,e){ return a + ((e.landings||{}).full_stop_night||0); }, 0);
    put('night_10_landings', nl >= 10, nl + ' night full-stop landing(s) logged');

    var soloXc = E.filter(function(e){ return (e.times||{}).solo > 0 && ((e.route||{}).distance_nm||0) > 0; });
    var s150 = soloXc.filter(function(e){ return e.route.distance_nm >= 150; });
    if (s150.length) put('solo_xc_150nm', true, s150[0].date + ', ' + s150[0].route.distance_nm +
      ' nm — confirm three points and a 50 nm leg');
    else {
      var anySolo = E.filter(function(e){ return (e.times||{}).solo > 0; });
      put('solo_xc_150nm', false, 'no solo cross-country of 150 nm found' +
        (anySolo.length && !soloXc.length ? ' (solo flights logged without distances)' : ''),
        anySolo.length && !soloXc.length);
    }

    put('towered_3_landings', false, 'cannot be determined from a logbook — whether an ' +
      'airport had an operating control tower is not a logged field', true);

    var ifr = E.filter(function(e){
      return (((e.instrument||{}).approaches)||[]).length >= 3 && ((e.route||{}).distance_nm||0) >= 250; });
    if (ifr.length){
      var kinds = {}; ifr[0].instrument.approaches.forEach(function(a){ kinds[a.type] = 1; });
      var n = Object.keys(kinds).length;
      put('ifr_xc_250nm', n >= 3, ifr[0].date + ', ' + ifr[0].route.distance_nm + ' nm, ' +
        n + ' kind(s) of approach');
    } else put('ifr_xc_250nm', false, 'no IFR cross-country of 250 nm with three approach types found');

    [['day_xc_100nm_2h', false], ['night_xc_100nm_2h', true]].forEach(function(pair){
      var c = E.filter(function(e){
        var t = e.times || {};
        return (t.total||0) >= 2 && ((e.route||{}).distance_nm||0) >= 100 &&
          (pair[1] ? (t.night||0) > 0 : (t.day||0) > 0); });
      put(pair[0], !!c.length, c.length ? c[0].date + ', ' + c[0].route.distance_nm + ' nm, ' +
        c[0].times.total + ' h' : 'not found');
    });

    var x300 = E.filter(function(e){ return ((e.route||{}).distance_nm||0) >= 300; });
    put('commercial_xc_300nm', !!x300.length, x300.length ? x300[0].date + ', ' +
      x300[0].route.distance_nm + ' nm — confirm three points and a 250 nm leg'
      : 'no cross-country of 300 nm found');

    return out;
  }

  function render(){
    if (!current) return;
    var head = '<h3>' + esc(current.name) + ' <span class="cfr">' + esc(current.cfr) +
      '</span></h3><p class="sub">' + esc(current.summary) + '</p>';

    if (!BOOK){
      head += '<table class="reqtable"><tbody>' + current.requirements.map(function(r){
        var tag = r.kind === 'manual' ? 'manual' : (r.hours ? r.hours + ' h' : 'flight');
        return '<tr><td class="mark m-manual">' + esc(tag) + '</td><td>' + esc(r.label) +
          '<span class="cfr"> ' + esc(r.cfr) + '</span></td></tr>';
      }).join('') + '</tbody></table>' +
      '<p class="hint">Load a logbook above to see what you have against these.</p>';
      el('progress').innerHTML = head;
      return;
    }

    var tests = flightTests(), met = 0, short_ = 0, manual = 0, unknown = 0;
    var rows = current.requirements.map(function(r){
      var mark, cls, body = esc(r.label) + '<span class="cfr"> ' + esc(r.cfr) + '</span>';
      if (r.kind === 'manual'){ mark = 'confirm'; cls = 'manual'; manual++; }
      else if (r.kind === 'flight'){
        var f = tests[r.test] || {met:false, unknown:true, detail:'not evaluated'};
        if (f.unknown){ mark = '?'; cls = 'unknown'; unknown++; }
        else { mark = f.met ? 'met' : 'short'; cls = f.met ? 'met' : 'short'; f.met ? met++ : short_++; }
        body += '<span class="note">' + esc(f.detail) + '</span>';
      } else {
        var have = r.kind === 'dual' ? hours('dual_received')
                 : r.kind === 'solo' ? hours('solo')
                 : r.kind === 'dual_instrument' ? dualInstrument()
                 : hours(r.bucket, {pic:r.pic_only, solo:r.solo_only, also:r.also});
        var ok = have >= r.hours;
        mark = ok ? 'met' : 'short'; cls = ok ? 'met' : 'short'; ok ? met++ : short_++;
        var pct = Math.min(100, Math.round(have / r.hours * 100));
        body += '<span class="note">have ' + have + ' of ' + r.hours + ' h' +
          (ok ? '' : ', ' + (Math.round((r.hours - have) * 10) / 10) + ' h remaining') + '</span>' +
          '<div class="bar' + (ok ? '' : ' short') + '"><span style="width:' + pct + '%"></span></div>';
        var cf = ((BOOK.carried_forward || {}).totals) || {};
        if ((r.pic_only || r.solo_only) && cf[r.bucket]){
          body += '<span class="note">excludes ' + cf[r.bucket] + ' h carried forward — a ' +
            'carried-forward total records no overlap with PIC or solo time, so count those by hand</span>';
        }
      }
      return '<tr><td class="mark m-' + cls + '">' + mark + '</td><td>' + body + '</td></tr>';
    }).join('');

    el('progress').innerHTML = head +
      '<div class="summary"><div><b class="m-met">' + met + '</b> met</div>' +
      '<div><b class="m-short">' + short_ + '</b> short</div>' +
      '<div><b class="m-unknown">' + unknown + '</b> undetermined</div>' +
      '<div><b class="m-manual">' + manual + '</b> to confirm</div></div>' +
      '<table class="reqtable"><tbody>' + rows + '</tbody></table>' +
      '<p class="hint">Computed from your logbook in this browser. Nothing was uploaded. ' +
      'Authority is <a href="' + esc(CERTS.ecfr) + '" rel="noopener">14 CFR part 61</a>, ' +
      'not this page.</p>';
  }

  boot();
})();
"""


def training_page(head_fn, foot: str) -> str:
    return (
        head_fn(
            "Flight training — Open Checklists",
            "Free FAA study material for student through commercial pilots, and progress "
            "toward a certificate computed from your own logbook.",
        )
        + f"<style>{TRAINING_CSS}</style>"
        + TRAINING_BODY
        + f"<script>{TRAINING_JS}</script>"
        + foot
    )
