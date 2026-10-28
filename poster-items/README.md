# Poster items

This folder contains copy-ready content and image assets for the Diesel Tank Level and Theft Monitor poster.

## Files

- [`POSTER-CONTENT.md`](POSTER-CONTENT.md) — proposed poster wording, results table, demonstration steps, and diagram.
- [`DEMO-FLOWCHART.md`](DEMO-FLOWCHART.md) — step-by-step presenter flow with an editable Mermaid version.
- [`assets/demo-flowchart.svg`](assets/demo-flowchart.svg) — printable demonstration flowchart graphic.
- [`assets/reference-image.jpg`](assets/reference-image.jpg) — the poster layout/template image supplied by the team.
- [`assets/wokwi-circuit-and-code.png`](assets/wokwi-circuit-and-code.png) — supplied Wokwi editor and circuit screenshot.
- [`assets/dashboard-with-graph.png`](assets/dashboard-with-graph.png) — supplied dashboard screenshot with the level graph.
- [`assets/fuel-level-graph.png`](assets/fuel-level-graph.png) — crop of the graph from the supplied dashboard screenshot.
- [`ASSET-NOTES.md`](ASSET-NOTES.md) — image provenance and guidance about the screenshots.

## Before printing

The supplied dashboard screenshot is useful as a UI/graph illustration, but it shows **STALE** data and mentions legacy readings from the earlier tank-capacity configuration. Do not present it as proof of a current, live cloud test. If evidence of a current run is required, configure the cloud project, wait for the dashboard to show **LIVE**, exercise the distance input, and capture a new screenshot.

Replace the team, institution, and department placeholders in the poster text. Include only credentials-free screenshots; never show `secrets.h`, an Adafruit IO key, or other private tokens.
