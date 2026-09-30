from __future__ import annotations

import json
from pathlib import Path

from gltest import get_contract_factory, get_validator_factory
from gltest.accounts import create_accounts
from gltest.assertions import tx_execution_succeeded
from gltest.types import TransactionStatus
from gltest.utils import extract_contract_address


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "contracts" / "DatasetBondRegistry.py"
JOB = ROOT / "contracts" / "DatasetBondJob.py"
ESCROW = 10**18
MANIFEST = "https://evidence.example.org/manifest.json"
EVIDENCE = "https://evidence.example.org/validation.json"
PROVENANCE = "https://evidence.example.org/provenance.json"
PROMPT = "You are evaluating a commissioned dataset delivery"


def ok(receipt):
    if not tx_execution_succeeded(receipt):
        raise AssertionError(json.dumps(receipt, default=str, indent=2))
    return receipt


def consensus_context():
    result = json.dumps(
        {
            "schema": "PASS",
            "completeness": "PASS",
            "annotation": "PASS",
            "consistency": "PASS",
            "provenance": "PASS",
            "summary": "The evidence supports every frozen delivery dimension.",
        }
    )
    web = {
        "nondet_web_request": {
            MANIFEST: {
                "method": "GET",
                "status": 200,
                "body": '{"records":1200,"fields":["id","utterance","intent","source_batch"]}',
            },
            EVIDENCE: {
                "method": "GET",
                "status": 200,
                "body": '{"schema_errors":0,"label_audit_accuracy":0.97,"duplicate_rate":0.002}',
            },
            PROVENANCE: {
                "method": "GET",
                "status": 200,
                "body": '{"source_batches":["batch-a"],"collection_method":"consented support simulation"}',
            },
        }
    }
    llm = {"nondet_exec_prompt": {PROMPT: result}}
    validators = get_validator_factory().batch_create_mock_validators(
        5, mock_llm_response=llm, mock_web_response=web
    )
    return {"validators": [validator.to_dict() for validator in validators]}


def test_five_validator_linked_contract_registration():
    owner, buyer_account, provider_account = create_accounts(3)
    registry_factory = get_contract_factory(contract_file_path=REGISTRY)
    job_factory = get_contract_factory(contract_file_path=JOB)

    registry_deploy = ok(
        registry_factory.deploy_contract_tx(
            args=[], account=owner, wait_transaction_status=TransactionStatus.FINALIZED
        )
    )
    registry_address = extract_contract_address(registry_deploy)
    registry = registry_factory.build_contract(registry_address, account=owner)

    job_args = [
        registry_address,
        buyer_account.address,
        provider_account.address,
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
    job_deploy = ok(
        job_factory.deploy_contract_tx(
            args=job_args,
            account=buyer_account,
            wait_transaction_status=TransactionStatus.FINALIZED,
        )
    )
    job_address = extract_contract_address(job_deploy)
    buyer = job_factory.build_contract(job_address, account=buyer_account)
    ok(
        registry.register_job(
            args=[
                job_address,
                buyer_account.address,
                provider_account.address,
                "dataset-001",
                "Public Transit Intent Dataset",
            ]
        ).transact(wait_transaction_status=TransactionStatus.FINALIZED)
    )
    registered = registry.get_job(args=["dataset-001"]).call()
    state = buyer.get_state(args=[]).call()
    assert registered["contract_address"] == job_address.lower()
    assert registered["buyer"] == buyer_account.address.lower()
    assert registered["provider"] == provider_account.address.lower()
    assert state["phase"] == "AWAITING_FUNDING"
    assert state["registry"] == registry_address.lower()
    assert registry.is_authorized_job(args=[job_address]).call() is True

    # genlayer-test 0.29.2 GLSim currently drops top-level transaction value.
    # Payable funding and intelligent adjudication are therefore exercised by
    # direct-mode validator replay and by the separate StudioNet smoke path.
