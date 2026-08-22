# Path 3 TIA Grok 4.6 rollout validation

Validated on 2026-08-21 after all authorized attempts reached a terminal state.

## Outcome

- Eight of eight authorized scorable rollouts are retained with complete native trajectories, native session archives, submitted `candidate.cir` artifacts, and production-verifier grades.
- Twenty attempts were launched. Twelve infrastructure failures were excluded and replaced on the same frozen task revision: ten nonzero agent exits, one API rate-limit failure, and one API overload failure.
- The frozen verifier produced a mean reward of 0.6312749522327985 and population variance of 0.008326963132884552. No rollout achieved the exact `1.0` required for a production pass.
- Deterministic regrading with the corrected private verifier produced a mean reward of 0.6228480474034194 and population variance of 0.008299132443941292. The correction did not change the model-visible task contract or execution environment.
- Canonical GPT-5.6 Terra review produced a mean reward of 0.37359020124708964 and population variance of 0.018686749080303537 across all eight submissions. No rollout achieved a canonical production pass.
- Six artifacts completed every simulation family. Two retained submissions caused transient simulation-family failures; these remain valid scored model outcomes and are not infrastructure failures.

## Evidence checks

All eight retained runs passed the following checks:

- the compressed ATIF trajectory, raw transcript, submitted netlist, and source job artifacts are byte-identical after decompression;
- trajectory schema, model session identifier, agent steps, and terminal state are present;
- no retained run contains an agent exception;
- the native session archive contains the original event stream;
- candidate, trajectory, and metadata hashes match each run's provenance record;
- frozen verifier details, reward, logs, and simulation artifacts are retained;
- corrected deterministic regrades contain all 28 criterion records;
- run identifiers and model session identifiers are unique across the retained set.

The campaign has no remaining live Docker container or Kubernetes sandbox.

## Canonical review validation

All eight post-hoc GPT-5.6 Terra canonical reviews are complete. Each retained canonical grade contains a structured six-section judgment, a completed API response identifier and returned-model record, immutable input hashes, the original deterministic score, and the section-gated composite score. No canonical review ended in an authentication, rate-limit, malformed-response, or other grading-infrastructure failure.

See `qualification.json` for machine-readable campaign provenance and `canonical-verifier-summary.json` for canonical-review status.
