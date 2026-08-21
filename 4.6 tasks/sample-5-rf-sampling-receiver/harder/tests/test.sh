#!/bin/sh
set -u
mkdir -p /logs/verifier
python3 /tests/grade.py > /logs/verifier/test-stdout.txt 2> /logs/verifier/test-stderr.txt
status=$?
if [ "$status" -ne 0 ] || [ ! -s /logs/verifier/reward.json ]; then
  printf '{"reward":0.0,"production_pass":0.0,"artifact_evaluable":0.0}\n' > /logs/verifier/reward.json
fi
exit 0
