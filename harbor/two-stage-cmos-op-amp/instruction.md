# Build a two-stage CMOS op amp

Build one two-stage CMOS op amp using a differentially driven, actively loaded
first stage followed by a common-source second stage with an active load. Use a
200 uA reference current and size the bias branches for 100 uA and 200 uA
operation.

Target output voltages of minus 0.8840 V, minus 0.5246 V, and minus 0.1803 V
at common-mode inputs of minus 1 V, 0 V, and 1 V, respectively. Target a
differential gain magnitude of 3079 V/V at 1 kHz and an upper 3 dB frequency of
6.252 MHz. Under the transient overload test, target 1.775 V peak-to-peak output
swing with no more than 35.30 percent total harmonic distortion.

Continue from the circuit supplied in `/app/candidate.cir`, and leave the
completed design in that file. The private grader connects the circuit to its
test fixture and evaluates it with Ngspice 46 and the
supplied 0.18 um `NMOS4` and `PMOS4` models.

## Design conditions

- The supply voltages are 1 V at `vdd` and minus 1 V at `vss`.
- Common-mode testing ties both inputs together and sweeps them from minus 1 V
  through 1 V.
- AC testing biases both inputs at 0 V, applies AC 1 V to `inp`, and applies
  AC minus 1 V to `inn`. The differential AC input is therefore 2 V.
- The AC sweep runs from 1 Hz through 100 MHz. The upper 3 dB frequency is the
  first descending crossing above 1 kHz at the 1 kHz gain divided by the square
  root of two.
- Transient testing drives `inp` with a 1 mV-peak, 1 kHz sine wave and `inn`
  with its opposite. The differential input is 4 mV peak-to-peak.
- The transient run lasts 20 ms and uses the final 5 ms. Total harmonic
  distortion includes harmonics through the fifth after removing the output
  mean.

The exact model cards are available at `/app/cmos018.lib` for your own
simulations.

## Submitted circuit

Submit exactly one subcircuit with these ports in this order:

```spice
.subckt candidate inp inn out vdd vss
...
.ends candidate
```

Your subcircuit may contain four-terminal MOSFETs using only model `NMOS4` or
`PMOS4`, positive-valued resistors, capacitors, and inductors, and exactly one
independent 200 uA DC current source named `IREF` from `vdd` to an internal bias
node. Use literal numeric values and put each instance on one line. Do not
include input stimuli, voltage sources, output loads, model declarations,
analysis directives, nested subcircuits, dependent or behavioral sources,
switches, or transmission-line elements. The grader supplies the models and
test fixture.
