* Four-stage RF driver gain test
.title SKY130 3.515 GHz transmit driver
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=2e-3
.temp 27

VDD vdd 0 1.8
VBIAS vbias 0 0.80
VIN rfin 0 sin(0 3m 3.515g)
XDRV rfin rfout vdd 0 vbias tx_driver
RLOAD rfout 0 100k
CLOAD rfout 0 200f

.tran 2p 100n 20n 2p uic

.control
set filetype=ascii
tran 2p 100n 20n 2p uic
let idd=-i(vdd)
meas tran vin_pp pp v(rfin) from=80n to=100n
meas tran vout_pp pp v(rfout) from=80n to=100n
meas tran idd_avg avg idd from=80n to=100n
wrdata raw/tx_driver_tran.dat time v(rfin) v(rfout) i(vdd)
quit
.endc

.end
