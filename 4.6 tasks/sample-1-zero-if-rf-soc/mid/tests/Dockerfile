# syntax=docker/dockerfile:1.7
FROM 493565080580.dkr.ecr.us-east-1.amazonaws.com/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests /logs/verifier /pdk \
    && chown -R verifier:verifier /logs
COPY tests/evaluator.py tests/lint_candidate.py tests/grade.py tests/test_reward_scale.py tests/test.sh /tests/
COPY tests/target-ledger.json tests/architecture-map.json tests/sky130-allowlist.json /tests/
COPY tests/fixtures/ /tests/fixtures/
COPY tests/pdk/ /pdk/
RUN chmod 0555 /tests/grade.py /tests/lint_candidate.py /tests/test.sh \
    && chmod -R a=rX /tests /pdk \
    && PYTHONPATH=/tests python3 /tests/test_reward_scale.py
ENV HOME=/home/verifier
ENV BENCH_FIXTURES=/tests/fixtures
ENV BENCH_LEDGER=/tests/target-ledger.json
ENV BENCH_ARCHITECTURE=/tests/architecture-map.json
ENV BENCH_ALLOWLIST=/tests/sky130-allowlist.json
ENV SKY130_PDK_BUNDLE=/pdk
USER verifier
WORKDIR /app
