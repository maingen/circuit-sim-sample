* Loaded VCO tuning-direction and range verification
.title 3.040 GHz loaded VCO tuning range
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=3e-3
.temp 27

VDD vdd 0 1.8
VLO vlo 0 0.70
VHI vhi 0 1.30
XVLO loplo lomlo vlo vdd 0 vco_3040m
XSLO loplo lomlo clklo vlo vdd 0 lo_slicer
XVHI lophi lomhi vhi vdd 0 vco_3040m
XSHI lophi lomhi clkhi vhi vdd 0 lo_slicer
.ic v(loplo)=1.05 v(lomlo)=0.75 v(lophi)=1.05 v(lomhi)=0.75

.tran 5p 60n 10n 5p uic

.control
set filetype=ascii
tran 5p 60n 10n 5p uic
let lodiff_lo=v(loplo)-v(lomlo)
let lodiff_hi=v(lophi)-v(lomhi)
meas tran period_vctrl_070 trig v(clklo) val=0.9 rise=100 targ v(clklo) val=0.9 rise=101
meas tran period_vctrl_130 trig v(clkhi) val=0.9 rise=100 targ v(clkhi) val=0.9 rise=101
meas tran pp_vctrl_070 pp lodiff_lo from=50n to=60n
meas tran pp_vctrl_130 pp lodiff_hi from=50n to=60n
wrdata raw/vco_3040m_tuning.dat time v(clklo) v(clkhi) v(loplo) v(lomlo) v(lophi) v(lomhi)
quit
.endc

.end
