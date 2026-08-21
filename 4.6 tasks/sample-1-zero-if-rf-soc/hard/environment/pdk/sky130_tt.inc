* Pinned SKY130A TT model header for ngspice.
.option scale=1u
.param sky130_fd_pr__nfet_01v8__dlc_rotweak=0
.param sky130_fd_pr__pfet_01v8__dlc_rotweak=0
.param mc_mm_switch=0
.option seed=1
.include "lod.spice"
.include "nonfet.spice"
.include "sky130_fd_pr__nfet_01v8__tt.corner.spice"
.include "sky130_fd_pr__pfet_01v8__tt.corner.spice"
.include "sky130_fd_pr__nfet_01v8__mismatch.corner.spice"
.include "sky130_fd_pr__pfet_01v8__mismatch.corner.spice"
