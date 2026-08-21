* Paper-like 7 MHz two-tone PA linearity test
.title SKY130 transmit PA two-tone IMD verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=3e-3
.temp 27

VDDDRV vdddrv 0 1.8
VDDPA vddpa 0 6.5
VBIASDRV vbiasdrv 0 0.80
VBIASPA vbiaspa 0 2.04
VT1 n1 0 sin(0 1.10 3.5115g)
VT2 src n1 sin(0 1.10 3.5185g)
RS src rfin 1
XPA rfin rfout vdddrv vddpa 0 vbiasdrv vbiaspa pa_probe predriver_probe tx_pa
RLOAD rfout 0 50

.tran 10p 400n 100n 10p uic

.control
set filetype=ascii
tran 10p 400n 100n 10p uic
let pload=v(rfout)*v(rfout)/50
meas tran pout_w avg pload from=200n to=400n
wrdata raw/tx_pa_twotone_tran.dat time v(rfin) v(rfout) i(vddpa) i(vdddrv)
quit
.endc

.end
