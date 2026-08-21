* Low-frequency synthesizer VCO startup and tuning test
.title 465 MHz VCO verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=2e-3
.temp 27

VDD vdd 0 1.8
VCTRL vctrl 0 0.614
VRESET reset 0 pulse(1.8 0 1n 20p 20p 400n 800n)
XVCO outp outm vctrl vdd 0 vco_465m
XSLC outp outm clk vctrl vdd 0 lo_slicer
XDIV clk reset q2 q4 q8 q16 q32 q64 vdd 0 divider_chain_64
XLOADT outp outm loadtp loadtm vdd 0 lo_buffer_if
XLOADR outp outm loadrp loadrm vdd 0 lo_buffer_if
.ic v(outp)=1.05 v(outm)=0.75

.tran 5p 200n 40n 5p uic

.control
set filetype=ascii
tran 5p 200n 40n 5p uic
let vdiff=v(outp)-v(outm)
meas tran vco_period trig vdiff val=0 rise=50 targ vdiff val=0 rise=51
meas tran vco_pp pp vdiff from=160n to=200n
wrdata raw/vco_465m_tran.dat time vdiff v(outp) v(outm)
quit
.endc

.end
