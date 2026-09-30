import os
import time

import pytest
import requests
from genlayer_py import create_account
from tests.windows_compat import install


install()


READ_ONLY_RPC_METHODS = {
    "eth_call",
    "eth_getTransactionByHash",
    "gen_getContractCode",
    "gen_getContractSchema",
    "gen_getTransactionReceipt",
}


@pytest.fixture(autouse=True)
def resilient_studionet_reads(monkeypatch):
    """Retry hosted read failures without ever replaying a signed write."""
    original_post = requests.post

    def post(url, *args, **kwargs):
        payload = kwargs.get("json")
        method = payload.get("method") if isinstance(payload, dict) else ""
        if "studio.genlayer.com" not in str(url) or method not in READ_ONLY_RPC_METHODS:
            return original_post(url, *args, **kwargs)
        kwargs["timeout"] = (10, 45)
        last_error = None
        response = None
        for attempt in range(5):
            try:
                response = original_post(url, *args, **kwargs)
                if response.status_code < 500:
                    return response
            except requests.RequestException as error:
                last_error = error
            time.sleep(2**attempt)
        if response is not None:
            return response
        if last_error is not None:
            raise last_error
        raise RuntimeError("StudioNet read retry exhausted")

    monkeypatch.setattr(requests, "post", post)


@pytest.fixture(autouse=True)
def hardened_direct_mode(request):
    """Enable production serialization and stale-mock checks."""
    if "direct_vm" not in request.fixturenames:
        yield
        return
    direct_vm = request.getfixturevalue("direct_vm")
    direct_vm.check_pickling = True
    direct_vm.strict_mocks = True
    yield


@pytest.fixture(scope="session")
def default_account():
    private_key = os.getenv("GENLAYER_PRIVATE_KEY")
    if not private_key:
        pytest.fail("GENLAYER_PRIVATE_KEY is required for StudioNet tests")
    return create_account(private_key)


@pytest.fixture(scope="session")
def secondary_account():
    private_key = os.getenv("GENLAYER_SECONDARY_PRIVATE_KEY")
    if not private_key:
        pytest.fail("GENLAYER_SECONDARY_PRIVATE_KEY is required for two-party StudioNet tests")
    return create_account(private_key)

