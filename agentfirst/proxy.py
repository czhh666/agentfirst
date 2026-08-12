import asyncio

import httpx

TIMEOUT = httpx.Timeout(30.0, connect=10.0)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_EXC = (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError)


class Upstream:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def call(self, method: str, url: str, query: dict, body: bytes | None,
                   auth_header: str | None, auth_value: str | None,
                   retries: int = 2, retry_delay: float = 0.3) -> tuple[int, dict, bytes]:
        last_exc = None
        for attempt in range(retries + 1):
            try:
                status, headers, content = await self._call_once(
                    method, url, query, body, auth_header, auth_value)
                if status not in RETRYABLE_STATUS or attempt >= retries:
                    return status, headers, content
            except RETRYABLE_EXC as exc:
                last_exc = exc
                if attempt >= retries:
                    raise last_exc
            await asyncio.sleep(retry_delay * (2 ** attempt))
        raise last_exc

    async def _call_once(self, method, url, query, body,
                         auth_header, auth_value) -> tuple[int, dict, bytes]:
        headers = {}
        if auth_header and auth_value:
            headers[auth_header] = auth_value
        content = body
        if content and not headers.get("content-type"):
            headers["content-type"] = "application/json"
        response = await self.client.request(
            method, url, params=query or None, content=content,
            headers=headers or None, timeout=TIMEOUT,
        )
        return response.status_code, dict(response.headers), response.content
