* Receiver LNA operating-point, AC, and noise verification
.title RX LNA verification at 3.415 GHz
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.temp 27

VDD vdd 0 1.8
VBG vbiasg 0 0.80
VBC vbiasc 0 1.20
VIN src 0 dc 0 ac 1
RS src rfin 50
XLNA rfin rfout vdd 0 vbiasg vbiasc rx_lna
RLOAD rfout 0 50

.op
.ac dec 200 500meg 8gig
.noise v(rfout) VIN dec 100 2gig 5gig

.control
set filetype=ascii
op
ac dec 200 500meg 8gig
wrdata raw/rx_lna_ac.dat frequency vdb(rfout) vp(rfout) vdb(rfin)
noise v(rfout) VIN dec 100 2gig 5gig
setplot noise1
wrdata raw/rx_lna_noise.dat frequency onoise_spectrum inoise_spectrum
quit
.endc

.end
