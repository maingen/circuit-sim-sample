* Transmit RF synthesizer VCO startup and tuning test
.title 3.040 GHz VCO verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=2e-3
.temp 27

VDD vdd 0 1.8
VCTRL vctrl 0 0.63
VRESET reset 0 pulse(1.8 0 1n 5p 5p 200n 400n)
XVCO outp outm vctrl vdd 0 vco_3040m
XSLC outp outm clk vctrl vdd 0 lo_slicer
XDIV clk reset q2 q4 q8 q16 q32 q64 vdd 0 divider_chain_64
XLOAD outp outm loadp loadm vdd 0 lo_buffer_rf
.ic v(outp)=1.05 v(outm)=0.75

.tran 0.5p 40n 10n 0.5p uic

.control
set filetype=ascii
tran 0.5p 40n 10n 0.5p uic
let vdiff=v(outp)-v(outm)
meas tran vco_period trig vdiff val=0 rise=50 targ vdiff val=0 rise=51
meas tran vco_pp pp vdiff from=30n to=40n
wrdata raw/vco_3040m_tran.dat time vdiff v(outp) v(outm)
quit
.endc

.end
