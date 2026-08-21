# Canonical section-gated verifier

This private post-Harbor verifier combines the frozen deterministic Ngspice grade with one structured GPT-5.6 Terra circuit-integrity review. The Ngspice verifier remains isolated without network access. The judge receives only immutable copies of the public instructions, reference circuit, submitted circuit, deterministic evidence, and section ledger.

This composite result is the canonical grade. The raw Ngspice result is retained as provenance and must not be reported as the final grade once the composite verifier has completed.

Each of the 28 deterministic criteria belongs to exactly one circuit section. A section-level `pass` preserves its criteria rewards. A section-level `fail` sets only its criteria rewards to zero. An `indeterminate` or malformed judge result is a grading-infrastructure failure and does not become a candidate failure.

The original deterministic grade remains in every canonical report. The canonical report records artifact, prompt, ledger, reference, and evidence hashes together with the OpenAI response identifier and returned model identifier.

Run deterministic QA with:

```sh
python3 canonical-verifier/test_canonical_verifier.py
```

Run one retained submission with:

```sh
python3 canonical-verifier/canonical_verifier.py \
  --candidate /path/to/candidate.cir \
  --static-details /path/to/details.json \
  --instruction instruction.md \
  --reference solution/reference.cir \
  --output-dir /path/to/canonical-grade
```

The command reads `OPENAI_API_KEY` from the process environment. It never reads or writes a credential file.

Install the pinned client dependency with:

```sh
python3 -m pip install -r canonical-verifier/requirements.txt
```

Do not rerun an agent merely because this private verifier changed. Regrade its retained candidate and frozen deterministic `details.json`, store the composite output beside the original evidence, and preserve both grades. Judge infrastructure failures are retried with a fresh output directory and never counted as model outcomes.

If only the deterministic combiner changes, a previously retained `judge.json` may be replayed with `--judge-response` and its original `provenance.json` supplied through `--judge-metadata`. This preserves the real response ID and returned-model record without making a second model judgment.
