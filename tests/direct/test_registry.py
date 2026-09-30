from pathlib import Path


CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "DatasetBondRegistry.py"
SDK = "v0.2.16"


def address(account) -> str:
    return "0x" + account.hex()


def deploy(vm, direct_deploy, owner):
    vm.sender = owner
    return direct_deploy(str(CONTRACT), sdk_version=SDK)


def test_owner_authenticates_job_and_reputation_is_idempotent(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    registry = deploy(direct_vm, direct_deploy, direct_alice)
    registry.register_job(
        address(direct_charlie),
        address(direct_alice),
        address(direct_bob),
        "dataset-001",
        "Public Transit Intent Dataset",
    )
    assert registry.is_authorized_job(address(direct_charlie)) is True

    direct_vm.sender = direct_charlie
    registry.record_outcome("PARTIAL_ACCEPT", 6000, 4000)
    registry.record_outcome("PARTIAL_ACCEPT", 6000, 4000)

    job = registry.get_job("dataset-001")
    provider = registry.get_reputation(address(direct_bob))["provider"]
    assert job["reported"] is True
    assert job["final_outcome"] == "PARTIAL_ACCEPT"
    assert registry.get_policy()["duplicate_reports"] == "IDEMPOTENT"
    assert provider["completed_jobs"] == "1"
    assert provider["partial_jobs"] == "1"
    assert provider["average_provider_payout_bps"] == "6000"


def test_registration_and_reporting_reject_spoofers(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    registry = deploy(direct_vm, direct_deploy, direct_alice)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only registry owner"):
        registry.register_job(
            address(direct_charlie),
            address(direct_alice),
            address(direct_bob),
            "spoofed",
            "Spoofed Job",
        )
    with direct_vm.expect_revert("unauthenticated job contract"):
        registry.record_outcome("ACCEPT", 10000, 0)
