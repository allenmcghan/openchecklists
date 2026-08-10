# Open Checklists

Open aircraft checklists and configuration profiles for Part 103 and
experimental aircraft, built to work with [Junco](https://github.com/allenmcghan/junco).

## What this is

A library of:

- **Aircraft profiles** — TOML configuration files for the Junco instrument
  node, one per aircraft type. Contains limits, sensor maps, calibration
  baselines, and unit preferences.
- **Pre-flight and emergency checklists** — Markdown checklists for specific
  aircraft, designed to be used alongside a Junco-equipped instrument panel.

The web configuration tool at [openchecklists.net](https://openchecklists.net)
generates and validates aircraft profiles. It is never required — every file
here is hand-editable.

## How Junco uses this

The Junco app can browse and import profiles from this library by aircraft
type, so a builder does not have to write one from scratch. Checklists are
referenced in-app during pre-flight and emergency procedure phases.

## Aircraft

| Aircraft | Profile | Checklists | Status |
|---|---|---|---|
| ParaPlane PM-2 | [profiles/pm2/pm2.toml](profiles/pm2/pm2.toml) | [checklists/pm2/](checklists/pm2/) | Draft |

## Specifications

| Document | Status |
|---|---|
| [spec/aircraft-profile.md](spec/aircraft-profile.md) | Draft — TOML profile format for Junco |

## Relationship to Junco

[Junco](https://github.com/allenmcghan/junco) is the engine and air data
sensor node. This project is the data layer it draws from: profiles tell
Junco how a specific aircraft is wired; checklists give the pilot something
to read before and during flight.

The profile format is defined here and consumed by Junco firmware and the
Android app. Neither project depends on the other to function — Junco accepts
hand-written TOML; checklists are readable without Junco.

## Related projects

| Project | What it does |
|---|---|
| [Junco](https://github.com/allenmcghan/junco) | Open engine and air data node. Reads profiles from this library |
| [Nuthatch](https://github.com/allenmcghan/nuthatch) | Open single-seat ultralight aircraft design |

## License

All content is [CC-BY-4.0](LICENSE). Build from it, adapt it, redistribute it.
If you fix something, a pull request is welcome.

## Contributing

Build reports and correction issues are the most useful contributions. If you
add a new aircraft, copy an existing profile as a template and verify against
your aircraft's documentation.
