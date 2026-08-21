* VCO load-pulling test with transistor LO buffers and real mixer gates
.title Loaded LO distribution verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"
.option scale=1e-6
.option method=gear reltol=4e-3
.temp 27

VDD vdd 0 1.8
VCTX vctx 0 0.58
VCRX vcrx 0 0.58
VCIF vcif 0 1.00
VTAIL tail 0 1.10
VIP inp 0 0.75
VIM inm 0 0.75
VLOB lobias 0 0.95

XTXV txp txm vctx vdd 0 vco_3040m
XTXB txp txm txbp txbm vdd 0 lo_buffer_rf
CTXBP txbp txlgp 100f
CTXBM txbm txlgm 100f
RTXBP lobias txlgp 20k
RTXBM lobias txlgm 20k
XTXM inp inm txlgp txlgm txop txom tail vdd 0 tx_mixer_475m_to_rf

XRXV rxp rxm vcrx vdd 0 vco_2940m
XRXB rxp rxm rxbp rxbm vdd 0 lo_buffer_rf
CRXBP rxbp rxlgp 100f
CRXBM rxbm rxlgm 100f
RRXBP lobias rxlgp 20k
RRXBM lobias rxlgm 20k
XRXM inp inm rxlgp rxlgm rxop rxom tail vdd 0 rx_mixer_rf_to_if1

XIFV ifp ifm vcif vdd 0 vco_465m
XIFBT ifp ifm ifbtp ifbtm vdd 0 lo_buffer_if
XIFBR ifp ifm ifbrp ifbrm vdd 0 lo_buffer_if
CIFTP ifbtp iftgp 500f
CIFTM ifbtm iftgm 500f
CIFRP ifbrp ifrgp 500f
CIFRM ifbrm ifrgm 500f
RIFTP lobias iftgp 20k
RIFTM lobias iftgm 20k
RIFRP lobias ifrgp 20k
RIFRM lobias ifrgm 20k
XIFMT inp inm iftgp iftgm iftop iftom tail vdd 0 tx_mixer_10m_to_475m
XIFMR inp inm ifrgp ifrgm ifrop ifrom tail vdd 0 rx_mixer_if1_to_10m

.ic v(txp)=1.05 v(txm)=0.75 v(rxp)=1.05 v(rxm)=0.75 v(ifp)=1.05 v(ifm)=0.75
.tran 5p 100n 20n 5p uic

.control
set filetype=ascii
tran 5p 100n 20n 5p uic
let txdiff=v(txp)-v(txm)
let rxdiff=v(rxp)-v(rxm)
let ifdiff=v(ifp)-v(ifm)
let txbufdiff=v(txbp)-v(txbm)
let rxbufdiff=v(rxbp)-v(rxbm)
let ifbufdiff=v(ifbtp)-v(ifbtm)
meas tran tx_period trig txdiff val=0 rise=200 targ txdiff val=0 rise=201
meas tran rx_period trig rxdiff val=0 rise=200 targ rxdiff val=0 rise=201
meas tran if_period trig ifdiff val=0 rise=20 targ ifdiff val=0 rise=21
meas tran txbuf_pp pp txbufdiff from=80n to=100n
meas tran rxbuf_pp pp rxbufdiff from=80n to=100n
meas tran ifbuf_pp pp ifbufdiff from=80n to=100n
wrdata raw/lo_distribution_tran.dat time txdiff rxdiff ifdiff v(txbp) v(txbm) v(rxbp) v(rxbm) v(ifbtp) v(ifbtm)
quit
.endc

.end
