# Build a two-stage CMOS op amp with an open feedback network

Build one two-stage CMOS op amp with an NMOS differential input pair, a PMOS
current-mirror active load, and a second stage with an active current-source
load. Connect a 92 kOhm resistor from the output to a feedback node and an
8 kOhm resistor from that node to ground, which gives a feedback factor of
0.08. Leave the feedback node disconnected from the amplifier input.

Target a loaded gain magnitude of 45.56 V/V at 10 MHz and an upper 3 dB
frequency of at least 82.72 MHz. Under the transient test, target a gain
magnitude of 47.51 V/V with no more than 0.004032 percent total harmonic
distortion. The loaded 10 MHz gain must be between 97 and 100 percent of the
unloaded reference gain.

Save the completed circuit as `/app/candidate.cir`. The private grader connects
the circuit to its test fixture and evaluates it with Ngspice 46 and the
supplied 0.18 um `NMOS4` and `PMOS4` models.

## Design conditions

- The supplies are 1 V at `vdd` and minus 1 V at `vss`.
- The non-inverting input is grounded. The grader drives `in` with a DC voltage
  of 0 V and an AC magnitude of 1 V.
- The open 92 kOhm and 8 kOhm network is the only output load.
- The AC sweep runs from 1 MHz through 5 GHz. Gain is measured at 10 MHz. The
  upper 3 dB frequency is the first descending crossing above 10 MHz at the
  low-frequency gain divided by the square root of two.
- The transient test drives `in` with a 1 mV-peak, 1 kHz sine wave for 20 ms
  and measures the final 5 ms.
- Transient total harmonic distortion includes harmonics through the fifth
  after removing the output mean.

The exact model cards are available at `/app/cmos018-s112b.lib` for your own
simulations.

## Submitted circuit

Submit exactly one subcircuit with these ports in this order:

```spice
.subckt candidate in out vdd vss
...
.ends candidate
```

Your subcircuit may contain four-terminal MOSFETs using only model `NMOS4` or
`PMOS4`, positive-valued resistors, capacitors, and inductors, and exactly one
independent 200 uA DC current source named `IREF` from `vdd` to an internal
bias node. Use literal numeric values and put each instance on one line. Do
not include input stimuli, voltage sources, other output loads, model
declarations, analysis directives, nested subcircuits, dependent or behavioral
sources, switches, transmission-line elements, or external files. The grader
supplies the models and test fixture.
