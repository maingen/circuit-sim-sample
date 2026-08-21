* Complete transmitter signal path with testbench LO sources
.title WiMAX transmitter end-to-end core verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=3e-3
.temp 27

VDD1 vdd1 0 1.8
VDD5 vdd5 0 6.5
VBBP bbp 0 sin(0.75 20m 10meg)
VBBM bbm 0 sin(0.75 20m 10meg 0 0 180)
VLO1P lo1p 0 sin(0.95 0.40 465meg)
VLO1M lo1m 0 sin(0.95 0.40 465meg 0 0 180)
VLO2P lo2p 0 sin(0.95 0.40 3.040gig)
VLO2M lo2m 0 sin(0.95 0.40 3.040gig 0 0 180)
XTX bbp bbm lo1p lo1m lo2p lo2m rfout pa_probe vdd1 vdd5 0 wimax_tx_core
RLOAD rfout 0 50

.tran 2p 250n 50n 2p uic

.control
set filetype=ascii
tran 2p 250n 50n 2p uic
let pload=v(rfout)*v(rfout)/50
meas tran pout_w avg pload from=150n to=250n
meas tran vout_rms rms v(rfout) from=150n to=250n
meas tran vout_pp pp v(rfout) from=150n to=250n
meas tran pa_drain_min min v(pa_probe) from=150n to=250n
meas tran pa_drain_max max v(pa_probe) from=150n to=250n
wrdata raw/wimax_tx_core_tran.dat time v(bbp) v(rfout)
quit
.endc

.end
