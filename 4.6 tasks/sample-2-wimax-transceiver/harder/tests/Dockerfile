# syntax=docker/dockerfile:1.7
FROM 493565080580.dkr.ecr.us-east-1.amazonaws.com/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests /logs/verifier /opt/sky130 \
    && chown -R verifier:verifier /logs
COPY environment/sky130 /opt/sky130
COPY tests /tests
RUN chmod -R a-w /opt/sky130 /tests \
    && chmod 0555 /tests/test.sh /tests/grade.py \
    && PYTHONPATH=/tests/grading python3 -c "import evaluator_core; import run_private_fixtures" \
    && PYTHONPATH=/tests/grading python3 /tests/test_reward_scale.py
ENV HOME=/home/verifier
USER verifier
WORKDIR /app
