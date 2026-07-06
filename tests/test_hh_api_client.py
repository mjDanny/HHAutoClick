import httpx
import pytest

from app.core.config import Settings
from app.hh.api_client import HHApiClient, HHApiError


def make_response(
    status_code: int,
    *,
    json: dict | None = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://api.hh.ru/vacancies?text=Python&per_page=1")
    if json is not None:
        return httpx.Response(status_code, json=json, headers=headers, request=request)
    return httpx.Response(status_code, text=text or "", headers=headers, request=request)


def test_hh_api_error_detects_ddos_guard_forbidden_with_body_request_id() -> None:
    response = make_response(
        403,
        json={
            "errors": [{"type": "forbidden"}],
            "request_id": "17833656995003147df8bc929ab51007",
        },
        headers={"server": "ddos-guard"},
    )

    error = HHApiError.from_response(response)

    assert error.status_code == 403
    assert error.server == "ddos-guard"
    assert error.request_id == "17833656995003147df8bc929ab51007"
    assert (
        error.message
        == "hh API returned 403 forbidden from ddos-guard. "
        "Search cannot continue from this network/environment. "
        "request_id=17833656995003147df8bc929ab51007"
    )


def test_hh_api_error_detects_forbidden_body_without_ddos_guard_header() -> None:
    response = make_response(
        400,
        json={"errors": [{"type": "forbidden"}], "request_id": "body-request-id"},
    )

    error = HHApiError.from_response(response)

    assert error.message == (
        "hh API returned 403 forbidden. "
        "Search cannot continue from this network/environment. "
        "request_id=body-request-id"
    )


def test_hh_api_error_prefers_request_id_header() -> None:
    response = make_response(
        403,
        json={"errors": [{"type": "forbidden"}], "request_id": "body-request-id"},
        headers={"x-request-id": "header-request-id"},
    )

    error = HHApiError.from_response(response)

    assert error.request_id == "header-request-id"
    assert error.message.endswith("request_id=header-request-id")


def test_hh_api_error_400_includes_safe_body_preview() -> None:
    response = make_response(400, text='{"errors":[{"type":"bad_argument"}]}')

    error = HHApiError.from_response(response)

    assert error.status_code == 400
    assert error.message == (
        'hh API returned 400 bad request: {"errors":[{"type":"bad_argument"}]}'
    )
    assert error.response_body == '{"errors":[{"type":"bad_argument"}]}'


async def test_hh_api_client_raises_friendly_error_from_http_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"errors": [{"type": "forbidden"}], "request_id": "mock-request-id"},
            headers={"server": "ddos-guard"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://api.hh.ru",
    ) as http_client:
        client = HHApiClient(Settings(), client=http_client)

        with pytest.raises(HHApiError) as exc:
            await client.search_vacancies({"text": "Python", "per_page": 1})

    assert "hh API returned 403 forbidden from ddos-guard" in exc.value.message
    assert exc.value.request_id == "mock-request-id"
