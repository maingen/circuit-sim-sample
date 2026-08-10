# syntax=docker/dockerfile:1.7
FROM public.ecr.aws/r9r0c2u2/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /bin/bash agent \
    && mkdir -p /app/scratch \
    && chown -R agent:agent /app

USER agent
RUN curl -fsSL https://x.ai/cli/install.sh | bash -s 0.2.118 \
    && /home/agent/.grok/bin/grok --version

USER root
COPY environment/candidate.cir environment/system.lib /app/
RUN chown agent:agent /app/candidate.cir \
    && chmod 0644 /app/candidate.cir \
    && chown root:root /app/system.lib \
    && chmod 0444 /app/system.lib

ENV HOME=/home/agent
USER agent
WORKDIR /app
