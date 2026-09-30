# Submission package

## Suggested title

DatasetBond — AI-Adjudicated Dataset Delivery Escrow

## Suggested description

DatasetBond is a GenLayer-native escrow and reputation protocol for commissioned datasets, implemented as two linked Intelligent Contracts. A buyer funds an isolated `DatasetBondJob`; the provider accepts frozen requirements and submits versioned manifest, validation, and provenance evidence. Five focused intelligent transactions independently refetch that evidence and bind one judgment each—schema, completeness, annotation quality, consistency, and provenance—under the Equivalence Principle.

The LLM never decides payment. Contract code deterministically maps the five stored labels to acceptance, one bounded revision, partial payout, or rejection. A scoped challenge can re-evaluate one dimension, while permissionless deadlines close every abandoned funded state. Settlement uses pull-payment credits and strict accounting. The linked `DatasetBondRegistry` accepts final reports only from owner-authenticated job addresses, making its role-specific reputation ledger resistant to spoofed outcomes.

## Evidence links to submit

1. Public repository root.
2. Exact `DatasetBondJob.py` source URL.
3. Exact `DatasetBondRegistry.py` source URL.
4. Studio deployment page for the job.
5. Studio deployment page for the registry.
6. Commit-pinned deployment record containing both addresses, transaction hashes, and source SHA-256 values.

Do not submit until `deployments/studionet.json` contains real values and each link works in a private/incognito browser window.
