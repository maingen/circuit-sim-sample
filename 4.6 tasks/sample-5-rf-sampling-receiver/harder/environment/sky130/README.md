# sky130 ngspice models

ngspice‑ready SPICE device models for the **SkyWater SKY130** open‑source 130 nm
PDK (the `sky130A` variant), extracted from an official **open_pdks** build. These
load directly in ngspice with a standard `.lib … tt` call — no editing, no shim,
no Spectre tooling required.

This is a redistribution of the foundry models for convenient reuse. All model
content is unmodified from the open_pdks build below.

## Provenance

| | |
|---|---|
| Source PDK | SkyWater SKY130 (`sky130A`) |
| Built by | [open_pdks](https://github.com/RTimothyEdwards/open_pdks) (the official open-source PDK builder) |
| Distributed via | [ciel](https://github.com/fossi-foundation/ciel) (successor to `volare`) — the FOSSi Foundation PDK package manager |
| open_pdks build hash | `b344c97eacc2aaf8e14ae7e43e2e9dc0871de2c0` |
| Extracted | from `sky130A/libs.tech/ngspice/` + `sky130A/libs.ref/sky130_fd_pr/spice/` |
| License | Apache License 2.0 — © SkyWater PDK Authors (see `LICENSE`) |

These are the same files open_pdks installs; nothing here was hand‑edited. The raw
upstream device models (`github.com/google/skywater-pdk-libs-sky130_fd_pr`) are a
Spectre export that ngspice cannot read on its own — open_pdks is the step that
makes them ngspice‑ready, which is what this repo captures.

## How it was obtained (reproducible)

```bash
pip install ciel truststore        # truststore: verify TLS via the OS cert store
python -m ciel fetch --pdk sky130 b344c97eacc2aaf8e14ae7e43e2e9dc0871de2c0
# models land in  ~/.ciel/.../sky130A/{libs.tech/ngspice, libs.ref/sky130_fd_pr/spice}
```

`truststore` is needed only on machines whose HTTPS traffic is intercepted by a
local security product (e.g. Norton/corporate proxy); it makes Python verify
certificates against the system trust store instead of its bundled CA list.

## Layout

```
libs.tech/ngspice/                 ngspice corner libraries + glue
  sky130.lib.spice                 << include THIS; sections: tt, ss, ff, sf, fs, …
  corners/  parameters/  r+c/  …
libs.ref/sky130_fd_pr/spice/       the actual binned BSIM device models (675 files)
```

The `sky130.lib.spice` corner files reference the device models by relative path
(`../../../libs.ref/sky130_fd_pr/spice/…`), so keep the two trees in this layout.

## Usage

```spice
* pick a corner section: tt (typical), ss, ff, sf, fs, …
.lib "libs.tech/ngspice/sky130.lib.spice" tt

* instantiate devices as subcircuits (X cards); dimensions in MICRONS:
Xn d g s b sky130_fd_pr__nfet_01v8 l=0.15 w=1   m=1
Xp d g s b sky130_fd_pr__pfet_01v8 l=0.15 w=1   m=1
```

Available FET cells include `sky130_fd_pr__nfet_01v8`, `__pfet_01v8`,
`__nfet_01v8_lvt`, `__pfet_01v8_hvt`, the 5 V/10 V/16 V/20 V devices, ESD FETs,
plus diodes, BJTs, resistors, capacitors, and the `cap_var_lvt` varactor.

## Verified

Loads and simulates in **ngspice‑45** (the build shipped with Qucs‑S):
`sky130_fd_pr__nfet_01v8` at l=0.15 µm, w=1 µm draws ≈69 µA at Vgs=Vds=1.0 V;
`sky130_fd_pr__pfet_01v8` ≈63 µA — both via the `tt` section with no edits.
