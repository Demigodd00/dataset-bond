"""Deploy, exercise, and verify DatasetBond on GenLayer StudioNet.

The script uses disposable in-memory signers and StudioNet faucet-issued test
GEN. No private key is retained, printed, or committed. Run only after the
current commit and public evidence URLs are available on GitHub.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from eth_account import Account
from eth_utils import to_checksum_address
from genlayer_py import create_client
from genlayer_py.assertions import tx_execution_succeeded
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionHashVariant, TransactionStatus


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_SOURCE = ROOT / "contracts" / "DatasetBondRegistry.py"
JOB_SOURCE = ROOT / "contracts" / "DatasetBondJob.py"
RECORD_PATH = ROOT / "deployments" / "studionet.json"
BASE = "https://raw.githubusercontent.com/Demigodd00/dataset-bond/main/evidence/demo"
MANIFEST_URL = BASE + "/manifest.json"
EVIDENCE_URL = BASE + "/validation.json"
PROVENANCE_URL = BASE + "/provenance.json"
ESCROW_ATTO = 10**15


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def tx_hex(value) -> str:
    rendered = str(value)
    if rendered.startswith("0x"):
        return rendered
    return "0x" + bytes(value).hex()


def preflight() -> None:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    for source in (REGISTRY_SOURCE, JOB_SOURCE):
        subprocess.run(["genvm-lint", str(source)], cwd=ROOT, check=True, env=environment)
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests/direct", "-q"],
        cwd=ROOT,
        check=True,
        env=environment,
    )


def wait(client, transaction) -> dict:
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hex(transaction),
        status=TransactionStatus.FINALIZED,
        interval=5_000,
        retries=120,
        full_transaction=True,
    )
    if not tx_execution_succeeded(receipt):
        raise RuntimeError(json.dumps(receipt, default=str, indent=2))
    return receipt


def extract_address(receipt: dict) -> str:
    for key in ("tx_data_decoded", "data"):
        value = receipt.get(key)
        if isinstance(value, dict) and value.get("contract_address"):
            return to_checksum_address(str(value["contract_address"]))
    raise RuntimeError("deployment receipt did not contain a contract address")


def verify_source(client, address: str, expected: str) -> str:
    response = client.provider.make_request("gen_getContractCode", [address])
    encoded = response.get("result")
    if not isinstance(encoded, str):
        raise RuntimeError("deployed source could not be read")
    actual = base64.b64decode(encoded, validate=True).decode("utf-8")
    if digest(actual) != digest(expected):
        raise RuntimeError("deployed source does not match local source")
    return digest(expected)


def read(client, address: str, method: str, args: list) -> dict | str:
    return client.read_contract(
        address=address,
        function_name=method,
        args=args,
        transaction_hash_variant=TransactionHashVariant.LATEST_FINAL,
    )


def write(client, address: str, method: str, args: list, value: int = 0) -> tuple[str, dict]:
    transaction = client.write_contract(
        address=address,
        function_name=method,
        args=args,
        value=value,
    )
    return tx_hex(transaction), wait(client, transaction)


def main() -> None:
    preflight()
    owner = Account.create()
    provider = Account.create()
    owner_client = create_client(chain=studionet, account=owner)
    provider_client = create_client(chain=studionet, account=provider)
    registry_source = REGISTRY_SOURCE.read_text(encoding="utf-8")
    job_source = JOB_SOURCE.read_text(encoding="utf-8")

    registry_deploy = owner_client.deploy_contract(code=registry_source, account=owner, args=[])
    registry_deploy_receipt = wait(owner_client, registry_deploy)
    registry_address = extract_address(registry_deploy_receipt)

    job_args = [
        registry_address,
        owner.address,
        provider.address,
        "dataset-001",
        "Public Transit Intent Dataset",
        "Deliver a labeled English-language intent dataset for public-transit support requests.",
        "Every record has id, utterance, intent, and source_batch; intent uses the frozen taxonomy.",
        "Labels follow the written intent definitions and the supplied ambiguous-example policy.",
        "Each source_batch is identified and the delivery includes a collection-method declaration.",
        1000,
        6000,
        3600,
        3600,
        3600,
        3600,
        3600,
    ]
    job_deploy = owner_client.deploy_contract(code=job_source, account=owner, args=job_args)
    job_deploy_receipt = wait(owner_client, job_deploy)
    job_address = extract_address(job_deploy_receipt)

    registration_tx, _ = write(
        owner_client,
        registry_address,
        "register_job",
        [job_address, owner.address, provider.address, "dataset-001", "Public Transit Intent Dataset"],
    )
    registered = read(owner_client, registry_address, "get_job", ["dataset-001"])
    if not isinstance(registered, dict) or registered.get("contract_address", "").lower() != job_address.lower():
        raise RuntimeError("registry did not authenticate the deployed job")

    faucet_transaction = owner_client.fund_account(owner.address, ESCROW_ATTO * 10)
    wait(owner_client, faucet_transaction)
    fund_tx, _ = write(owner_client, job_address, "fund", [], value=ESCROW_ATTO)
    accept_tx, _ = write(provider_client, job_address, "accept_job", [])
    manifest_digest = hashlib.sha256(
        (ROOT / "evidence" / "demo" / "manifest.json").read_bytes()
    ).hexdigest()
    submit_args = [MANIFEST_URL, EVIDENCE_URL, PROVENANCE_URL, manifest_digest, 1200]
    submit_tx, _ = write(provider_client, job_address, "submit_delivery", submit_args)
    assess_tx, _ = write(provider_client, job_address, "assess_submission", [])
    state = read(owner_client, job_address, "get_state", [])
    assessment_transactions = [assess_tx]
    submission_transactions = [submit_tx]
    if isinstance(state, dict) and state.get("phase") == "REVISION_REQUIRED":
        revision_tx, _ = write(provider_client, job_address, "submit_delivery", submit_args)
        reassess_tx, _ = write(provider_client, job_address, "assess_submission", [])
        submission_transactions.append(revision_tx)
        assessment_transactions.append(reassess_tx)
        state = read(owner_client, job_address, "get_state", [])
    if not isinstance(state, dict) or state.get("phase") != "REVIEW_WINDOW":
        raise RuntimeError("intelligent assessment did not reach the bounded review window")

    settlement_tx, settlement_receipt = write(owner_client, job_address, "buyer_accept", [])
    triggered = settlement_receipt.get("triggered_transactions", [])
    for child in triggered:
        wait(owner_client, child)
    for _ in range(30):
        registered = read(owner_client, registry_address, "get_job", ["dataset-001"])
        if isinstance(registered, dict) and registered.get("reported") is True:
            break
        time.sleep(5)
    else:
        raise RuntimeError("registry outcome report did not finalize")

    final_state = read(owner_client, job_address, "get_state", [])
    provider_credit = read(owner_client, job_address, "get_credit", [provider.address])
    if not isinstance(final_state, dict) or final_state.get("phase") != "SETTLED":
        raise RuntimeError("job did not settle")
    if provider_credit != str(ESCROW_ATTO):
        raise RuntimeError("provider pull-payment credit does not equal escrow")
    withdraw_tx, withdraw_receipt = write(provider_client, job_address, "withdraw", [])
    for child in withdraw_receipt.get("triggered_transactions", []):
        wait(provider_client, child)
    if read(owner_client, job_address, "get_credit", [provider.address]) != "0":
        raise RuntimeError("provider credit was not cleared after withdrawal")

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    record = {
        "network": "studionet",
        "chain_id": 61999,
        "commit": commit,
        "deployed_at": now_iso(),
        "wallet_policy": "disposable StudioNet-only signers; no secret retained or committed",
        "test_currency": "StudioNet faucet-issued GEN with no monetary value",
        "registry": {
            "address": registry_address,
            "deployer": owner.address,
            "deploy_transaction": tx_hex(registry_deploy),
            "source_sha256": verify_source(owner_client, registry_address, registry_source),
            "registration_transaction": registration_tx,
            "reported_outcome": registered,
        },
        "job": {
            "address": job_address,
            "buyer": owner.address,
            "provider": provider.address,
            "deploy_transaction": tx_hex(job_deploy),
            "source_sha256": verify_source(owner_client, job_address, job_source),
            "constructor_args": job_args,
        },
        "smoke_test": {
            "faucet_transaction": tx_hex(faucet_transaction),
            "fund_transaction": fund_tx,
            "accept_transaction": accept_tx,
            "submission_transactions": submission_transactions,
            "assessment_transactions": assessment_transactions,
            "settlement_transaction": settlement_tx,
            "withdraw_transaction": withdraw_tx,
            "observed_assessment": final_state.get("current_labels"),
            "observed_model_outcome": final_state.get("current_overall"),
            "observed_final_outcome": final_state.get("final_outcome"),
            "provider_credit_after_withdrawal": "0",
        },
    }
    RECORD_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"registry": registry_address, "job": job_address, "record": str(RECORD_PATH)}))


if __name__ == "__main__":
    main()

