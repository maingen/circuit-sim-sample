* Bias, gain DAC, power detector, and control logic testbench
.title Bias and control block verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.temp 27

VDD vdd 0 1.8
XBIAS vdd 0 vbiasn vbiasp bias_reference

VB0 b0 0 pulse(0 1.8 1u 1n 1n 1u 2u)
VB1 b1 0 pulse(0 1.8 2u 1n 1n 2u 4u)
VB2 b2 0 pulse(0 1.8 4u 1n 1n 4u 8u)
XDAC b0 b1 b2 vdac vdd 0 gain_dac

VEN enable 0 pulse(0 1.8 1u 1n 1n 6u 8u)
VLIM limit 0 pulse(0 1.8 4u 1n 1n 2u 8u)
XCTL enable limit drive vdd 0 control_logic

VRF rfin 0 sin(0.65 0.25 100meg)
XDET rfin env vdd 0 power_detector

.op
.tran 2n 12u

.control
set filetype=ascii
op
print v(vbiasn) v(vbiasp) v(vdac) v(env)
tran 2n 12u
meas tran vdac_code0 find v(vdac) at=0.5u
meas tran vdac_code1 find v(vdac) at=1.5u
meas tran vdac_code3 find v(vdac) at=3.5u
meas tran vdac_code7 find v(vdac) at=7.5u
meas tran drive_enabled find v(drive) at=2.5u
meas tran drive_limited find v(drive) at=5.0u
meas tran env_avg avg v(env) from=10u to=12u
wrdata raw/bias_control_tran.dat time v(vbiasn) v(vbiasp) v(vdac) v(drive) v(env)
quit
.endc

.end

