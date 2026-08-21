# Candidate submission

Implement every file under `dut/` as a flattened, circuit-only SPICE fragment. Do not add `.subckt`, `.include`, `.lib`, sources, analyses, model cards, or `.end`. Private fixtures load the pinned SKY130 wrapper and attach only true external sources and loads.

Keep `manifest.json` and every required named node. Save local simulation decks and logs under `work/`.
