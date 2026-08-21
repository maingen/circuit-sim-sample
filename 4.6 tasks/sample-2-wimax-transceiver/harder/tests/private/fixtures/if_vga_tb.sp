* Differential IF VGA operating-point and AC testbench
.title IF VGA verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.temp 27

VDD vdd 0 1.8
VINP inp 0 dc 0.75 ac 0.5
VINM inm 0 dc 0.75 ac 0.5 180
VGAIN gain 0 1.10
XVGA inp inm outp outm gain vdd 0 tx_if_vga
CLP outp 0 50f
CLM outm 0 50f

.op
.ac dec 100 100k 2gig

.control
set filetype=ascii
op
print v(outp) v(outm) i(VDD)
ac dec 100 100k 2gig
let vdiff=v(outp)-v(outm)
wrdata raw/if_vga_ac.dat frequency vdb(vdiff) vp(vdiff)
quit
.endc

.end
