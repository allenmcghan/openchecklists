# ParaPlane PM-2 profile

Draft Junco aircraft profile for the ParaPlane PM-2 powered parachute.

## Aircraft

The PM-2 is a twin-engine powered parachute. The Junco v1 target is a
single-seat variant with twin two-stroke engines on a trike cart.

## Status

Draft. Limits are drawn from factory specifications and the Junco v1
development unit. The burn rate table is estimated and should be replaced
with measured flight data once the node is flying.

## Using this profile

Copy `pm2.toml` to your Junco node using the web AP interface (connect to
the node's Wi-Fi, then use the configuration tool at
[openchecklists.net](https://openchecklists.net) or edit the file directly).

After loading:

1. Set `[identity].registration` to your N-number
2. Verify limits against your engine documentation
3. Update `[calibration]` after measuring your sensors against a reference
4. Replace `burn_rate_table` with measured gph at known RPM settings

## Limits reference

These are defaults. Verify against your specific engine documentation.

| Parameter | Value | Notes |
|---|---|---|
| CHT max | 435 °F | Appropriate for air-cooled two-strokes. Reduce if you see heat-related failures |
| EGT max | 1,250 °F | Watch for rapid rise on one cylinder — seizure precursor |
| RPM redline | 6,800 | Verify against your engine's documentation |
| Fuel reserve | 1.5 gal | Alert triggers below this |
| Density altitude | 3,000 ft | Pre-takeoff advisory only |
