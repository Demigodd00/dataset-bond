# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
from datetime import datetime, timezone
import re


ERROR_EXPECTED = "[EXPECTED]"
VERSION = "1.0.0"
MAX_TEXT_CHARS = 4_000
MAX_TITLE_CHARS = 96
MIN_WINDOW_SECS = 300
MAX_WINDOW_SECS = 2_592_000


def _now_unix() -> int:
    return int(datetime.fromisoformat(gl.message_raw["datetime"]).timestamp())


def _to_iso(value: int) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _address(value: str) -> Address:
    cleaned = value.strip()
    if re.fullmatch(r"0x[0-9a-fA-F]{40}", cleaned) is None:
        raise gl.vm.UserError(f"{ERROR_EXPECTED} invalid address")
    if cleaned.lower() == "0x0000000000000000000000000000000000000000":
        raise gl.vm.UserError(f"{ERROR_EXPECTED} zero address is not allowed")
    return Address(cleaned)


def _text(value: str, label: str, maximum: int = MAX_TEXT_CHARS) -> str:
    cleaned = value.strip()
    if len(cleaned) == 0 or len(cleaned) > maximum or "\x00" in cleaned:
        raise gl.vm.UserError(f"{ERROR_EXPECTED} {label} must be 1..{maximum} characters")
    return cleaned


def _window(value: u256, label: str) -> u256:
    amount = int(value)
    if amount < MIN_WINDOW_SECS or amount > MAX_WINDOW_SECS:
        raise gl.vm.UserError(
            f"{ERROR_EXPECTED} {label} must be {MIN_WINDOW_SECS}..{MAX_WINDOW_SECS} seconds"
        )
    return value


@allow_storage
@dataclass
class JobRecord:
    id: str
    contract_address: Address
    buyer: Address
    provider: Address
    title: str
    created_at_unix: u256
    created_at_iso: str
    reported: bool
    final_outcome: str
    provider_payout_bps: u256
    buyer_refund_bps: u256
    settled_at_unix: u256
    settled_at_iso: str


@allow_storage
@dataclass
class Reputation:
    completed_jobs: u256
    accepted_jobs: u256
    partial_jobs: u256
    rejected_jobs: u256
    timeout_jobs: u256
    cumulative_provider_payout_bps: u256
    cumulative_buyer_refund_bps: u256


