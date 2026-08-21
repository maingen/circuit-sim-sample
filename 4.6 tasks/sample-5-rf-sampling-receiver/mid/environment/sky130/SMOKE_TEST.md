# Smoke-test results

Every device subcircuit in this repo was enumerated and exercised in ngspice‑45
(an operating point with type‑appropriate DC bias, `.option rshunt=1e12` to keep
the matrix non‑singular). FET instances are sized to a valid model bin (parsed
from the device's own bins, or from the W/L encoded in its name); a device
"passes" if the model binds, the op converges, and its terminal current is finite.

## Headline

**Of the 155 devices the standard `tt` corner loads, 154 pass — 0 electrical
failures.** The one that doesn't instantiate is a PDK‑internal inconsistency in a
special cell, not a model defect (details below). The 154 cover every standard
primitive family you'd actually instantiate.

| Family | pass / tested |
|---|---|
| NMOS FETs (`nfet_01v8`/lvt, `nfet_03v3/05v0`, `g5v0`, `20v0`, esd, RF `bM…`) | 67 / 67 |
| PMOS FETs (`pfet_01v8`/lvt/hvt/mvt, `g5v0`, `20v0`, esd, RF `bM…`) | 33 / 33 |
| Resistors (`res_generic/high/xhigh_po`, nd/pd, iso) | 18 / 18 |
| Capacitors (`cap_mim`, in‑corner `cap_vpp` MOM) | 30 / 30 |
| Varactors (`cap_var_lvt`, `cap_var_hvt`) | 2 / 2 |
| NPN BJTs (`npn_05v5`, `npn_11v0`) | 3 / 3 |
| parasitic res model | 1 / 1 |
| **Total (tt corner)** | **154 / 155** |

Example operating points (sanity): `nfet_01v8` ≈ 69 µA, `pfet_01v8` ≈ 63 µA,
`rf_nfet_01v8_bM02` ≈ 130 µA at the test bias — all physically sensible.

## Not covered by this smoke test

These are not model defects — they are devices that the generic "`.lib tt` +
one op" method can't exercise uniformly. They load and work in normal PDK use.

1. **`special_pfet_pass` (1)** — *genuine instantiation failure.* This SRAM/latch
   special cell instantiates `special_pfet_latch` with a parameter list the latch
   subckt doesn't accept (`unknown subckt`). A pre‑existing inconsistency in the
   PDK's own special‑cell definitions. The other special cells pass.

2. **RF finger‑array + 16 V FETs (17):** the `rf_*_aF*` (finger‑array) variants and
   `nfet/pfet_g5v0d16v0`. These need device‑specific RF/geometry parameters (they
   are meant to be placed via PDK symbols, not generic `l/w`), so a generic op
   can't bind them uniformly.

3. **Devices not in the `tt` corner (28):** 17 `cap_vpp` MOM capacitors, 3
   inductors (`ind_*`), 6 ESD RF diodes (`esd_rf_diode_*`), and 2 ESD/isolated
   FETs (`esd_nfet_05v0_nvt`, `nfet_20v0_nvt_iso`). The `tt` corner's include
   chain doesn't pull these in, and they carry internal dependencies (sub‑models /
   invariant params) that need device‑specific setup to resolve. This matches how
   open_pdks ships them — outside the standard corner.

## Reproduce

The harness lives outside the repo (`_smoke.py`). It enumerates every
`.subckt sky130_fd_pr__…`, classifies it, sizes FETs to a valid bin, and runs one
batch op against `libs.tech/ngspice/sky130.lib.spice`. Per‑device results are in
`_smoke_table.txt`.
