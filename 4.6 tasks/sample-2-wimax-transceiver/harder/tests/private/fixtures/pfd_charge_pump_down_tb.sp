* PFD, charge pump, and loop filter test with feedback leading reference
.title PFD and charge-pump down-direction verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=2e-3
.temp 27

VDD vdd 0 1.8
VREF refclk 0 pulse(0 1.8 5n 50p 50p 10.104n 20.408n)
VFB fbclk 0 pulse(0 1.8 5n 50p 50p 9.9n 20n)
XPFD refclk fbclk 0 up dn vdd 0 pfd
XCP up dn cp vdd 0 charge_pump
XLF cp vctrl 0 pll_loop_filter
RLEAK vctrl 0 1meg

.tran 100p 2u

.control
set filetype=ascii
tran 100p 2u
meas tran up_avg avg v(up) from=1u to=2u
meas tran dn_avg avg v(dn) from=1u to=2u
meas tran vctrl_start find v(vctrl) at=1u
meas tran vctrl_stop find v(vctrl) at=2u
wrdata raw/pfd_charge_pump_down_tran.dat time v(refclk) v(fbclk) v(up) v(dn) v(cp) v(vctrl)
quit
.endc

.end
