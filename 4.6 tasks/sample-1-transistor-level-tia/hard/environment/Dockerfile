# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04 AS ihp-models

ARG DEBIAN_FRONTEND=noninteractive
ARG IHP_PDK_REVISION=22f2a25f1734796de3debbbf29cf697cbbc54081
ARG OPENVAF_REVISION=3369a83f9c626f6d298f9f881379f561ce432e27
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates clang-18 curl git libclang-18-dev llvm-18-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
ENV CARGO_HOME=/opt/rust/cargo RUSTUP_HOME=/opt/rust/rustup \
    LLVM_SYS_181_PREFIX=/usr/lib/llvm-18 PATH=/opt/rust/cargo/bin:/usr/lib/llvm-18/bin:/usr/local/bin:/usr/bin:/bin
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain 1.90.0 \
    && git clone https://github.com/OpenVAF/OpenVAF-Reloaded.git /tmp/openvaf \
    && git -C /tmp/openvaf checkout "$OPENVAF_REVISION" \
    && cargo build --manifest-path /tmp/openvaf/Cargo.toml --release --features llvm18 --bin openvaf-r \
    && install -m 0555 /tmp/openvaf/target/release/openvaf-r /usr/local/bin/openvaf-r
RUN git clone https://github.com/IHP-GmbH/IHP-Open-PDK.git /opt/ihp-open-pdk \
    && git -C /opt/ihp-open-pdk checkout "$IHP_PDK_REVISION" \
    && cd /opt/ihp-open-pdk/ihp-sg13g2/libs.tech/verilog-a \
    && ./openvaf-compile-va.sh --compile-model-generic \
    && test -s ../ngspice/osdi/psp103.osdi \
    && test -s ../ngspice/osdi/r3_cmc.osdi \
    && rm -rf /opt/ihp-open-pdk/.git

FROM 493565080580.dkr.ecr.us-east-1.amazonaws.com/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96
COPY --from=ihp-models /opt/ihp-open-pdk /opt/ihp-open-pdk
RUN useradd --uid 10001 --create-home --shell /bin/bash agent \
    && mkdir -p /app/scratch \
    && ln -s /opt/ihp-open-pdk/ihp-sg13g2/libs.tech/ngspice/.spiceinit /home/agent/.spiceinit \
    && chown -R agent:agent /app /home/agent
COPY environment/candidate.cir /app/candidate.cir
RUN chown agent:agent /app/candidate.cir && chmod 0644 /app/candidate.cir
ENV EESIM_IHP_PDK_ROOT=/opt/ihp-open-pdk PDK_ROOT=/opt/ihp-open-pdk PDK=ihp-sg13g2 HOME=/home/agent
USER agent
WORKDIR /app
