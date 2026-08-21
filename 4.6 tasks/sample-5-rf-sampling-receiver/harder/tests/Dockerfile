# syntax=docker/dockerfile:1.7
FROM 493565080580.dkr.ecr.us-east-1.amazonaws.com/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests/fixtures /logs/verifier /opt/sky130 \
    && chown -R verifier:verifier /logs
COPY tests/sky130/ /opt/sky130/
COPY tests/evaluator.py tests/lint_candidate.py tests/scoring.py tests/grade.py tests/test.sh /tests/
COPY tests/fixtures/ /tests/fixtures/
COPY tests/target_ledger.json tests/reference_measurements.json /tests/
RUN chmod 0555 /tests/grade.py /tests/test.sh \
    && chmod 0444 /tests/evaluator.py /tests/lint_candidate.py /tests/scoring.py /tests/target_ledger.json /tests/reference_measurements.json
ENV HOME=/home/verifier
ENV SKY130_LIB=/opt/sky130/libs.tech/ngspice/sky130.lib.spice
ENV NGSPICE_BIN=/usr/bin/ngspice
USER verifier
WORKDIR /app
