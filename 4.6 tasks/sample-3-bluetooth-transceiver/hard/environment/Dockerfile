# syntax=docker/dockerfile:1.7
FROM 493565080580.dkr.ecr.us-east-1.amazonaws.com/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10001 --create-home --shell /bin/bash agent \
    && mkdir -p /app/working /opt/sky130-pdk \
    && chown -R agent:agent /app
COPY environment/candidate.cir environment/architecture.json /app/
COPY environment/sky130-pdk/ /opt/sky130-pdk/
RUN chown agent:agent /app/candidate.cir /app/architecture.json \
    && chmod 0644 /app/candidate.cir /app/architecture.json \
    && chmod -R a-w /opt/sky130-pdk
ENV HOME=/home/agent
USER agent
WORKDIR /app
