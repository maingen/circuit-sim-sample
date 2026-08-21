* Transistor-level divider chain at the transmit VCO frequency
.title CMOS divide-by-64 verification at 3.040 GHz
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=2e-3
.temp 27

VDD vdd 0 1.8
VCLK clk 0 pulse(0 1.8 1n 5p 5p 159.47p 328.95p)
VRESET reset 0 pulse(1.8 0 0.5n 5p 5p 200n 400n)
XDIV clk reset q2 q4 q8 q16 q32 q64 vdd 0 divider_chain_64

.tran 2p 80n

.control
set filetype=ascii
tran 2p 80n
meas tran q2_period trig v(q2) val=0.9 rise=40 targ v(q2) val=0.9 rise=41
meas tran q4_period trig v(q4) val=0.9 rise=20 targ v(q4) val=0.9 rise=21
meas tran q64_period trig v(q64) val=0.9 rise=2 targ v(q64) val=0.9 rise=3
wrdata raw/divider_3040m_tran.dat time v(clk) v(q2) v(q4) v(q8) v(q16) v(q32) v(q64)
quit
.endc

.end

