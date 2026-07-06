import logging
from json import JSONDecodeError
from types import TracebackType
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)
BODY_PREVIEW_LIMIT = 500


class HHApiError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int | None,
        message: str,
        response_body: str | None = None,
        request_id: str | None = None,
        server: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.response_body = response_body
        self.request_id = request_id
        self.server = server
        self.url = url

    @classmethod
    def from_response(cls, response: httpx.Response) -> "HHApiError":
        body_preview = _safe_body_preview(response)
        body_json = _safe_json(response)
        request_id = _request_id(response, body_json)
        server = response.headers.get("server")
        status_code = response.status_code
        is_ddos_guard = server is not None and "ddos-guard" in server.lower()
        is_forbidden = (
            status_code == 403
            or is_ddos_guard
            or _has_forbidden_error(body_json)
        )

        if is_forbidden:
            source = " from ddos-guard" if is_ddos_guard else ""
            message = (
                f"hh API returned 403 forbidden{source}. "
                "Search cannot continue from this network/environment."
            )
        else:
            reason = response.reason_phrase.lower() or "error"
            message = f"hh API returned {status_code} {reason}"
            if body_preview:
                message = f"{message}: {body_preview}"

        if request_id:
            message = f"{message} request_id={request_id}"

        return cls(
            status_code=status_code,
            message=message,
            response_body=body_preview,
            request_id=request_id,
            server=server,
            url=_safe_url(response.request.url),
        )


HHApiForbiddenError = HHApiError


def _safe_body_preview(response: httpx.Response) -> str | None:
    text = response.text.strip()
    if not text:
        return None
    return text[:BODY_PREVIEW_LIMIT]


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except (JSONDecodeError, ValueError):
        return None


def _request_id(response: httpx.Response, body_json: Any) -> str | None:
    header_request_id = response.headers.get("x-request-id")
    if header_request_id:
        return header_request_id
    if isinstance(body_json, dict):
        value = body_json.get("request_id")
        if isinstance(value, str):
            return value
    return None


def _has_forbidden_error(body_json: Any) -> bool:
    if not isinstance(body_json, dict):
        return False
    errors = body_json.get("errors")
    if not isinstance(errors, list):
        return False
    return any(isinstance(error, dict) and error.get("type") == "forbidden" for error in errors)


def _safe_url(url: httpx.URL) -> str:
    parts = urlsplit(str(url))
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))


class HHApiClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owned_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HHApiClient":
        if self._client is None:
            self._owned_client = httpx.AsyncClient(
                base_url=str(self._settings.hh_base_url).rstrip("/"),
                timeout=20,
            )
            self._client = self._owned_client
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._owned_client:
            await self._owned_client.aclose()
            self._owned_client = None
            self._client = None

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": self._settings.hh_user_agent}
        if self._settings.hh_access_token:
            headers["Authorization"] = f"Bearer {self._settings.hh_access_token}"
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        base_url = str(self._settings.hh_base_url).rstrip("/")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url=base_url, timeout=20)
        try:
            response = await client.request(method, path, headers=self._headers(), **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            error = HHApiError.from_response(exc.response)
            logger.warning("hh.ru API request failed: %s %s: %s", method, path, error.message)
            raise error from exc
        except httpx.HTTPError:
            logger.exception("hh.ru API request failed: %s %s", method, path)
            raise
        finally:
            if owns_client:
                await client.aclose()

    async def search_vacancies(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request("GET", "/vacancies", params=params)

    async def get_vacancy(self, vacancy_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/vacancies/{vacancy_id}")
