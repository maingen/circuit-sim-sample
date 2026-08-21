* Transmit PA single-tone power, efficiency, and device-stress test
.title SKY130 3.515 GHz transmit power amplifier
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=2e-3
.temp 27

VDDDRV vdddrv 0 1.8
VDDPA vddpa 0 6.5
VBIASDRV vbiasdrv 0 0.80
VBIASPA vbiaspa 0 2.04
VIN src 0 sin(0 0.78 3.515g)
RS src rfin 1
XPA rfin rfout vdddrv vddpa 0 vbiasdrv vbiaspa pa_probe predriver_probe tx_pa
RLOAD rfout 0 50

.tran 2p 100n 20n 2p uic

.control
set filetype=ascii
tran 2p 100n 20n 2p uic
let pload=v(rfout)*v(rfout)/50
let pdc=-v(vddpa)*i(vddpa)-v(vdddrv)*i(vdddrv)
meas tran pout_w avg pload from=80n to=100n
meas tran pdc_w avg pdc from=80n to=100n
meas tran vout_pp pp v(rfout) from=80n to=100n
meas tran drain_min min v(pa_probe) from=80n to=100n
meas tran drain_max max v(pa_probe) from=80n to=100n
meas tran driver_drain_min min v(predriver_probe) from=80n to=100n
meas tran driver_drain_max max v(predriver_probe) from=80n to=100n
wrdata raw/tx_pa_tran.dat time v(src) v(rfin) v(rfin) v(pa_probe) v(rfout) i(vddpa) i(vdddrv)
quit
.endc

.end
