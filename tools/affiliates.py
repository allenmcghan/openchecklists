"""Amazon Associates gear suggestions for the static site.

Links are Amazon *search* URLs, never guessed ASINs: a search link cannot rot
into a dead or wrong product, and it lets Amazon show whatever is currently
stocked. No prices anywhere — the Associates operating agreement forbids static
prices, and they would be stale within a week anyway.

Nothing in here is rendered unless the build is given --amazon-tag. An untagged
gear box earns nothing and only clutters the page, so the build emits no
affiliate HTML at all without a tag.

Boxes never go inside a checklist's item list and never print.
"""

from __future__ import annotations

import html
import re
import urllib.parse
import zlib

TAG_RE = re.compile(r"^[a-z0-9-]+-2[0-9]$")

DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."

# key -> (name, why a pilot wants it, Amazon search query)
ITEMS: dict[str, tuple[str, str, str]] = {
    # Universal pilot gear
    "anr_headset": ("ANR aviation headset",
                    "Active noise reduction cuts the fatigue that cockpit noise causes on longer flights.",
                    "ANR aviation headset"),
    "pnr_headset": ("Passive (PNR) aviation headset",
                    "Durable, battery-free and affordable: a good first headset or a passenger spare.",
                    "passive aviation headset"),
    "kneeboard": ("Pilot kneeboard",
                  "Keeps clearances, frequencies and your checklist on your leg instead of the floor.",
                  "pilot kneeboard"),
    "tablet_mount": ("Tablet kneeboard / yoke mount",
                     "Holds an iPad or tablet EFB where you can see it without it sliding around.",
                     "tablet kneeboard aviation"),
    "flight_bag": ("Pilot flight bag",
                   "One place for headset, documents, charts and spare batteries.",
                   "pilot flight bag"),
    "flashlight": ("Red/white LED flashlight",
                   "White light for the walkaround, red to read the panel without losing night vision.",
                   "red white LED aviation flashlight"),
    "fuel_tester": ("Fuel sampler / tester",
                    "Checks sumped fuel for water, sediment and the right colour on every preflight.",
                    "aircraft fuel sampler tester"),
    "sunglasses": ("Non-polarized pilot sunglasses",
                   "Polarized lenses can black out some displays and hide glare off other traffic.",
                   "non polarized pilot sunglasses"),
    "e6b": ("E6B flight computer",
            "The manual wind-triangle computer: no batteries, and still taught for the knowledge test.",
            "E6B flight computer"),
    "cx3": ("ASA CX-3 flight computer",
            "Electronic flight computer you can take into the FAA knowledge test.",
            "ASA CX-3 flight computer"),
    "logbook": ("Pilot logbook",
                "A paper logbook to record time and endorsements your examiner can read at a glance.",
                "pilot logbook"),
    "chart_supplement": ("FAA Chart Supplement",
                         "Airport, frequency and procedure data in print for when the tablet dies.",
                         "FAA chart supplement"),
    "poh_binder": ("POH binder & sheet protectors",
                   "Keeps the POH and printed checklists readable after years of fuel and coffee.",
                   "POH binder pilot sheet protectors"),
    "tiedowns": ("Portable tie-down kit",
                 "For away fields with no ropes, or ropes you would rather not trust.",
                 "aircraft tie down kit"),
    "chocks": ("Wheel chocks",
               "Stops the aircraft rolling on a sloped ramp while you load or preflight.",
               "aircraft wheel chocks"),
    "covers": ("Cowl plugs & pitot cover",
               "Keeps birds, wasps and water out of the engine and pitot tube between flights.",
               "cowl plugs pitot cover"),
    "stratux": ("Stratux ADS-B receiver kit",
                "Low-cost portable ADS-B In: traffic and weather on your tablet app.",
                "Stratux ADS-B receiver"),
    "sentry": ("Sentry portable ADS-B receiver",
               "Traffic, weather and backup attitude in one box, with a built-in CO detector.",
               "Sentry ADS-B receiver"),
    "co_detector": ("Aviation carbon monoxide detector",
                    "A cracked exhaust feeding the cabin heat is silent; a detector is not.",
                    "aviation carbon monoxide detector"),
    "handheld_radio": ("Handheld aviation radio",
                       "A backup transceiver, or the only radio in an aircraft without one.",
                       "handheld aviation transceiver"),
    # Ultralight / Part 103 / powered parachute / paramotor
    "comms_helmet": ("Helmet with built-in headset",
                     "Head protection plus intercom and radio for open cockpits and paramotors.",
                     "ultralight helmet with headset"),
    "flight_suit": ("Flight suit",
                    "Wind and abrasion protection when there is no cabin around you.",
                    "flight suit pilot"),
    "gloves": ("Flying gloves",
               "Grip and warmth: the airflow in an open cockpit is cold even in summer.",
               "pilot flying gloves"),
    "wind_meter": ("Handheld wind meter",
                   "Measure the surface wind before committing a light wing to a takeoff.",
                   "handheld anemometer wind meter"),
    "windsock": ("Portable windsock",
                 "Shows wind direction and gusts at a field with no sock of its own.",
                 "portable windsock pole"),
    "two_stroke_oil": ("2-stroke engine oil",
                       "Use the oil type and ratio your engine manufacturer specifies — nothing else.",
                       "2 stroke engine oil"),
    "mix_bottle": ("2-stroke oil mixing bottle",
                   "Measures oil accurately so the fuel/oil ratio is right every fill.",
                   "2 stroke oil ratio mixing bottle"),
    "fuel_can": ("Fuel can",
                 "For hauling fuel to fields with no pump.",
                 "fuel can 5 gallon"),
    "reserve_info": ("Reserve parachute (research)",
                     "Compare models here, but buy, fit and repack through a qualified rigger.",
                     "ultralight reserve parachute"),
    "ppg_book": ("Powered paragliding & ultralight books",
                 "Training and technique references for flying light wings.",
                 "powered paragliding bible"),
    # Light-sport and experimental builders
    "rivet_tool": ("Hand rivet puller",
                   "Pulled-rivet tool for kit assembly and field repairs.",
                   "hand rivet tool aircraft"),
    "clecos": ("Cleco fastener kit",
               "Temporary fasteners that hold skins in place while you drill and rivet.",
               "cleco fastener kit"),
    "deburr": ("Deburring tool",
               "Removes burrs from drilled holes, which become crack starters if left.",
               "deburring tool"),
    "safety_wire": ("Safety wire pliers",
                    "Twist and cut safety wire quickly and consistently.",
                    "safety wire pliers"),
    "torque_wrench": ("Inch-pound torque wrench",
                      "AN hardware torques are in inch-pounds; a small-range wrench hits them accurately.",
                      "inch pound torque wrench"),
    "an_hardware": ("AN hardware assortment",
                    "AN bolts, nuts and washers to have on the bench — match them to your plans.",
                    "AN hardware kit aircraft"),
    "ac43": ("AC 43.13-1B/2B in print",
             "The FAA's acceptable methods for inspection and repair, on the workbench.",
             "AC 43.13-1B acceptable methods techniques practices"),
    "std_handbook": ("Standard Aircraft Handbook",
                     "Shop-practice reference for hardware, rivets, tubing and fittings.",
                     "Standard Aircraft Handbook for Mechanics and Technicians"),
    # Training and test prep
    "far_aim": ("ASA FAR/AIM",
                "The regulations and the Aeronautical Information Manual in one current book.",
                "ASA FAR AIM"),
    "phak": ("Pilot's Handbook of Aeronautical Knowledge (print)",
             "The core FAA text behind the knowledge test, easier to study on paper.",
             "Pilot's Handbook of Aeronautical Knowledge"),
    "afh": ("Airplane Flying Handbook (print)",
            "How each manoeuvre is flown, and why.",
            "Airplane Flying Handbook FAA"),
    "weather_hb": ("Aviation Weather Handbook (print)",
                   "Weather is where accidents come from; this is the FAA's reference.",
                   "Aviation Weather Handbook FAA"),
    "ppl_testprep": ("Private pilot test prep book",
                     "Practice questions with explanations for the FAA knowledge test.",
                     "private pilot test prep book"),
    "ppl_oral": ("Private pilot oral exam guide",
                 "Rehearse the questions an examiner is likely to ask on checkride day.",
                 "private pilot oral exam guide"),
    "ifr_oral": ("Instrument rating oral exam guide",
                 "The same idea for the instrument checkride.",
                 "instrument rating oral exam guide"),
    "sport_testprep": ("Sport pilot test prep",
                       "Knowledge-test practice for the sport pilot certificate.",
                       "sport pilot test prep"),
    "part107": ("Remote pilot (Part 107) test prep",
                "Knowledge-test practice for the commercial drone certificate.",
                "remote pilot part 107 test prep"),
}

