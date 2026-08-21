# syntax=docker/dockerfile:1.7
FROM eesimbench/sample4-sky130-ngspice46:local
RUN useradd --uid 10001 --create-home --shell /bin/bash agent \
    && mkdir -p /app/blocks /app/scratch \
    && chown -R agent:agent /app
COPY environment/candidate.cir /app/candidate.cir
COPY environment/blocks /app/blocks
RUN chown -R agent:agent /app && chmod -R u+rwX,go-rwx /app
ENV HOME=/home/agent
USER agent
WORKDIR /app
