# Security model

## Trust boundaries

- Public evidence is adversarial input. It is size-bounded, UTF-8 checked, and framed as data rather than instructions.
- The fetched manifest must match the provider's submitted SHA-256 digest before model assessment begins.
- LLM output is untrusted until its exact six-field shape and five label values are validated.
- Payment is deterministic contract code; an LLM cannot set amounts or invent a settlement category.
- Registry reputation accepts reports only when `gl.message.sender_address` is an authenticated job address.
- The registry owner must inspect the deployed child source and constructor values before registration.

## Economic safety

- Only the named buyer can fund and voluntarily accept.
- Only the named provider can accept the job and submit a delivery.
- Escrow has explicit minimum and maximum bounds.
- Every funded wait has a bounded deadline and permissionless close function.
- Settlement uses checks-effects-interactions and pull payments.
- Duplicate registry reports are idempotent.
- Registry retries are capped at three to prevent unbounded report spam.

## Assessment safety

- Schema and provenance are hard-failure dimensions.
- `UNCLEAR` cannot be silently treated as acceptance.
- Exactly one revision and one scoped challenge are available.
- A challenge can modify only its named dimension, after independently fetching original and counterevidence.
- Summaries never participate in equivalence or payout decisions.

## Known boundaries

DatasetBond evaluates whether submitted evidence supports frozen delivery requirements. It does not certify copyright ownership, privacy compliance, regulatory compliance, or the truth of facts outside the fetched evidence. Production users should independently audit data rights and privacy.

Owner-authenticated registration is intentionally used instead of an on-chain Python child factory because the pinned standard GenVM runner is lintable and reproducible as a single-file Studio deployment. Registration must be accompanied by source-hash verification.
