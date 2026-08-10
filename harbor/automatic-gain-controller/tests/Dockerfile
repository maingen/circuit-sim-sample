# syntax=docker/dockerfile:1.7
FROM public.ecr.aws/r9r0c2u2/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests/grader /tests/models /logs/verifier \
    && chown -R verifier:verifier /logs

COPY environment/system.lib /tests/models/system.lib
COPY tests/grader /tests/grader
COPY tests/grade.py tests/test.sh tests/test_evaluator.py /tests/
RUN chmod 0444 /tests/models/system.lib /tests/grader/*.py /tests/test_evaluator.py \
    && chmod 0555 /tests/grade.py /tests/test.sh \
    && PYTHONPATH=/tests python3 /tests/test_evaluator.py

ENV HOME=/home/verifier
USER verifier
WORKDIR /app