# Gear lists, most relevant first. A box shows the head of the list (after a
# stable per-page rotation of the tail, so not every page shows the same eight).
GEAR: dict[str, list[str]] = {
    "universal": ["anr_headset", "kneeboard", "fuel_tester", "flashlight", "sunglasses", "sentry",
                  "co_detector", "covers", "stratux", "tablet_mount", "flight_bag", "pnr_headset",
                  "e6b", "cx3", "logbook", "chart_supplement", "poh_binder", "tiedowns", "chocks",
                  "handheld_radio"],
    "glider": ["kneeboard", "sunglasses", "handheld_radio", "stratux", "sentry", "logbook", "e6b",
               "tiedowns", "flight_bag", "tablet_mount"],
    "ultralight": ["comms_helmet", "wind_meter", "flight_suit", "gloves", "handheld_radio",
                   "fuel_can", "windsock", "reserve_info", "ppg_book", "kneeboard", "stratux",
                   "sunglasses"],
    "two_stroke": ["two_stroke_oil", "mix_bottle"],
    "builder": ["torque_wrench", "safety_wire", "clecos", "rivet_tool", "deburr", "an_hardware",
                "ac43", "std_handbook"],
    "test_prep": ["far_aim", "phak", "ppl_testprep", "ppl_oral", "cx3", "e6b", "afh",
                  "weather_hb", "sport_testprep", "ifr_oral", "part107", "logbook"],
}

