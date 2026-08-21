* Second receiver mixer at the inferred 465 MHz LO
.title RX 475 MHz to 10 MHz Gilbert mixer verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=2e-3
.temp 27

VDD vdd 0 1.8
VTAIL tailbias 0 1.10
VINP inp 0 sin(0.75 5m 475meg 0 0 0)
VINM inm 0 sin(0.75 5m 475meg 0 0 180)
VLOP lop 0 sin(0.95 0.40 465meg 0 0 0)
VLOM lom 0 sin(0.95 0.40 465meg 0 0 180)
XMIX inp inm lop lom outp outm tailbias vdd 0 rx_mixer_if1_to_10m
CLOADP outp loadp 10p
CLOADM outm loadm 10p
RLOADP loadp 0 1k
RLOADM loadm 0 1k

.tran 5p 300n 100n 5p

.control
set filetype=ascii
tran 5p 300n 100n 5p
let vdiff=v(loadp)-v(loadm)
let idd=-i(VDD)
meas tran vout_rms rms vdiff from=200n to=300n
meas tran idd_avg avg idd from=200n to=300n
wrdata raw/rx_mixer_if1_to_10m_tran.dat time vdiff v(outp) v(outm)
quit
.endc

.end

