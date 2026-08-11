import httpx

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class Upstream:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def call(self, method: str, url: str, query: dict, body: bytes | None,
                   auth_header: str | None, auth_value: str | None) -> tuple[int, dict, bytes]:
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
