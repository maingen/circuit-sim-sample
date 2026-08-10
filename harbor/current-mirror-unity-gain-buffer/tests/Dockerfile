# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04 AS toolchain

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        autoconf automake bison build-essential ca-certificates curl flex git \
        libedit-dev libfftw3-dev libreadline-dev libtool libx11-dev libxaw7-dev unzip \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://git.code.sf.net/p/ngspice/ngspice /tmp/ngspice \
    && git -C /tmp/ngspice checkout ngspice-46 \
    && cd /tmp/ngspice \
    && ./autogen.sh \
    && ./configure --prefix=/usr/local --with-x=no \
    && make -j4 \
    && make install \
    && /usr/local/bin/ngspice --version-small | grep -F 'ngspice-46'

RUN mkdir -p /opt/eesim/models \
    && curl -fsSL https://analogicdesign.com/Files/p18.zip -o /tmp/p18.zip \
    && printf '%s  %s\n' \
       '6696fa66f1edf90d2289370f7b91a629940deb434e78490df58492f33a9d984f' \
       '/tmp/p18.zip' | sha256sum -c - \
    && unzip -q /tmp/p18.zip -d /opt/eesim/models \
    && chmod -R a+rX,go-w /opt/eesim/models

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates coreutils passwd python3 \
        libedit2 libfftw3-double3 libreadline8 libx11-6 libxaw7 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests /logs/verifier \
    && chown -R verifier:verifier /logs

COPY --from=toolchain /usr/local /usr/local
COPY --from=toolchain /opt/eesim/models /opt/eesim/models
COPY tests/evaluator.py tests/grade.py tests/test.sh tests/test_reward_scale.py /tests/
RUN chmod 0555 /tests/grade.py /tests/test.sh \
    && chmod 0444 /tests/evaluator.py /tests/test_reward_scale.py \
    && PYTHONPATH=/tests python3 /tests/test_reward_scale.py

ENV EESIM_MODEL_DIR=/opt/eesim/models HOME=/home/verifier \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
USER verifier
WORKDIR /app
