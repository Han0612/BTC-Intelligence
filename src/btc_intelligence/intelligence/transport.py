import asyncio
import json

import httpx

from ..collectors.binance import retry_after_seconds
from ..models import now_ms
from .safety import fetch_url


class FetchError(RuntimeError):
    def __init__(self, message, status="ERROR", retry_at=0, http_status=None):
        super().__init__(message)
        self.status = status
        self.retry_at = retry_at
        self.http_status = http_status


class Transport:
    def __init__(self, client, config):
        self.client = client
        self.config = config
        self.slots = asyncio.Semaphore(config.concurrency)

    async def get(self, url, headers=None, params=None):
        url = fetch_url(url)
        for attempt in range(self.config.retries):
            try:
                async with self.slots:
                    async with self.client.stream("GET",url,headers=headers,params=params,timeout=self.config.timeout) as response:
                        code = response.status_code
                        if code in {401,403,418,451}:
                            raise FetchError(f"HTTP {code}；拒绝访问，不绕过", "RESTRICTED",now_ms()+86400000,code)
                        if code == 429:
                            delay = retry_after_seconds(response.headers.get("retry-after"))
                            raise FetchError("HTTP 429；按 Retry-After 暂停该来源", "HTTP_ERROR",now_ms()+int(delay*1000),code)
                        if code == 304:
                            return code,b"",dict(response.headers)
                        if 300 <= code < 400:
                            raise FetchError(f"HTTP {code} 重定向；未跟随，须先审查目标","HTTP_ERROR",http_status=code)
                        response.raise_for_status()
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            size += len(chunk)
                            if size > 3_000_000:
                                raise FetchError("响应超过 3 MB 限制")
                            chunks.append(chunk)
                        return code,b"".join(chunks),dict(response.headers)
            except FetchError:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 or attempt+1 == self.config.retries:
                    raise FetchError(f"HTTP {exc.response.status_code}","HTTP_ERROR",http_status=exc.response.status_code) from None
            except (httpx.HTTPError, OSError) as exc:
                if attempt+1 == self.config.retries:
                    # 不记录完整请求或 Authorization，避免泄露潜在凭据。
                    raise FetchError(f"{type(exc).__name__}：请求失败（已有限重试）","NETWORK_ERROR") from None
            await asyncio.sleep(min(2**attempt,8))

    async def json(self, url, params=None):
        _,body,_ = await self.get(url,params=params)
        try:
            return json.loads(body)
        except (ValueError,UnicodeError):
            raise FetchError("API 返回无效 JSON") from None
