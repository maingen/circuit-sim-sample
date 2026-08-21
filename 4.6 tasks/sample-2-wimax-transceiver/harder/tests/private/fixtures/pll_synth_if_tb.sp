* Closed-loop 465 MHz IF synthesizer test
.title 465 MHz divide-by-32 PLL verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=5e-3
.temp 27

VDD vdd 0 1.8
VREF refclk 0 pulse(0 1.8 141n 50p 50p 34.359n 68.817n)
VDRESET div_reset 0 pulse(1.8 0 2n 50p 50p 3u 6u)
VPRESET pfd_reset 0 pulse(1.8 0 250n 50p 50p 3u 6u)
XPLL refclk div_reset pfd_reset lop lom vctrl feedback_probe vdd 0 pll_synth_if
* The IF oscillator drives one TX and one RX buffer in the complete radio.
XLOADT lop lom loadtp loadtm vdd 0 lo_buffer_if
XLOADR lop lom loadrp loadrm vdd 0 lo_buffer_if
RLT vdd vlobias 8.2k
RLB vlobias 0 9.1k
RGT vdd vgain 6.2k
RGB vgain 0 10k
CLOTP loadtp mixlotp 500f
CLOTM loadtm mixlotm 500f
CLORP loadrp mixlorp 500f
CLORM loadrm mixlorm 500f
RLOTP vlobias mixlotp 20k
RLOTM vlobias mixlotm 20k
RLORP vlobias mixlorp 20k
RLORM vlobias mixlorm 20k
RINTP vgain mixintp 1k
RINTM vgain mixintm 1k
RINRP vgain mixinrp 1k
RINRM vgain mixinrm 1k
XMIXT mixintp mixintm mixlotp mixlotm mixtoutp mixtoutm vgain vdd 0 tx_mixer_10m_to_475m
XMIXR mixinrp mixinrm mixlorp mixlorm mixroutp mixroutm vgain vdd 0 rx_mixer_if1_to_10m
.ic v(lop)=1.05 v(lom)=0.75 v(vctrl)=0.70 v(vctrl)=0.70

.tran 25p 800n 20n 25p uic

.control
set filetype=ascii
tran 25p 800n 20n 25p uic
let lodiff=v(lop)-v(lom)
meas tran lo_period trig lodiff val=0 rise=300 targ lodiff val=0 rise=301
meas tran vctrl_late find v(vctrl) at=750n
meas tran q32_period trig v(feedback_probe) val=0.9 rise=9 targ v(feedback_probe) val=0.9 rise=10
meas tran lo_pp pp lodiff from=700n to=800n
wrdata raw/pll_fixture_tran.dat time lodiff v(vctrl) v(feedback_probe)
quit
.endc

.end
