# Aircraft profile

**Status:** draft, revision 1. Required for Junco v1.

Originally specified in the [Junco](https://github.com/allenmcghan/junco)
project. This document is now authoritative;
`junco/spec/aircraft-profile.md` redirects here.

---

## Requirement

Adapting Junco to a different aircraft must never require a toolchain. One
human-readable, hand-editable file describes the aircraft completely. A web
based configuration tool at [openchecklists.net](https://openchecklists.net)
generates and validates it, but is never required to produce one.

---

## Format

**TOML as the source of truth, plus a compiled binary form. The node stores
both.**

- **TOML is authoritative.** Hand-editable, comments survive round trips, no
  significant whitespace to get wrong, unambiguous types. It is what the
  owner edits and what the web configuration tool emits.
- **The binary form is derived.** Compiled from the TOML by the configuration
  tool or by the node's Wi-Fi AP mode, never in flight. Fixed layout, no
  parsing, directly usable.
- **Both live on the node.** The TOML so the aircraft is self-documenting and
  a replacement tool can read it back; the binary so nothing parses text at
  boot.
- **BLE serves the binary form.** A client needs the values, not the comments.

If the two ever disagree, the TOML wins and the binary is rebuilt. A node
that finds a binary whose hash does not match its TOML refuses to arm and
says so.

---

## Schema

### Top level

| Key | Type | Notes |
|---|---|---|
| `schema_version` | integer | The node refuses a version it does not recognise. Migration lives in the configuration tool, not in firmware |

### `[identity]`

| Key | Type | Notes |
|---|---|---|
| `registration` | string | FAA N-number, or `""` if unregistered. Used for logbook entry drafts |
| `make` | string | Manufacturer or builder name |
| `model` | string | Aircraft model |

### `[powerplant]`

| Key | Type | Notes |
|---|---|---|
| `engine_count` | integer | 1 or 2 in v1 |
| `cylinders_per_engine` | integer | Determines CHT and EGT channel count |
| `pulses_per_revolution` | integer | CDI ignition: typically 1 per cylinder |
| `hour_meter_offsets` | float array | One entry per engine. Pre-existing hours before Junco installation |

### `[channels]`

| Key | Type | Options |
|---|---|---|
| `fuel_backend` | string | `"burn_integration"`, `"magnetic_float"`, `"load_cell"`, `"ultrasonic"`, `"capacitive"` |

### `[calibration]`

| Key | Type | Notes |
|---|---|---|
| `pitot_position_error_pa` | float | Airspeed position error correction. Zero until flight-tested |
| `baro_offset_pa` | float | Baro correction against a known altimeter. Zero until measured |
| `thermocouple_offsets_c` | float array | One per sensor in order: CHT L, CHT R, EGT L, EGT R. Zero until calibrated |
| `fuel_curve` | array of `[float, float]` | `[[volume, sensor_reading], ...]` for non-integration backends. Empty for burn integration |

### `[limits]`

Alert thresholds. In the units specified by `[units]`.

| Key | Type | Notes |
|---|---|---|
| `cht_max` | float | CHT over-limit. Triggers audio alert |
| `egt_max` | float | EGT over-limit. Triggers audio alert |
| `rpm_max` | integer | RPM redline |
| `fuel_reserve` | float | Fuel endurance alert below this quantity |
| `density_alt_advisory` | integer | Pre-takeoff density altitude advisory. Always in feet |

### `[fuel]`

| Key | Type | Notes |
|---|---|---|
| `capacity` | float | Total tank capacity, in the volume units from `[units]` |
| `usable` | float | Usable quantity. Must be less than or equal to capacity |
| `burn_rate_table` | array of `[integer, float]` | `[[rpm, volume_per_hour], ...]`. Both engines combined. Used by burn integration and endurance display |

### `[units]`

| Key | Options |
|---|---|
| `altitude` | `"feet"` or `"meters"` |
| `speed` | `"mph"`, `"knots"`, or `"kph"` |
| `temperature` | `"fahrenheit"` or `"celsius"` |
| `volume` | `"gallons"` or `"liters"` |
| `pressure` | `"inHg"` or `"hPa"` |
| `reference` | `"magnetic"` or `"true"` |

### `[logging]`

| Key | Type | Notes |
|---|---|---|
| `rate_hz` | integer | Log rate. Maximum is channel-dependent; see Junco BLE specification |
| `retention_days` | integer | How long the node retains logs before overwriting |
| `enabled` | boolean | Set `false` to disable logging entirely |

### `[build]`

| Key | Options | Notes |
|---|---|---|
| `class` | `"self_built"`, `"kit_built"`, `"factory_qualified"` | Written into every log header per Junco design rule 7 |

---

## Versioning

`schema_version = 1` is the initial version. This field increments on any
breaking change. Additive changes — new optional keys a node can safely ignore
— may be made within a version.

The node refuses a version it does not recognise. It never guesses. A node
that half-understands a profile may be reading a CHT limit from the wrong
field, and there is no safe default for that.

---

## Validation

Validated by the configuration tool on save, and by the node on load, because
the node cannot assume the file arrived from the tool.

Minimum rejections:

- `engine_count`, `cylinders_per_engine`, and the channel map disagreeing
- `usable` greater than `capacity`
- `pulses_per_revolution` of zero
- Two channels claiming the same pin or address
- A limit outside the range its sensor can represent
- A fuel backend named in `[channels]` with no corresponding calibration

A channel that fails validation is not armed. The node reports it rather than
substituting a default.

---

## Profile hash

SHA-256 over the exact bytes stored on the node, truncated to 8 bytes.

**Hash the stored bytes, not a re-serialization.** Hashing a re-serialized
structure means any change to the serializer silently changes the hash of an
unmodified profile, which invalidates every cached copy and every log header
that referenced it.

The same 8 bytes appear in the Junco log header and over BLE, so a log and a
live connection name the same profile identically.

---

## What the profile does not contain

The profile describes the aircraft, and it lives on the node so a borrowed
phone or a replacement tablet inherits the right configuration by connecting.

Anything describing the pilot's own equipment rather than the aircraft is
app-side configuration and stays on the phone. Traffic backend selection is
the current example: which receiver or feed a pilot uses changes without the
aircraft changing, and the node is not in that data path at all.

---

## Still open

- The binary form field layout (shared with Junco BLE telemetry spec)
- What the node does when no valid profile exists on a freshly built unit