# Aircraft category (schema enum) -> gear lists to draw from, in order.
CATEGORY_GEAR: dict[str, list[str]] = {
    "part103_ultralight": ["ultralight"],
    "powered_parachute": ["ultralight"],
    "weight_shift_control": ["ultralight"],
    "light_sport": ["builder", "universal"],
    "experimental_amateur_built": ["builder", "universal"],
    "experimental_exhibition": ["builder", "universal"],
    "glider": ["glider"],
}

CSS = """
.aff-box{margin:2rem 0;padding:1.1rem 1.2rem;border:1px solid #e3e7ef;border-radius:14px;background:#fbfcfe;
font-size:.92rem;color:#1f2a3a}
.aff-box .aff-lbl{margin:0;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:#6b7686;font-weight:700}
.aff-box h2{margin:.15rem 0 .7rem;font-size:1.08rem;letter-spacing:-.01em}
.aff-box ul{list-style:none;margin:0;padding:0;display:grid;gap:.55rem;
grid-template-columns:repeat(auto-fill,minmax(15rem,1fr))}
.aff-box li{margin:0;padding:.55rem .7rem;border:1px solid #e9edf3;border-radius:10px;background:#fff}
.aff-box li a{font-weight:650;color:#1f4e79}
.aff-box li span{display:block;color:#5b6576;font-size:.84rem;margin-top:.15rem;line-height:1.35}
.aff-box .aff-disc{margin:.8rem 0 0;font-size:.78rem;color:#6b7686}
@media print{.aff-box{display:none!important}}
"""


