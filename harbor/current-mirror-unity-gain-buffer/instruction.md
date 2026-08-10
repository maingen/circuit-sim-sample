# Design a current-mirror unity-gain buffer

A 1.8 V CMOS data-converter front end requires a unity-gain buffer with:

\[
\mathrm{SR}_{+} \ge 98.9480113766\ \mathrm{V/\mu s}, \qquad
\mathrm{SR}_{-} \ge 101.902777538\ \mathrm{V/\mu s}, \qquad
f_u \ge 172.166876271\ \mathrm{MHz}.
\]

Design one transistor-level current-mirror amplifier and save it as
`/app/candidate.cir`. The private grader connects your circuit as a unity-gain
buffer and evaluates it with Ngspice 46 and the representative 0.18 um `p18`
BSIM model bundle.

## Design conditions

- The supply voltage is 1.8 V.
- The external output load is 2.5 pF.
- Total quiescent current drawn from the positive supply must not exceed
  399.573 uA.
- Every MOSFET must have a channel length of 0.4 um.
- The required current-mirror ratio is \(K=2\).
- The feedback factor is one.
- Phase margin must be at least 47.7725720755 degrees.
- The input common-mode and output operating voltage is 1.0 V.
- Slew-rate testing steps the input between 0.75 V and 1.25 V.
- Final grading evaluates the `p18` TT, FF, and SS process files at 27 C.

The 2.5 pF load is supplied by the grader. Any compensation capacitor you add
is part of the amplifier and does not replace that load.

## Submitted circuit

Submit exactly one subcircuit, which means one reusable SPICE circuit block,
with these ports in this order:

```spice
.subckt candidate vinp vinn vout vdd vb1 vb2 vss
...
.ends candidate
```

The grader sets `vss` to 0 V, `vdd` to 1.8 V, `vb1` to 1.4 V, and `vb2` to
0.6 V. You may use or ignore the two bias-voltage ports. The `vb1` and `vb2`
ports may connect only to MOSFET gates.

Your subcircuit may contain:

- Four-terminal MOSFETs using model `nmos` or `pmos`.
- Resistors.
- Capacitors.
- One independent DC current source named `IBIAS` whose negative terminal is
  `vss`. Its value is the bias current that you choose.
