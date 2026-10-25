# Ground school and the Aha Trivia pilot games

Status: built 2026-10-25. Owner request: "Embed the aha trivia pilot tests in this site using the aha game
engine. We also need full training materials."

## Objective

Give a student a complete, free path to each pilot knowledge test on openchecklists.net:
lessons to learn the material, the Aha Trivia game to keep it fresh, and the existing FAA
sample-question practice tests to prove readiness.

## What was built

1. **Aha Trivia games, embedded with the engine's own embed mode.** `tools/aha_embed.py` emits the
   same iframe ahatrivia.com/embed/ hands out (`/play/?course=<id>&embed=1`). Courses: Private Pilot
   (`pilot`), Sport Pilot (`sport-pilot`), Part 107 (`drone`), Instrument (`instrument`), Commercial
   (`commercial`), Aerospace Explorer (`aerospace`). Three forms:
   - a lazy iframe for one course (course pages, practice tests);
   - a tab picker over one iframe (ground school hub, test prep hub), so a page loads one game;
   - a Start button that loads the game only when asked (lesson pages, which stay light).
2. **Ground school** at `/ground-school/`: six courses (Part 103, Part 107, Sport, Private,
   Instrument, Commercial) from `ground-school/<id>.json`. Each course has an overview (facts table,
   tests, requirements, study plan, lessons, game, test-day checklist, what comes next), one page per
   lesson (objectives, teaching, numbers, traps, official readings, self-check, mark complete) and a
   printable whole-course page.
3. **Links in**: a Ground school item in every navigation bar and footer, a banner and per-certificate
   links on the training page, and links plus games on the test prep pages.

## Decisions

- **Iframe, not a copy of the engine.** The embed mode is the engine's supported way onto other
  sites. It keeps scores on the player's device, shares nothing with us, keeps Aha Trivia's paywall
  and content updates in one place, and needs no build coupling between the two repositories.
- **Content as JSON with a validator.** Same pattern as `quiz/`: tracked source, a generator, and a
  test that fails the build on a wrong answer index, a non-https reference or a dangling plan step.
- **Our words, linked sources.** Lessons are written by us and cite 14 CFR, the AIM, the ACS and FAA
  handbooks; we do not reproduce copyrighted test-prep material.
- **Progress stays in the browser** (`localStorage` `ocl:gs:<course>`), like the practice tests.
  No new API, no new personal data.
- **Print page is `noindex`** so the full-course copy does not compete with the lesson pages.
- **Privacy**: the policy names the Aha Trivia embed and links its own policy.

## Checks

- `python3 tools/test_ground_school.py`: content rules, validator rejections, page output, embeds.
- `python3 tests/e2e/ground_school_e2e.py BASE`: real browser, desktop and phone.
- Course facts and links were checked against the current eCFR and FAA source pages before publishing.
