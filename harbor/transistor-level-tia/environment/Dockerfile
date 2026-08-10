# syntax=docker/dockerfile:1.7
FROM public.ecr.aws/r9r0c2u2/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10001 --create-home --shell /bin/bash agent \
    && mkdir -p /app/scratch \
    && chown -R agent:agent /app

COPY environment/candidate.cir /app/candidate.cir
RUN chown agent:agent /app/candidate.cir && chmod 0644 /app/candidate.cir

ENV HOME=/home/agent
USER agent
WORKDIR /app
