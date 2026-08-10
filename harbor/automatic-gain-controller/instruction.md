# Build a transistor-level AGC controller

Build a transistor-level automatic-gain-control controller. Filter the differential detector input with one 600 ohm resistor in each leg and one 150 fF differential capacitor, isolate the filter with NPN emitter followers and transistor-mirror sinks, and design one local CMOS operational-amplifier subcircuit. Instantiate that locally authored amplifier exactly twice: once to generate `pkd`, and once to compare `pkd` with `oa` and generate `agc`.

At detector differences of 20 mV and 50 mV, target `pkd` values of 1.080 V and 1.499 V and `agc` values of 1.399 V and 1.200 V. The first closed-loop stage must have gain 13.97 V/V within 2 percent. The `agc` output must decrease as detector difference increases, remain from 1.2 V through 1.4 V, and enter and remain within 1 percent of its final value within 5 us after either step.

Save the completed circuit as `/app/candidate.cir`. You may use Ngspice 46 and the supplied transistor models at `/app/system.lib` while designing. The private fixture owns supplies, references, stimuli, loads, and analyses.

## Design conditions

- The supply is 3.3 V and `vss` is ground.
- The fixture evaluates `oa` at 1.2 V and 1.4 V and applies detector differences of 0 V, 20 mV, and 50 mV.
- The fixture holds `agc_pkd_ref` at 0.8 V.
- The fixture holds `agc_ref` at 1.2864 V.
- The fixture holds `detn` at 3.15 V and drives `detp` at `detn` plus the applied detector difference.
- The fixture loads `agc` with 1 Mohm in parallel with 10 pF.
- The fixture evaluates operating behavior and a 10 us transient sequence containing both detector steps.
## Submitted circuit

Submit exactly one top-level subcircuit with these ports in this order:

```spice
.subckt candidate detp detn oa pkd agc agc_pkd_ref agc_ref vcc vss
...
.ends candidate
```

Define exactly one additional local amplifier subcircuit in the same file and call it exactly twice with `X` instances. The local amplifier must contain a differential pair, transistor tail source, active transistor load, an additional gain or output stage, and physical compensation. Use only `R`, `C`, `L`, `D`, `Q`, and `M` elements inside the two subcircuits, except for the two required local `X` calls in `candidate`. Use only models `NMOS_SYS`, `PMOS_SYS`, `QN_SYS`, and `QP_SYS`. Do not include independent sources, model declarations, analysis directives, external files, behavioral or dependent sources, switches, transmission lines, or prebuilt circuit blocks.
