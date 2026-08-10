# syntax=docker/dockerfile:1.7
FROM public.ecr.aws/r9r0c2u2/eesimbench/ngspice-46-ubuntu24.04@sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96

RUN useradd --uid 10002 --create-home --shell /bin/bash verifier \
    && mkdir -p /tests /logs/verifier /opt/eesim/models \
    && chown -R verifier:verifier /logs

COPY environment/cmos018-s112b.lib /opt/eesim/models/cmos018-s112b.lib
COPY solution/reference-a.cir /tests/reference-a.cir
COPY tests/evaluator.py tests/grade.py tests/test.sh tests/test_evaluator.py /tests/
RUN chmod 0444 /opt/eesim/models/cmos018-s112b.lib /tests/reference-a.cir \
        /tests/evaluator.py /tests/test_evaluator.py \
    && chmod 0555 /tests/grade.py /tests/test.sh \
    && PYTHONPATH=/tests python3 /tests/test_evaluator.py

ENV EESIM_CMOS_MODEL=/opt/eesim/models/cmos018-s112b.lib HOME=/home/verifier
USER verifier
WORKDIR /app
