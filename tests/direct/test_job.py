from pathlib import Path
import hashlib
import json


CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "DatasetBondJob.py"
ESCROW = 10**18
MANIFEST = "https://evidence.example.org/manifest.json"
EVIDENCE = "https://evidence.example.org/validation.json"
PROVENANCE = "https://evidence.example.org/provenance.json"
MANIFEST_BODY = '{"records":1200,"fields":["id","utterance","intent","source_batch"]}'
DIGEST = hashlib.sha256(MANIFEST_BODY.encode("utf-8")).hexdigest()
PROMPT = "You are evaluating a commissioned dataset delivery"


def address(account) -> str:
    return "0x" + account.hex()


def deploy(vm, direct_deploy, buyer, provider, registry):
    vm.sender = buyer
    return direct_deploy(
        str(CONTRACT),
        address(registry),
        address(buyer),
        address(provider),
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
    )


def fund_accept_submit(contract, vm, buyer, provider):
    vm.sender = buyer
    vm.value = ESCROW
    contract.fund()
    vm.value = 0
    vm.sender = provider
    contract.accept_job()
    contract.submit_delivery(MANIFEST, EVIDENCE, PROVENANCE, DIGEST, 1200)


def assessment(**overrides):
    result = {
        "schema": "PASS",
        "completeness": "PASS",
        "annotation": "PASS",
        "consistency": "PASS",
        "provenance": "PASS",
        "summary": "The supplied packet affirmatively supports all five frozen dimensions.",
    }
    result.update(overrides)
    return result


def mock_packet(vm, result):
    vm.mock_web(MANIFEST, {"status": 200, "body": MANIFEST_BODY})
    vm.mock_web(EVIDENCE, {"status": 200, "body": '{"schema_errors":0,"label_audit_accuracy":0.97,"duplicate_rate":0.002}'})
    vm.mock_web(PROVENANCE, {"status": 200, "body": '{"source_batches":["batch-a"],"collection_method":"consented support simulation"}'})
    vm.mock_llm(PROMPT, json.dumps(result))


def test_consensus_assessment_and_buyer_accept_create_pull_credit(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie)
    fund_accept_submit(contract, direct_vm, direct_alice, direct_bob)
    mock_packet(direct_vm, assessment())
    contract.assess_submission()
    leader = direct_vm._captured_validators[-1][0]
    for _ in range(5):
        assert direct_vm.run_validator(leader_result=leader) is True
    assert contract.get_assessment(1)["overall"] == "ACCEPT"

    direct_vm.sender = direct_alice
    contract.buyer_accept()
    state = contract.get_state()
    assert state["phase"] == "SETTLED"
    assert state["final_outcome"] == "BUYER_ACCEPTED"
    assert contract.get_credit(address(direct_bob)) == str(ESCROW)
    assert state["registry_report_attempts"] == "1"


def test_unclear_result_allows_exactly_one_revision(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie)
    fund_accept_submit(contract, direct_vm, direct_alice, direct_bob)
    mock_packet(direct_vm, assessment(annotation="UNCLEAR", summary="The annotation audit is ambiguous."))
    contract.assess_submission()
    assert contract.get_state()["phase"] == "REVISION_REQUIRED"

    direct_vm.clear_mocks()
    direct_vm.sender = direct_bob
    contract.submit_delivery(MANIFEST, EVIDENCE, PROVENANCE, DIGEST, 1200)
    mock_packet(direct_vm, assessment())
    contract.assess_submission()
    state = contract.get_state()
    assert state["phase"] == "REVIEW_WINDOW"
    assert state["revision_used"] is True
    assert state["submission_version"] == "2"
    with direct_vm.expect_revert("delivery_or_revision_required"):
        contract.submit_delivery(MANIFEST, EVIDENCE, PROVENANCE, "c" * 64, 1200)


def test_partial_accept_uses_deterministic_sixty_forty_split(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie)
    fund_accept_submit(contract, direct_vm, direct_alice, direct_bob)
    mock_packet(
        direct_vm,
        assessment(completeness="FAIL", consistency="FAIL", summary="Three dimensions pass; two non-hard dimensions fail."),
    )
    contract.assess_submission()
    assert contract.get_state()["current_overall"] == "PARTIAL_ACCEPT"
    contract.action_deadline_unix = 0
    contract.close_expired()
    assert contract.get_credit(address(direct_bob)) == str(ESCROW * 60 // 100)
    assert contract.get_credit(address(direct_alice)) == str(ESCROW * 40 // 100)


def test_abandoned_funded_job_is_permissionlessly_refundable(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie)
    direct_vm.sender = direct_alice
    direct_vm.value = ESCROW
    contract.fund()
    direct_vm.value = 0
    contract.acceptance_deadline_unix = 0
    direct_vm.sender = direct_charlie
    contract.close_expired()
    assert contract.get_state()["final_outcome"] == "ACCEPTANCE_TIMEOUT"
    assert contract.get_credit(address(direct_alice)) == str(ESCROW)


def test_schema_failure_is_hard_reject_and_malformed_llm_fails_closed(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie)
    fund_accept_submit(contract, direct_vm, direct_alice, direct_bob)
    mock_packet(direct_vm, assessment(schema="FAIL", summary="Required schema fields are absent."))
    contract.assess_submission()
    assert contract.get_state()["current_overall"] == "REJECT"


def test_malformed_llm_response_fails_closed(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie)
    fund_accept_submit(contract, direct_vm, direct_alice, direct_bob)
    mock_packet(direct_vm, {"schema": "PASS"})
    with direct_vm.expect_revert("invalid_response_shape"):
        contract.assess_submission()


def test_changed_manifest_is_rejected_before_model_assessment(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract = deploy(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie)
    fund_accept_submit(contract, direct_vm, direct_alice, direct_bob)
    direct_vm.mock_web(MANIFEST, {"status": 200, "body": '{"records":9999}'})
    direct_vm.mock_web(EVIDENCE, {"status": 200, "body": "{}"})
    direct_vm.mock_web(PROVENANCE, {"status": 200, "body": "{}"})
    with direct_vm.expect_revert("manifest_digest_mismatch"):
        contract.assess_submission()
