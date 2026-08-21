# Pinned public SKY130 model bundle

This directory contains only the public model files needed by the benchmark's two allowed one-transistor wrappers:

- `sky130_fd_pr__nfet_01v8`
- `sky130_fd_pr__pfet_01v8`

The files come from SKY130A version `c6d73a35f524070e85faff4a6a9eef49553ebc2b`. The benchmark uses the TT corner, 27 C, a 1.8 V supply, and model seed 1. The upstream files retain their Apache-2.0 license headers. `sky130_tt.inc` changes only the include paths so the frozen bundle is relocatable.
