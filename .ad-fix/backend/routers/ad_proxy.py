"""Ad proxy router - fetches external ad resources via first-party path."""
import logging
import re
import httpx
from fastapi import APIRouter, Request, Response, HTTPException

logger = logging.getLogger("ad_proxy")
router = APIRouter()

# Shared client for connection pool reuse
_shared_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=15, follow_redirects=True)
    return _shared_client


@router.get("/adp/{domain}/{path:path}")
async def ad_proxy(domain: str, path: str, request: Request):
    """Proxy external ad resources via first-party path to evade browser ad blockers."""
    if not re.match(r"^[a-z0-9][a-z0-9.-]+\.[a-z]+$", domain, re.I):
        raise HTTPException(status_code=400, detail="Invalid domain")

    url = "https://" + domain + "/" + path
    qs = request.url.query
    if qs:
        url += "?" + qs

    headers = {
        "User-Agent": request.headers.get("User-Agent", "Mozilla/5.0"),
        "Referer": "https://" + domain + "/",
        "Accept": request.headers.get("Accept", "*/*"),
        "Accept-Language": request.headers.get("Accept-Language", "en-US,en;q=0.9"),
    }

    try:
        client = _get_client()
        resp = await client.get(url, headers=headers)

        content_type = resp.headers.get("content-type", "application/octet-stream")
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot connect to upstream")
    except Exception as e:
        logger.error("Ad proxy error for %s: %s", domain, e)
        raise HTTPException(status_code=502, detail=str(e))
