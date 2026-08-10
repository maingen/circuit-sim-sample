# Circuit Simulation Sample Environments

This repository contains five EESimBench electrical-engineering tasks as self-contained Harbor environments. It also contains eight final Grok 4.5 rollouts for each task, including the submitted circuit, complete trajectory, and production verifier result.

## Repository contents

- `harbor/` contains the five runnable task packages.
- `rollouts/` contains 40 retained model runs and their final grades.
- `tasks.csv` is the machine-readable task catalog.
- `tasks.md` explains the engineering work and the retained results.
- `.env.example` lists the credential needed to run Grok Build.
- `LICENSE` contains the Apache License 2.0 terms and repository canary.

## Run a Harbor task

Install Docker and Harbor 0.20.0. The immutable task images are published in ECR Public, so Docker registry authentication is not required. Copy `.env.example` to `.env` and set `XAI_API_KEY` before running Grok Build.

For example, this command starts the current-mirror unity-gain buffer task:

```bash
harbor run \
  -p harbor/current-mirror-unity-gain-buffer \
  -a grok-build \
  -m grok-4.5 \
  -e docker \
  --env-file .env \
  --ae 'XAI_API_KEY=${XAI_API_KEY}' \
  --ak version=0.2.118 \
  --ak reasoning_effort=high
```

The task packages use immutable agent and verifier image digests. The verifier runs separately without network access.

## Verify without a model API key

| Agent | Submitted artifact | Artifact evaluable | Production pass | Reward |
| --- | --- | ---: | ---: | ---: |
| Oracle | Checked-in reference circuit | 1.0 | 1.0 | 1.0 |
| No-op | None | 0.0 | 0.0 | 0.0 |

### Oracle

```bash
harbor run \
  -p harbor/current-mirror-unity-gain-buffer \
  -a oracle \
  --job-name oracle-run \
  -y
```

### No-op

```bash
harbor run \
  -p harbor/current-mirror-unity-gain-buffer \
  -a nop \
  --job-name nop-run \
  -y
```

## Grok 4.5 Rollouts

`rollouts/rollouts.jsonl` begins with one collection record followed by one record for each rollout. Every rollout directory contains:

- `agent/raw.txt.gz`, which preserves the raw Grok Build stream.
- `agent/trajectory.json.gz`, which preserves the complete Harbor trajectory.
- `submission/candidate.cir`, which is the circuit submitted for grading.
- `verifier/`, which contains the final grade, reward, logs, and any simulation artifacts.
- `metadata/`, which contains the Harbor configuration, lock, result, artifact manifest, and grading provenance.

The final retained results are:

| Task | Evaluable | Mean reward | Population variance |
| --- | ---: | ---: | ---: |
| Cascoded current-mirror OTA | 6/8 | 0.576312 | 0.202794 |
| Two-stage CMOS op amp | 3/8 | 0.369038 | 0.227029 |
| Loaded source follower | 2/8 | 0.240385 | 0.173724 |
| Automatic gain controller | 6/8 | 0.449366 | 0.202049 |
| Transistor-level PAM4 TIA | 7/8 | 0.525935 | 0.046290 |

Use the checksum manifest to verify every retained evidence file:

```bash
cd rollouts
shasum -a 256 -c SHA256SUMS
```

The task catalog and each rollout's provenance record identify the exact EESimBench source revision used for export.

## License

This repository uses the Apache License 2.0. See `LICENSE` for the complete terms and canary notice.
