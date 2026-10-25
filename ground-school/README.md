# Ground school content

One JSON file per course. `tools/site_ground_school.py` turns each file into pages under
`/ground-school/<id>/`, and `tools/test_ground_school.py` checks every file against the
rules below. The build fails if a file breaks a rule.

The text is our own. Every fact that a student could be tested on carries a reference to
14 CFR (eCFR), the AIM, an Airman Certification Standards document or an FAA handbook.
Those sources are U.S. Government works. We link to them; we do not copy them.

## Courses

| File | Course | Aha Trivia course | Practice test |
| --- | --- | --- | --- |
| `part-103.json` | Ultralight (Part 103) | none | `/quiz/part-103-ultralight/` |
| `part-107.json` | Remote Pilot (Part 107 drone) | `drone` | `/quiz/part-107/` |
| `sport-pilot.json` | Sport Pilot | `sport-pilot` | `/quiz/sport-pilot/` |
| `private-pilot.json` | Private Pilot Airplane | `pilot` | `/quiz/private-pilot/` |
| `instrument-rating.json` | Instrument Rating Airplane | `instrument` | none |
| `commercial-pilot.json` | Commercial Pilot Airplane | `commercial` | none |

## File format

All text fields are plain text. The generator escapes them, so do not put HTML or
Markdown in them.

```jsonc
{
  "id": "private-pilot",              // file name without .json; also the URL slug
  "title": "Private Pilot (Airplane)", // page heading
  "short": "Private Pilot",            // short name for buttons and breadcrumbs
  "icon": "✈️",
  "order": 4,                          // position on the hub page, smallest first
  "summary": "One or two sentences for the hub card and the meta description.",
  "who": "A short paragraph: who this course is for and what the certificate allows.",
  "aha_course": "pilot",               // Aha Trivia course id, or null
  "quiz_slug": "private-pilot",        // existing /quiz/<slug>/ practice test, or null
  "checked": "2026-10-25",             // date the facts were last checked against the sources
  "facts": [                           // 4 to 8 headline facts for the overview table
    {"label": "Minimum age", "value": "17 to hold the certificate",
     "cite": {"label": "14 CFR 61.103(a)", "url": "https://www.ecfr.gov/current/title-14/section-61.103"}}
  ],
  "knowledge_test": {                  // null when there is no knowledge test (Part 103)
    "code": "PAR", "questions": 60, "minutes": 150, "passing": "70%",
    "notes": ["Plain sentences about endorsements, what to bring, retakes and validity."],
    "cites": [{"label": "...", "url": "https://..."}]
  },
  "practical_test": {                  // null when there is no practical test
    "standard": "Private Pilot Airplane ACS (FAA-S-ACS-6)",
    "url": "https://www.faa.gov/...",
    "notes": ["Plain sentences about the oral exam and the flight test."]
  },
  "requirements": [                    // eligibility and experience, one requirement per item
    {"text": "40 hours of flight time, including ...",
     "cite": {"label": "14 CFR 61.109(a)", "url": "https://www.ecfr.gov/current/title-14/section-61.109"}}
  ],
  "plan": [                            // a study schedule; each step names module ids
    {"step": "Week 1", "focus": "What to do this week.", "modules": ["regulations"]}
  ],
  "modules": [                         // 6 to 12 lessons
    {
      "id": "airspace",                // URL slug: lowercase letters, digits and hyphens
      "title": "Airspace",
      "summary": "One sentence about what this lesson covers.",
      "objectives": ["After this lesson you can ..."],        // 3 to 6
      "sections": [                                           // 3 to 8
        {"heading": "Class B", "points": ["A plain paragraph or a single teaching point."]}
      ],
      "numbers": [                                            // numbers worth memorizing; may be empty
        {"item": "Class B VFR visibility", "value": "3 statute miles", "cite": "14 CFR 91.155"}
      ],
      "traps": ["A common test mistake and how to avoid it."], // may be empty
      "read": [                                               // 2 to 6 official sources
        {"label": "PHAK Chapter 15: Airspace", "url": "https://www.faa.gov/...",
         "library": {"doc": "faa-phak", "q": "class b airspace"}}  // optional: search link into /search.html
      ],
      "check": [                                              // 3 to 5 self-check questions
        {"q": "Question text?", "choices": ["A", "B", "C"], "answer": 0,
         "why": "Why the answer is right.", "cite": "14 CFR 91.155"}
      ]
    }
  ],
  "test_day": ["One item per line: what to bring and do on test day."],
  "after": ["One item per line: what comes after you pass."]
}
```

## Library search ids

A `library` link opens our full-text search on that document. Valid `doc` values:
`faa-phak`, `faa-awh`, `faa-ifh`, `faa-rmh`, `faa-wb`, `faa-pfh`, `faa-wscfh`,
`faa-afh-8083-3c-ch2`, `acs-private-airplane`, `acs-instrument-airplane`,
`acs-commercial-airplane`.

## Rules the test enforces

- Every `url` starts with `https://`.
- Every `check` question has 3 or 4 choices and an `answer` index inside them.
- Every module id is unique in its file, and every `plan` step names real module ids.
- Every module has objectives, sections, readings and self-check questions.
