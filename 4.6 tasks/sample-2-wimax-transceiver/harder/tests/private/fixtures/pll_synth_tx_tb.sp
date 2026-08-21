* Closed-loop transmitter RF synthesizer test
.title 3.040 GHz divide-by-64 PLL verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=5e-3
.temp 27

VDD vdd 0 1.8
VREF refclk 0 pulse(0 1.8 141n 50p 50p 10.476n 21.053n)
VDRESET div_reset 0 pulse(1.8 0 2n 20p 20p 2u 4u)
VPRESET pfd_reset 0 pulse(1.8 0 200n 20p 20p 2u 4u)
XPLL refclk div_reset pfd_reset lop lom vctrl feedback_probe vdd 0 pll_synth_tx
* The output buffer is the nominal in-system load presented by the TX chain.
XLOAD lop lom loadp loadm vdd 0 lo_buffer_rf
RLT vdd vlobias 8.2k
RLB vlobias 0 9.1k
RGT vdd vgain 6.2k
RGB vgain 0 10k
CLOP loadp mixlop 100f
CLOM loadm mixlom 100f
RLOP vlobias mixlop 20k
RLOM vlobias mixlom 20k
VINP mixinp 0 sin(1.1 0.1 475meg)
VINM mixinm 0 sin(1.1 0.1 475meg 0 0 180)
XMIX mixinp mixinm mixlop mixlom mixoutp mixoutm vgain vdd 0 tx_mixer_475m_to_rf
.ic v(lop)=1.05 v(lom)=0.75 v(vctrl)=0.70 v(vctrl)=0.70

.tran 25p 800n 20n 25p uic

.control
set filetype=ascii
tran 25p 800n 20n 25p uic
let lodiff=v(lop)-v(lom)
meas tran lo_period trig lodiff val=0 rise=2000 targ lodiff val=0 rise=2001
meas tran vctrl_early find v(vctrl) at=100n
meas tran vctrl_late find v(vctrl) at=750n
meas tran q64_period trig v(feedback_probe) val=0.9 rise=32 targ v(feedback_probe) val=0.9 rise=33
meas tran lo_pp pp lodiff from=700n to=800n
wrdata raw/pll_fixture_tran.dat time lodiff v(vctrl) v(feedback_probe)
quit
.endc

.end
