import logging
from types import TracebackType
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


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
