* Standalone AC checks for every paper-mapped passive filter
.title RLC filter bank verification
.include "/opt/sky130/sky130_tt_1v8.spice"
.include "@@WRAPPERS@@"

VIN1 in1 0 dc 0 ac 1
RS1 in1 nsrc1 50
XTXIF1 nsrc1 txif1 0 tx_if_saw1_equiv
RTXIF1 txif1 0 50
VIN2 in2 0 dc 0 ac 1
RS2 in2 nsrc2 50
XTXIF2 nsrc2 txif2 0 tx_if_saw2_equiv
RTXIF2 txif2 0 50
VIN3 in3 0 dc 0 ac 1
RS3 in3 nsrc3 50
XRXIF1 nsrc3 rxif1 0 rx_if1_bpf
RRXIF1 rxif1 0 50
VIN4 in4 0 dc 0 ac 1
RS4 in4 nsrc4 50
XRXIF2 nsrc4 rxif2 0 rx_if2_bpf
RRXIF2 rxif2 0 50
VIN5 in5 0 dc 0 ac 1
RS5 in5 nsrc5 50
XTXRF nsrc5 txrf 0 tx_rf_bpf
RTXRF txrf 0 50
VIN6 in6 0 dc 0 ac 1
RS6 in6 nsrc6 50
XRXRF nsrc6 rxrf 0 rx_rf_bpf
RRXRF rxrf 0 50

.ac dec 100 1meg 10gig

.control
set filetype=ascii
ac dec 100 1meg 10gig
wrdata raw/filters_ac.dat frequency vdb(txif1) vdb(txif2) vdb(rxif1) vdb(rxif2) vdb(txrf) vdb(rxrf)
quit
.endc

.end
