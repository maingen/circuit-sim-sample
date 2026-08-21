* SKY130 model loading and NMOS operating-point smoke test
.title SKY130 NMOS smoke test
.include "/opt/sky130/sky130_tt_1v8.spice"
.temp 27
.option scale=1e-6

VDD d 0 1.8
VG g 0 0.9
VS s 0 0
XMN d g s 0 sky130_fd_pr__nfet_01v8 l=0.15 w=1.26 mult=1

.op

.control
set filetype=ascii
op
let id=-i(VDD)
print v(d) v(g) id
wrdata raw/sky130_smoke_op.dat v(d) v(g) id
quit
.endc

.end