class DatasetBondRegistry(gl.Contract):
    owner: Address
    next_job_id: u256
    total_jobs: u256
    total_reported: u256
    jobs: TreeMap[str, JobRecord]
    job_ids: DynArray[str]
    authorized_jobs: TreeMap[str, bool]
    job_id_by_address: TreeMap[str, str]
    provider_reputation: TreeMap[str, Reputation]
    buyer_reputation: TreeMap[str, Reputation]

    def __init__(self):
        self.owner = gl.message.sender_address
        self.next_job_id = u256(1)
        self.total_jobs = u256(0)
        self.total_reported = u256(0)

    @gl.public.write
    def register_job(
        self,
        job_address: str,
        buyer: str,
        provider: str,
        job_id: str,
        title: str,
    ) -> None:
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} only registry owner can authenticate jobs")
        contract_address = _address(job_address)
        buyer_address = _address(buyer)
        provider_address = _address(provider)
        if provider_address == buyer_address:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} buyer and provider must be different")
        job_id = _text(job_id, "job id", 64)
        title = _text(title, "title", MAX_TITLE_CHARS)
        address_key = str(contract_address).lower()
        if self.authorized_jobs.get(address_key, False):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} job address already registered")
        if job_id in self.jobs:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} job id already registered")
        now = _now_unix()
        self.jobs[job_id] = JobRecord(
            id=job_id,
            contract_address=contract_address,
            buyer=buyer_address,
            provider=provider_address,
            title=title,
            created_at_unix=u256(now),
            created_at_iso=_to_iso(now),
            reported=False,
            final_outcome="",
            provider_payout_bps=u256(0),
            buyer_refund_bps=u256(0),
            settled_at_unix=u256(0),
            settled_at_iso="",
        )
        self.authorized_jobs[address_key] = True
        self.job_id_by_address[address_key] = job_id
        self.job_ids.append(job_id)
        self.next_job_id = u256(int(self.next_job_id) + 1)
        self.total_jobs = u256(int(self.total_jobs) + 1)

    @gl.public.write
    def record_outcome(
        self,
        outcome: str,
        provider_payout_bps: u256,
        buyer_refund_bps: u256,
    ) -> None:
        sender_key = str(gl.message.sender_address).lower()
        if not self.authorized_jobs.get(sender_key, False):
            raise gl.vm.UserError(f"{ERROR_EXPECTED} unauthenticated job contract")
        job_id = self.job_id_by_address[sender_key]
        job = self.jobs[job_id]
        if job.reported:
            return
        normalized = outcome.strip().upper()
        allowed = (
            "ACCEPT",
            "BUYER_ACCEPTED",
            "PARTIAL_ACCEPT",
            "REJECT",
            "PROVIDER_DECLINED",
            "BUYER_CANCELLED",
            "ACCEPTANCE_TIMEOUT",
            "DELIVERY_TIMEOUT",
            "ASSESSMENT_TIMEOUT",
            "REVISION_TIMEOUT",
        )
        if normalized not in allowed:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} invalid final outcome")
        provider_bps = int(provider_payout_bps)
        buyer_bps = int(buyer_refund_bps)
        if provider_bps < 0 or buyer_bps < 0 or provider_bps + buyer_bps != 10_000:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} payout basis points must total 10000")

        now = _now_unix()
        job.reported = True
        job.final_outcome = normalized
        job.provider_payout_bps = provider_payout_bps
        job.buyer_refund_bps = buyer_refund_bps
        job.settled_at_unix = u256(now)
        job.settled_at_iso = _to_iso(now)
        self.jobs[job_id] = job
        self.total_reported = u256(int(self.total_reported) + 1)
        provider_key = str(job.provider).lower()
        buyer_key = str(job.buyer).lower()
        provider_stats = self._reputation(self.provider_reputation, provider_key)
        buyer_stats = self._reputation(self.buyer_reputation, buyer_key)
        provider_stats.completed_jobs = u256(int(provider_stats.completed_jobs) + 1)
        buyer_stats.completed_jobs = u256(int(buyer_stats.completed_jobs) + 1)
        provider_stats.cumulative_provider_payout_bps = u256(
            int(provider_stats.cumulative_provider_payout_bps) + provider_bps
        )
        buyer_stats.cumulative_buyer_refund_bps = u256(
            int(buyer_stats.cumulative_buyer_refund_bps) + buyer_bps
        )
        if normalized in ("ACCEPT", "BUYER_ACCEPTED"):
            provider_stats.accepted_jobs = u256(int(provider_stats.accepted_jobs) + 1)
            buyer_stats.accepted_jobs = u256(int(buyer_stats.accepted_jobs) + 1)
        elif normalized == "PARTIAL_ACCEPT":
            provider_stats.partial_jobs = u256(int(provider_stats.partial_jobs) + 1)
            buyer_stats.partial_jobs = u256(int(buyer_stats.partial_jobs) + 1)
        elif normalized.endswith("TIMEOUT"):
            provider_stats.timeout_jobs = u256(int(provider_stats.timeout_jobs) + 1)
            buyer_stats.timeout_jobs = u256(int(buyer_stats.timeout_jobs) + 1)
        else:
            provider_stats.rejected_jobs = u256(int(provider_stats.rejected_jobs) + 1)
            buyer_stats.rejected_jobs = u256(int(buyer_stats.rejected_jobs) + 1)
        self.provider_reputation[provider_key] = provider_stats
        self.buyer_reputation[buyer_key] = buyer_stats

    def _reputation(self, index: TreeMap[str, Reputation], key: str) -> Reputation:
        if key in index:
            return index[key]
        return Reputation(
            completed_jobs=u256(0),
            accepted_jobs=u256(0),
            partial_jobs=u256(0),
            rejected_jobs=u256(0),
            timeout_jobs=u256(0),
            cumulative_provider_payout_bps=u256(0),
            cumulative_buyer_refund_bps=u256(0),
        )

    @gl.public.view
    def is_authorized_job(self, job_address: str) -> bool:
        return self.authorized_jobs.get(job_address.strip().lower(), False)

    @gl.public.view
    def get_job(self, job_id: str) -> dict:
        if job_id not in self.jobs:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} job not found")
        job = self.jobs[job_id]
        return {
            "id": job.id,
            "contract_address": str(job.contract_address).lower(),
            "buyer": str(job.buyer).lower(),
            "provider": str(job.provider).lower(),
            "title": job.title,
            "created_at_unix": str(int(job.created_at_unix)),
            "created_at_iso": job.created_at_iso,
            "reported": job.reported,
            "final_outcome": job.final_outcome,
            "provider_payout_bps": str(int(job.provider_payout_bps)),
            "buyer_refund_bps": str(int(job.buyer_refund_bps)),
            "settled_at_unix": str(int(job.settled_at_unix)),
            "settled_at_iso": job.settled_at_iso,
        }

    @gl.public.view
    def get_reputation(self, account: str) -> dict:
        account_key = str(_address(account)).lower()
        provider = self._reputation(self.provider_reputation, account_key)
        buyer = self._reputation(self.buyer_reputation, account_key)
        return {
            "account": account_key,
            "provider": self._reputation_dict(provider),
            "buyer": self._reputation_dict(buyer),
        }

    def _reputation_dict(self, value: Reputation) -> dict:
        completed = int(value.completed_jobs)
        provider_average = 0
        buyer_average = 0
        if completed > 0:
            provider_average = int(value.cumulative_provider_payout_bps) // completed
            buyer_average = int(value.cumulative_buyer_refund_bps) // completed
        return {
            "completed_jobs": str(completed),
            "accepted_jobs": str(int(value.accepted_jobs)),
            "partial_jobs": str(int(value.partial_jobs)),
            "rejected_jobs": str(int(value.rejected_jobs)),
            "timeout_jobs": str(int(value.timeout_jobs)),
            "average_provider_payout_bps": str(provider_average),
            "average_buyer_refund_bps": str(buyer_average),
        }

    @gl.public.view
    def get_policy(self) -> dict:
        return {
            "name": "DatasetBond Registry",
            "version": VERSION,
            "owner_authenticated_jobs_only": True,
            "duplicate_reports": "IDEMPOTENT",
            "reputation_dimensions": "OUTCOME_COUNTS_AND_AVERAGE_PAYOUT_SPLIT",
            "holds_job_funds": False,
            "runner": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6",
        }
