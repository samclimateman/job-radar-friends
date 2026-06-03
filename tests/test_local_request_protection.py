import asyncio
from types import SimpleNamespace

from starlette.responses import JSONResponse

from job_radar.api.main import reject_cross_site_mutations
from job_radar.security.local_requests import is_trusted_local_request


def test_local_post_allows_same_origin():
    assert is_trusted_local_request(
        method="POST",
        origin="http://127.0.0.1:8766",
        referer=None,
        sec_fetch_site="same-origin",
        allowed_ports={8766},
    )


def test_local_post_rejects_cross_site_origin():
    assert not is_trusted_local_request(
        method="POST",
        origin="https://evil.example",
        referer=None,
        sec_fetch_site="cross-site",
        allowed_ports={8766},
    )


def test_local_post_rejects_same_site_wrong_port():
    assert not is_trusted_local_request(
        method="POST",
        origin="http://127.0.0.1:9999",
        referer=None,
        sec_fetch_site="same-site",
        allowed_ports={8766},
    )


def test_local_post_allows_same_site_allowed_dev_port():
    assert is_trusted_local_request(
        method="POST",
        origin="http://localhost:5173",
        referer=None,
        sec_fetch_site="same-site",
        allowed_ports={8766, 5173},
    )


def test_local_post_rejects_same_site_without_origin_or_referer():
    assert not is_trusted_local_request(
        method="POST",
        origin=None,
        referer=None,
        sec_fetch_site="same-site",
        allowed_ports={8766},
    )


def test_fastapi_rejects_cross_site_mutation():
    async def call_next(_request):
        return JSONResponse({"ok": True})

    request = SimpleNamespace(
        method="POST",
        headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
    )
    response = asyncio.run(reject_cross_site_mutations(request, call_next))

    assert response.status_code == 403


def test_fastapi_allows_same_origin_mutation():
    async def call_next(_request):
        return JSONResponse({"ok": True})

    request = SimpleNamespace(
        method="POST",
        headers={"origin": "http://127.0.0.1:8766", "sec-fetch-site": "same-origin"},
    )
    response = asyncio.run(reject_cross_site_mutations(request, call_next))

    assert response.status_code == 200
