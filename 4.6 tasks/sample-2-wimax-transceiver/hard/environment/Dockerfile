# syntax=docker/dockerfile:1.7
FROM 493565080580.dkr.ecr.us-east-1.amazonaws.com/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10001 --create-home --shell /bin/bash agent \
    && mkdir -p /app/submission/work /opt/sky130 \
    && chown -R agent:agent /app
COPY environment/sky130 /opt/sky130
COPY environment/submission /app/submission
RUN chmod -R a-w /opt/sky130 \
    && chown -R agent:agent /app/submission
ENV HOME=/home/agent
USER agent
WORKDIR /app
