# DatasetBond

DatasetBond is a GenLayer-native escrow and reputation protocol for commissioned dataset deliveries. A buyer locks funds, a provider accepts a bounded job and submits versioned evidence, and GenLayer validators independently inspect the public delivery packet before the contract deterministically derives a payout.

It is built as two linked Intelligent Contracts:

- `DatasetBondJob` owns one escrow lifecycle, its frozen requirements, versioned submissions, five-dimensional AI assessment, revision/challenge process, timeout closure, and pull-payment credits.
- `DatasetBondRegistry` authenticates deployed jobs and accepts reputation reports only from their registered contract addresses, preventing users from spoofing successful outcomes.

## Why this is an Intelligent Contract

DatasetBond does not store one free-form LLM label. Validators independently refetch three bounded evidence documents and bind five intermediate judgments: schema, completeness, annotation quality, consistency, and provenance. Payment is then derived by explicit contract rules. The assessment feeds a reusable lifecycle with revision, challenge, settlement, withdrawal, timeout recovery, and role-specific reputation.

## Decision policy

| Stored dimensions | Contract result |
| --- | --- |
| Schema or provenance is `FAIL` | `REJECT` |
| All five are `PASS` | `ACCEPT` |
| Any is `UNCLEAR` on first review | `REVISE` once |
| Three or four pass, no unclear or hard failure | `PARTIAL_ACCEPT` |
| Anything else | `REJECT` |

The LLM never chooses a payout. A buyer may voluntarily accept during review; otherwise the frozen policy settles after the review deadline. The sample partial payout is 60% to the provider and 40% back to the buyer.

## Repository map

```text
contracts/       tracked GenLayer contract source
tests/direct/    hardened lifecycle, consensus replay, and failure tests
tests/integration/ linked-contract GLSim test
evidence/demo/   public-style sample assessment packet
frontend/        static policy and lifecycle explorer
deployments/     network deployment records
docs/            architecture, security, audit, and submission notes
```

## Run locally

Python 3.12 is recommended.

```powershell
python -m pip install -r requirements.txt
genvm-lint contracts/DatasetBondRegistry.py
genvm-lint contracts/DatasetBondJob.py
python -m pytest tests/direct -q
```

For the linked-contract simulation, start GLSim in one terminal and run the integration test in another:

```powershell
python tests/run_glsim.py --no-browser --seed 42
python -m pytest tests/integration/test_glsim_linked_contracts.py -q
```

## Deployment order

1. Deploy `DatasetBondRegistry.py` from the registry-owner wallet.
2. Deploy `DatasetBondJob.py` with that registry address and frozen job terms.
3. From the registry owner, call `register_job` with the exact deployed job address, buyer, provider, job ID, and title.
4. Verify both addresses and source hashes in `deployments/studionet.json` before publishing evidence links.

The release script performs those steps with disposable StudioNet-only signers, faucet-issued test GEN, a complete assessment and settlement lifecycle, and exact deployed-source verification:

```powershell
python scripts/deploy_studionet.py
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SECURITY.md](docs/SECURITY.md), and [docs/SUBMISSION.md](docs/SUBMISSION.md) for the full rationale and submission checklist.
