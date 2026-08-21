# syntax=docker/dockerfile:1.7
FROM eesimbench/sample4-sky130-ngspice46:local
RUN useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests /logs/verifier \
    && chown -R verifier:verifier /logs
COPY tests /tests
RUN chmod -R a-w /tests && chmod 0555 /tests/grade.py /tests/test.sh
ENV HOME=/home/verifier
USER verifier
WORKDIR /app
