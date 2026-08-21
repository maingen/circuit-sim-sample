* Complete receiver signal path with testbench LO sources
.title WiMAX receiver end-to-end core verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=3e-3
.temp 27

VDD1 vdd1 0 1.8
VRF src 0 sin(0 1m 3.415gig)
RS src rfin 50
VLO1P lo1p 0 sin(0.95 0.40 2.940gig)
VLO1M lo1m 0 sin(0.95 0.40 2.940gig 0 0 180)
VLO2P lo2p 0 sin(0.95 0.40 465meg)
VLO2M lo2m 0 sin(0.95 0.40 465meg 0 0 180)
XRX rfin lo1p lo1m lo2p lo2m outp outm vdd1 0 wimax_rx_core
RLOADP outp 0 1k
RLOADM outm 0 1k

.tran 2p 300n 50n 2p uic

.control
set filetype=ascii
tran 2p 300n 50n 2p uic
let vdiff=v(outp)-v(outm)
meas tran vout_rms rms vdiff from=200n to=300n
meas tran vout_pp pp vdiff from=200n to=300n
wrdata raw/wimax_rx_core_tran.dat time v(src) vdiff
quit
.endc

.end
