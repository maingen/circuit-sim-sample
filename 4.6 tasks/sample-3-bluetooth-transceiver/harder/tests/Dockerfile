# syntax=docker/dockerfile:1.7
FROM 493565080580.dkr.ecr.us-east-1.amazonaws.com/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests /logs/verifier /opt/sky130-pdk \
    && chown -R verifier:verifier /logs
COPY tests/ /tests/
COPY environment/sky130-pdk/ /opt/sky130-pdk/
RUN chmod 0555 /tests/grade.py /tests/test.sh \
    && chmod 0444 /tests/evaluator.py /tests/linter.py /tests/score.py /tests/fixtures.py /tests/target_ledger.json /tests/sky130_allowlist.json \
    && chmod -R a-w /opt/sky130-pdk
ENV HOME=/home/verifier
ENV BENCHMARK_DIFFICULTY=harder
ENV STARTER_SHA256=3726701037a680a76ffecc75e1ffa91e6d6c9811be477057530ee8c1b77577ce
ENV TARGET_LEDGER=/tests/target_ledger.json
ENV SKY130_INCLUDE=/opt/sky130-pdk/models/sky130_27v_tt.spice
ENV SKY130_ALLOWLIST=/tests/sky130_allowlist.json
USER verifier
WORKDIR /app