def validate_tag(tag: str) -> str:
    if not TAG_RE.match(tag):
        raise SystemExit("--amazon-tag must look like yourtag-20 (lowercase letters, digits, hyphens, ending -2N)")
    return tag


def search_url(query: str, tag: str) -> str:
    return "https://www.amazon.com/s?" + urllib.parse.urlencode({"k": query, "tag": tag})


def gear_lists_for(aircraft: dict | None) -> list[str]:
    """Which GEAR lists suit an aircraft block (schema `aircraft` object)."""
    ac = aircraft or {}
    lists = list(CATEGORY_GEAR.get(ac.get("category") or "", ["universal"]))
    engines = ac.get("engine") or []
    if any((e or {}).get("type") == "piston_2stroke" for e in engines):
        # Oil and mixing gear goes right after the first list's lead items.
        lists.insert(1 if lists[0] == "ultralight" else 0, "two_stroke")
    return lists


def pick(lists: list[str], seed: str = "", limit: int = 8) -> list[str]:
    """The first four items of each list (the essentials) come first; the rest
    is filled from the lists' tails, rotated by a stable hash of `seed` so
    neighbouring pages don't all show the same eight."""
    keys: list[str] = []
    for name in lists:
        keys += [k for k in GEAR[name][:4] if k not in keys]
    tail = [k for name in lists for k in GEAR[name][4:] if k not in keys]
    if seed and tail:
        r = zlib.crc32(seed.encode()) % len(tail)
        tail = tail[r:] + tail[:r]
    for k in tail:
        if k not in keys:
            keys.append(k)
    return keys[:limit]


def box_html(tag: str, keys: list[str], heading: str = "Gear for this aircraft", css: bool = True) -> str:
    """The affiliate box. Empty string when there is no tag — callers can always
    call this unconditionally."""
    if not tag or not keys:
        return ""
    e = html.escape
    lis = "".join(
        f'<li><a href="{e(search_url(ITEMS[k][2], tag))}" target="_blank" '
        f'rel="sponsored noopener nofollow">{e(ITEMS[k][0])}</a><span>{e(ITEMS[k][1])}</span></li>'
        for k in keys if k in ITEMS
    )
    style = f"<style>{CSS}</style>" if css else ""
    return (f'{style}<aside class="aff-box noprint" aria-label="Gear suggestions (affiliate links)">'
            f'<p class="aff-lbl">Gear suggestions (affiliate links)</p><h2>{e(heading)}</h2>'
            f'<ul>{lis}</ul><p class="aff-disc">{DISCLOSURE} Links go to Amazon search results; '
            "check fit and approval for your aircraft before you buy.</p></aside>")


def aircraft_box(tag: str, aircraft: dict | None, seed: str = "", heading: str = "Gear for this aircraft") -> str:
    if not tag:
        return ""
    return box_html(tag, pick(gear_lists_for(aircraft), seed), heading)


TOPIC_HEADINGS = {
    "test-prep": ("test_prep", "Study books and test-prep gear"),
    "general": ("universal", "Gear every pilot uses"),
    "ultralight": ("ultralight", "Ultralight and powered-parachute gear"),
    "builder": ("builder", "Builder's tools"),
}

_SLOT_RE = re.compile(r'<div class="aff-slot" data-topic="([a-z0-9-]+)"></div>')


def fill_slots(page: str, tag: str) -> str:
    """Replace <div class="aff-slot" data-topic="..."></div> placeholders (written
    by other page generators) with a box. Unknown topics are left empty."""
    if not tag or "aff-slot" not in page:
        return page

    def sub(m: re.Match) -> str:
        topic = TOPIC_HEADINGS.get(m.group(1))
        if not topic:
            return m.group(0)
        return box_html(tag, GEAR[topic[0]][:8], topic[1])

    return _SLOT_RE.sub(sub, page)
