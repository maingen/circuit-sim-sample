* Complete transceiver with all three transistor-level PLLs and both signal paths
.title Complete SKY130 WiMAX transceiver end-to-end verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=5e-3
.temp 27

VDD1 vdd1 0 1.8
VDD5 vdd5 0 6.5
VBBP bbp 0 sin(0.75 20m 10meg)
VBBM bbm 0 sin(0.75 20m 10meg 0 0 180)
VREFT reft 0 pulse(0 1.8 141n 50p 50p 10.476n 21.053n)
VREFR refr 0 pulse(0 1.8 141n 50p 50p 10.834n 21.769n)
VREFI refi 0 pulse(0 1.8 141n 50p 50p 34.359n 68.817n)
VDRESET div_reset 0 pulse(1.8 0 2n 20p 20p 2u 4u)
VPRESET pfd_reset 0 pulse(1.8 0 200n 20p 20p 2u 4u)
XSYS bbp bbm rxoutp rxoutm antenna reft refr refi div_reset pfd_reset vdd1 vdd5 0 txlop txlom rxlop rxlom iflop iflom txfb rxfb iffb txvc rxvc ifvc pa_probe wimax_transceiver
RANT antenna 0 50
RLOADP rxoutp 0 1k
RLOADM rxoutm 0 1k
.ic v(txlop)=1.05 v(txlom)=0.75 v(rxlop)=1.05 v(rxlom)=0.75
.ic v(iflop)=1.05 v(iflom)=0.75
.ic v(txvc)=0.70 v(rxvc)=0.70 v(ifvc)=0.70

.tran 25p 800n 20n 25p uic

.control
set filetype=ascii
tran 25p 800n 20n 25p uic
let rxdiff=v(rxoutp)-v(rxoutm)
let pant=v(antenna)*v(antenna)/50
let txlodiff=v(txlop)-v(txlom)
let rxlodiff=v(rxlop)-v(rxlom)
let iflodiff=v(iflop)-v(iflom)
meas tran antenna_power avg pant from=600n to=800n
meas tran rxout_rms rms rxdiff from=600n to=800n
meas tran tx_lo_period trig txlodiff val=0 rise=2000 targ txlodiff val=0 rise=2001
meas tran rx_lo_period trig rxlodiff val=0 rise=2000 targ rxlodiff val=0 rise=2001
meas tran if_lo_period trig iflodiff val=0 rise=300 targ iflodiff val=0 rise=301
meas tran tx_q64_period trig v(txfb) val=0.9 rise=25 targ v(txfb) val=0.9 rise=26
meas tran rx_q64_period trig v(rxfb) val=0.9 rise=25 targ v(rxfb) val=0.9 rise=26
meas tran if_q32_period trig v(iffb) val=0.9 rise=5 targ v(iffb) val=0.9 rise=6
meas tran tx_vctrl_600 find v(txvc) at=600n
meas tran tx_vctrl_800 find v(txvc) at=800n
meas tran rx_vctrl_600 find v(rxvc) at=600n
meas tran rx_vctrl_800 find v(rxvc) at=800n
meas tran if_vctrl_600 find v(ifvc) at=600n
meas tran if_vctrl_800 find v(ifvc) at=800n
meas tran pa_drain_min min v(pa_probe) from=600n to=800n
meas tran pa_drain_max max v(pa_probe) from=600n to=800n
wrdata raw/wimax_transceiver_tran.dat time v(bbp) v(antenna) rxdiff txlodiff rxlodiff iflodiff v(txvc) v(rxvc) v(ifvc)
quit
.endc

.end
