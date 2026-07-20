"""Video CRUD + play + resolve endpoints."""
import logging
import os
import json
import time
import asyncio
import secrets
from fastapi import APIRouter, Query, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, JSONResponse
from database import get_pool, _d
from schemas import VideoCreate, VideoUpdate, VideoOut
from metadata import fetch_metadata
from resolver import resolve_video_url, get_resolve_stats
from proxy import proxy_stream, proxy_hls, proxy_image, _get_cached
from .state import ads_enabled, m3u8_cache, M3U8_CACHE_TTL, play_result_cache, PLAY_RESULT_CACHE_TTL, site_name_cache
from urllib.parse import quote

logger = logging.getLogger("app")
router = APIRouter()


def _has_expired_thumb_auth(url: str) -> bool:
    """Check if thumbnail URL has an expired auth token (e.g. expose.eisees.com ?auth=<ts>-<sig>)."""
    if "auth=" not in url:
        return False
    try:
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(url).query)
        auth_val = qs.get("auth", [""])[0]
        if "-" in auth_val:
            ts = int(auth_val.split("-")[0])
            if ts < time.time() - 12 * 3600:
                return True
    except Exception:
        pass

def _is_placeholder_thumb(url: str) -> bool:
    """Detect common placeholder/default/no-image thumbnails by URL pattern."""
    if not url:
        return False
    u = url.lower()
    keywords = ['placeholder', 'no-image', 'noimage', 'no_image', 'default-thumb',
                'default_thumb', 'defaultthumb', 'no-thumb', 'nothumb', 'no_thumb',
                'no-photo', 'nophoto', 'no_photo', 'blank', 'dummy',
                'coming-soon', 'coming_soon', 'image-not-found',
                'notfound', 'not-found', 'not_found']
    return any(kw in u for kw in keywords)


def _is_placeholder_thumb(url: str) -> bool:
    """Detect common placeholder/default/no-image thumbnails."""
    if not url:
        return False
    u = url.lower()
    keywords = ['placeholder', 'no-image', 'noimage', 'no_image', 'default-thumb',
                'default_thumb', 'defaultthumb', 'no-thumb', 'nothumb', 'no_thumb',
                'no-photo', 'nophoto', 'no_photo', 'blank', 'dummy',
                'coming-soon', 'coming_soon', 'image-not-found',
                'notfound', 'not-found', 'not_found']
    return any(kw in u for kw in keywords)

    return False


async def require_admin(request: Request):
    """FastAPI dependency: enforce admin token (HttpOnly cookie or Bearer header)"""
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    if not admin_token:
        raise HTTPException(503, "Server admin key not configured")
    token = request.cookies.get("vh_admin_token", "")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if secrets.compare_digest(token, admin_token):
        return True
    raise HTTPException(401, "Unauthorized")


def _is_direct_video_url(url: str) -> bool:
    """Check if URL points to direct video stream (not HTML page)"""
    if not url or not url.startswith("http"):
        return False
    path = url.lower().split("?")[0].split("#")[0]
    video_exts = (".mp4", ".webm", ".m3u8", ".mkv", ".avi", ".mov", ".flv", ".ts", ".mpd")
    return any(path.endswith(e) for e in video_exts)


async def _normalize_site_name(domain: str) -> str:
    """Map a domain like 'eporner.com' to the sites.name like 'EPORNER'."""
    if not domain:
        return domain
    low = domain.lower()
    if low in site_name_cache:
        return site_name_cache[low]
    pool = await get_pool()
    try:
        rows = await pool.fetch("SELECT name, url FROM sites")
        from urllib.parse import urlparse
        for row in rows:
            site_domain = urlparse(row["url"]).netloc.lower()
            site_name_cache[site_domain] = row["name"]
        if low in site_name_cache:
            return site_name_cache[low]
    except Exception:
        pass
    return domain.split(".")[0].upper()


# -- Video management --------------------------------------

@router.get("/api/videos/site-names")
async def video_site_names():
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT DISTINCT site_name FROM videos WHERE site_name IS NOT NULL AND site_name != '' ORDER BY site_name")
    return [r['site_name'] for r in rows]


@router.get("/api/videos")
async def list_videos(
    page: int = 1, size: int = 24,
    sort: str = "newest",
    category: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    vr_only: bool = False,
    site_name: str | None = None,
    site_id: int | None = None,
    status: str = "published",
):
    offset = (page - 1) * size
    pool = await get_pool()
    where, params = ["v.status = $1", "v.fail_count < 5"], [status]
    idx = 2
    if category:
        where.append(f"v.category ILIKE ${idx}"); params.append(category); idx += 1
    if tag:
        where.append(f"v.tags::jsonb @> ${idx}::jsonb"); params.append(json.dumps([tag])); idx += 1
    if search:
        where.append(f"(v.search_vector @@ plainto_tsquery('simple', ${idx}) OR v.title ILIKE ${idx+1})")
        params.append(search); params.append(f"%{search}%"); idx += 2
    if vr_only:
        where.append("v.vr_mode = 'equirectangular'")
    if site_name:
        where.append(f"v.site_name ILIKE ${idx}"); params.append(f"%{site_name}%"); idx += 1
    if site_id:
        where.append(f"v.site_id = ${idx}"); params.append(site_id); idx += 1

    if sort == "relevance" and search:
        search_idx = params.index(search) + 1
        order = f"ts_rank(v.search_vector, plainto_tsquery('simple', ${search_idx})) DESC"
    else:
        # Time-based filters for weekly/monthly top
        if sort == "weekly":
            where.append("v.created_at >= NOW() - INTERVAL '7 days'")
            order = "v.views DESC"
        elif sort == "monthly":
            where.append("v.created_at >= NOW() - INTERVAL '30 days'")
            order = "v.views DESC"
        else:
            order = {
                "newest": "v.created_at DESC",
                "most_viewed": "v.views DESC",
                "top_rated": "v.likes DESC",
                "likes": "v.likes DESC",
                "favorites": "v.favorites DESC",
                "longest": "CASE WHEN v.duration ~ '^[0-9]+:[0-9]{2}:[0-9]{2}$' THEN (SPLIT_PART(v.duration,':',1)::int * 3600 + SPLIT_PART(v.duration,':',2)::int * 60 + SPLIT_PART(v.duration,':',3)::int) WHEN v.duration ~ '^[0-9]+:[0-9]{2}$' THEN (SPLIT_PART(v.duration,':',1)::int * 60 + SPLIT_PART(v.duration,':',2)::int) ELSE 0 END DESC",
                "shortest": "CASE WHEN v.duration ~ '^[0-9]+:[0-9]{2}:[0-9]{2}$' THEN (SPLIT_PART(v.duration,':',1)::int * 3600 + SPLIT_PART(v.duration,':',2)::int * 60 + SPLIT_PART(v.duration,':',3)::int) WHEN v.duration ~ '^[0-9]+:[0-9]{2}$' THEN (SPLIT_PART(v.duration,':',1)::int * 60 + SPLIT_PART(v.duration,':',2)::int) ELSE 999999 END ASC",
            }.get(sort, "v.created_at DESC")
    async with pool.acquire() as db:
        rows = await db.fetch(
            f"SELECT v.*, u.channel_name as uploader_name, u.channel_slug as uploader_slug, u.is_verified as uploader_verified FROM videos v LEFT JOIN users u ON v.uploader_id = u.id WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ${idx} OFFSET ${idx+1}",
            *params, size, offset
        )
        # fallback to ILIKE fuzzy search when full-text results < 3 and no pagination
        if search and len(rows) < min(size, 3) and page == 1:
            ilike_where = ["v.status = $1", "v.fail_count < 5"]
            ilike_params = [status]
            ilike_idx = 2
            if category:
                ilike_where.append(f"v.category = ${ilike_idx}"); ilike_params.append(category); ilike_idx += 1
            ilike_where.append(f"(v.title ILIKE ${ilike_idx} OR v.description ILIKE ${ilike_idx})")
            ilike_params.append(f"%{search}%"); ilike_idx += 1
            if vr_only:
                ilike_where.append("v.vr_mode = 'equirectangular'")
            rows2 = await db.fetch(
                f"SELECT v.*, u.channel_name as uploader_name, u.channel_slug as uploader_slug, u.is_verified as uploader_verified FROM videos v LEFT JOIN users u ON v.uploader_id = u.id WHERE {' AND '.join(ilike_where)} ORDER BY v.created_at DESC LIMIT ${ilike_idx} OFFSET ${ilike_idx+1}",
                *ilike_params, size, offset
            )
            seen_ids = {r['id'] for r in rows}
            for r in rows2:
                if r['id'] not in seen_ids:
                    rows.append(r)
                    seen_ids.add(r['id'])
    # Count total for pagination (same WHERE conditions)
    count_where = list(where)  # copy
    count_params = list(params)  # copy
    count_idx = len(count_params) + 1
    total = 0
    async with pool.acquire() as db:
        total = await db.fetchval(
            f"SELECT COUNT(*) FROM videos v WHERE {' AND '.join(count_where)}",
            *count_params
        )
    return {"items": [_d(r) for r in rows], "total": total, "page": page, "size": size}


@router.get("/api/videos/count")
async def count_videos(category: str | None = None, search: str | None = None, vr_only: bool = False, status: str = "published"):
    pool = await get_pool()
    where, params = ["status = $1"], [status]
    idx = 2
    if category:
        where.append(f"category = ${idx}"); params.append(category); idx += 1
    if search:
        where.append(f"(search_vector @@ plainto_tsquery('simple', ${idx}) OR title ILIKE ${idx+1} OR description ILIKE ${idx+1})")
        params.append(search); params.append(f"%{search}%"); idx += 2
    if vr_only:
        where.append("vr_mode = 'equirectangular'")
    async with pool.acquire() as db:
        c = await db.fetchval(f"SELECT COUNT(*) FROM videos WHERE {' AND '.join(where)}", *params)
    return {"count": c}


@router.get("/api/videos/{video_id}", response_model=VideoOut)
async def get_video(video_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT v.*, u.channel_name as uploader_name, u.channel_slug as uploader_slug, u.is_verified as uploader_verified FROM videos v LEFT JOIN users u ON v.uploader_id = u.id WHERE v.id = $1", video_id)
    if not row:
        raise HTTPException(404, "Video not found")
    return _d(row)


@router.post("/api/videos", response_model=VideoOut)
async def add_video(data: VideoCreate, _auth=Depends(require_admin)):
    meta = await fetch_metadata(data.url)
    if not meta.get("site_name") and "/" in data.url:
        meta["site_name"] = await _normalize_site_name(data.url.split("/")[2])
    if data.category:
        meta["category"] = data.category
    if data.vr_mode != "auto":
        meta["vr_mode"] = data.vr_mode

    pool = await get_pool()
    try:
        async with pool.acquire() as db:
            _uid = await db.fetchval("SELECT id FROM users ORDER BY RANDOM() LIMIT 1")
            vid = await db.fetchval(
                """INSERT INTO videos (url, title, description, thumbnail, video_url, duration, site_name, vr_mode, category, tags, auto_fetched, status, site_id, uploader_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,1,$11,NULL,$12) RETURNING id""",
                data.url, meta.get("title",""), meta.get("description",""), meta.get("thumbnail",""),
                meta.get("video_url",""), meta.get("duration",""), meta.get("site_name",""),
                meta.get("vr_mode","auto"), meta.get("category",""),
                json.dumps(meta.get("tags",[]), ensure_ascii=False), data.status, _uid
            )
            row = await db.fetchrow("SELECT * FROM videos WHERE id = $1", vid)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "URL already exists")
        logger.error(f"Internal error: {e}", exc_info=True); raise HTTPException(500, "Internal server error")
    from thumb_refresher import trigger_keyframe_if_needed
    await trigger_keyframe_if_needed(pool, row)
    return _d(row)


@router.post("/api/videos/batch", response_model=dict)
async def add_videos_batch(urls: list[str], _auth=Depends(require_admin)):
    results = {"added": 0, "skipped": 0, "errors": []}
    pool = await get_pool()
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            meta = await fetch_metadata(url)
            if not meta.get("site_name") and "/" in url:
                meta["site_name"] = await _normalize_site_name(url.split("/")[2])
            async with pool.acquire() as db:
                _uid = await db.fetchval("SELECT id FROM users ORDER BY RANDOM() LIMIT 1")
                vid = await db.fetchval(
                    """INSERT INTO videos (url, title, description, thumbnail, video_url, duration, site_name, vr_mode, category, tags, auto_fetched, status, site_id, uploader_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,1,'published',NULL,$11) RETURNING id""",
                    url, meta["title"], meta["description"], meta["thumbnail"],
                    meta["video_url"], meta["duration"], meta["site_name"],
                    meta["vr_mode"], meta.get("category",""),
                    json.dumps(meta.get("tags",[]), ensure_ascii=False), _uid
                )
                row = await db.fetchrow("SELECT * FROM videos WHERE id = $1", vid)
            from thumb_refresher import trigger_keyframe_if_needed
            await trigger_keyframe_if_needed(pool, row)
            results["added"] += 1
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                results["skipped"] += 1
            else:
                logger.warning("bulk add video failed for %s: %s", url, e)
                results["errors"].append({"url": url, "error": "Failed to add video"})
    return results


@router.put("/api/videos/{video_id}")
async def update_video(video_id: int, data: VideoUpdate, _auth=Depends(require_admin)):
    pool = await get_pool()
    sets, vals = [], []
    idx = 1
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            sets.append(f"{k} = ${idx}"); vals.append(v); idx += 1
    if not sets:
        raise HTTPException(400, "No fields to update")
    sets.append(f"updated_at = now()")
    vals.append(video_id)
    async with pool.acquire() as db:
        await db.execute(f"UPDATE videos SET {', '.join(sets)} WHERE id = ${idx}", *vals)
    return {"ok": True}


@router.delete("/api/videos/{video_id}")
async def delete_video(video_id: int, _auth=Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("DELETE FROM videos WHERE id = $1", video_id)
    return {"ok": True}


@router.post("/api/videos/batch-delete")
async def batch_delete_videos(request: Request, _auth=Depends(require_admin)):
    body = await request.json()
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "No video IDs provided for deletion")
    pool = await get_pool()
    async with pool.acquire() as db:
        count = await db.fetchval("SELECT COUNT(*) FROM videos WHERE id = ANY($1::int[])", ids)
        await db.execute("DELETE FROM videos WHERE id = ANY($1::int[])", ids)
    return {"deleted": count}


@router.post("/api/videos/{video_id}/refetch")
async def refetch_metadata(video_id: int, _auth=Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT url, site_id FROM videos WHERE id = $1", video_id)
    if not row:
        raise HTTPException(404)
    meta = await fetch_metadata(row["url"])
    # Look up per-site title_clean rules
    site_title_clean = {}
    if row.get("site_id"):
        from backend.spiders._common import _get_site_config
        try:
            _, _, _, _, site_title_clean = await _get_site_config("", site_id=row["site_id"])
        except Exception:
            pass
    # Clean title to remove site name suffix
    from backend.spiders._common import clean_video_title
    meta["title"] = clean_video_title(meta.get("title", ""), meta.get("site_name", ""), site_title_clean)
    async with pool.acquire() as db:
        await db.execute(
            """UPDATE videos SET title=$1, description=$2, thumbnail=$3, duration=$4, site_name=$5, tags=$6, updated_at=now() WHERE id=$7""",
            meta["title"], meta["description"], meta["thumbnail"],
            meta["duration"], meta["site_name"],
            json.dumps(meta.get("tags",[]), ensure_ascii=False), video_id
        )
    return {"ok": True, "metadata": meta}


@router.post("/api/admin/thumbnails/refresh")
async def admin_refresh_thumbnails(_auth=Depends(require_admin)):
    """Kick off a background batch refresh of empty/dead/missing thumbnails."""
    from thumb_refresher import trigger_manual_refresh
    if not await trigger_manual_refresh():
        raise HTTPException(409, "A thumbnail refresh is already running")
    return {"ok": True, "message": "refresh started"}


@router.post("/api/videos/{video_id}/view")
async def increment_view(video_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE videos SET views = views + 1 WHERE id = $1", video_id)
    return {"ok": True}


# -- Like / Favorite reactions (public, localStorage prevents spam) --

@router.post("/api/videos/{video_id}/like")
async def like_video(video_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE videos SET likes = likes + 1 WHERE id = $1", video_id)
        row = await db.fetchrow("SELECT likes FROM videos WHERE id = $1", video_id)
    return {"likes": row["likes"] if row else 0}

@router.post("/api/videos/{video_id}/unlike")
async def unlike_video(video_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE videos SET likes = GREATEST(0, likes - 1) WHERE id = $1", video_id)
        row = await db.fetchrow("SELECT likes FROM videos WHERE id = $1", video_id)
    return {"likes": row["likes"] if row else 0}

@router.post("/api/videos/{video_id}/favorite")
async def favorite_video(video_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE videos SET favorites = favorites + 1 WHERE id = $1", video_id)
        row = await db.fetchrow("SELECT favorites FROM videos WHERE id = $1", video_id)
    return {"favorites": row["favorites"] if row else 0}

@router.post("/api/videos/{video_id}/unfavorite")
async def unfavorite_video(video_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE videos SET favorites = GREATEST(0, favorites - 1) WHERE id = $1", video_id)
        row = await db.fetchrow("SELECT favorites FROM videos WHERE id = $1", video_id)
    return {"favorites": row["favorites"] if row else 0}


# -- Play: real-time resolve + proxy --------------------------

@router.api_route("/api/play/{video_id}", methods=["GET", "HEAD"])
async def play_video(video_id: int, request: Request):
    t0 = time.time()

    # check m3u8 in-memory cache
    cached_entry = m3u8_cache.get(video_id)
    if cached_entry and cached_entry[0] > time.time():
        _, m3u8_content, ct = cached_entry
        headers = {"Cache-Control": "no-cache", "X-Cache": "HIT-MEM"}
        return Response(content=m3u8_content, media_type=ct, headers=headers)

    # check play result cache (MP4 etc - avoid re-resolve within 5min)
    pr_entry = play_result_cache.get(video_id)
    if pr_entry and pr_entry[0] > time.time():
        return JSONResponse(pr_entry[1], headers={"X-Cache": "HIT-PLAY"})

    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT v.*, u.channel_name as uploader_name, u.channel_slug as uploader_slug, u.is_verified as uploader_verified FROM videos v LEFT JOIN users u ON v.uploader_id = u.id WHERE v.id = $1", video_id)
    if not row:
        raise HTTPException(404, "Video not found")

    video = _d(row)
    source_url = video["url"]
    fallback_url = video["video_url"]

    # 1. disk cache
    if fallback_url:
        cached = _get_cached(fallback_url)
        if cached:
            return FileResponse(cached, media_type="video/mp4",
                headers={"X-Cache": "HIT-DISK", "X-Proxy-Time": f"{(time.time()-t0)*1000:.0f}ms"})

    # 2. real-time resolve
    needs_force = any(d in source_url for d in ("91porna", "91porny", "91porn.plus"))
    resolved = await resolve_video_url(source_url, force=needs_force)
    video_url = resolved.get("video_url", "")
    resolve_method = resolved.get("method", "unknown")

    # Update thumbnail if resolve returns one and current is missing/junk
    resolved_thumb = resolved.get("thumbnail", "")
    current_thumb = video.get("thumbnail", "")
    _thumb_is_junk = (
        not current_thumb
        or current_thumb.startswith("data:")
        or current_thumb.endswith(".svg")
        or (current_thumb.startswith("http") and _has_expired_thumb_auth(current_thumb))
        or (current_thumb.startswith("http") and _is_placeholder_thumb(current_thumb))
    )
    if resolved_thumb and resolved_thumb.startswith("http") and _thumb_is_junk:
        try:
            from spiders._common import _download_thumb_to_local
            _lt = await _download_thumb_to_local(resolved_thumb, source_url=source_url)
            if _lt:
                async with pool.acquire() as db:
                    await db.execute("UPDATE videos SET thumbnail=$1 WHERE id=$2", _lt, video_id)
                logger.info(f"Video {video_id} thumbnail localized: {_lt}")
            elif resolved_thumb != current_thumb:
                # At least save the fresh remote URL (proxy will cache on first view)
                async with pool.acquire() as db:
                    await db.execute("UPDATE videos SET thumbnail=$1 WHERE id=$2", resolved_thumb, video_id)
                logger.info(f"Video {video_id} thumbnail updated to fresh remote URL")
        except Exception as e:
            logger.debug(f"Thumbnail update skip for {video_id}: {e}")

    # 2b. If thumb is junk/missing/expired, extract a key frame from the resolved video
    _kf_needed = _thumb_is_junk
    # Also check if current thumb is a local path but file is missing
    if not _kf_needed and current_thumb and current_thumb.startswith("/image_cache/"):
        from thumb_refresher import _local_thumb_exists
        _kf_needed = not _local_thumb_exists(current_thumb)
    # Also check if external thumb download above failed (still http after attempt)
    if not _kf_needed and current_thumb.startswith("http") and _thumb_is_junk:
        _kf_needed = True
    if _kf_needed and video_url:
        try:
            from thumb_refresher import _extract_keyframe
            _kf_headers = resolved.get("headers") or None
            _kf_duration = video.get("duration")
            kf = await _extract_keyframe(video_url, headers=_kf_headers, duration=_kf_duration)
            if kf:
                async with pool.acquire() as db:
                    await db.execute("UPDATE videos SET thumbnail=$1 WHERE id=$2", kf, video_id)
                logger.info(f"Video {video_id} keyframe extracted: {kf}")
        except Exception as e:
            logger.debug(f"Keyframe extraction skip for {video_id}: {e}")

    # 3. proxy passthrough
    if video_url and _is_direct_video_url(video_url):
        if resolve_method in ("ytdlp", "meta") and video_url != fallback_url:
            async with pool.acquire() as db:
                await db.execute("UPDATE videos SET video_url=$1, fail_count=0, updated_at=now() WHERE id=$2", video_url, video_id)

        cached = _get_cached(video_url)
        if cached:
            return FileResponse(cached, media_type="video/mp4",
                headers={"X-Cache": "HIT-DISK", "X-Resolve": resolve_method, "X-Proxy-Time": f"{(time.time()-t0)*1000:.0f}ms"})

        if ".m3u8" in video_url.lower():
            for attempt in range(5):
                hls_resp = await proxy_hls(request, video_url, source_url)
                if hls_resp.status_code == 200:
                    body = hls_resp.body if hasattr(hls_resp, 'body') else b''
                    if body.startswith(b'#EXTM3U'):
                        ct = hls_resp.media_type or 'application/vnd.apple.mpegurl'
                        m3u8_cache[video_id] = (time.time() + M3U8_CACHE_TTL, body.decode('utf-8', errors='replace'), ct)
                        return hls_resp
                    elif attempt < 4:
                        logger.warning(f"m3u8 decode attempt {attempt+1} returned 200 but no EXTM3U, re-resolving...")
                        await asyncio.sleep(0.5)
                        fresh = await resolve_video_url(source_url, force=True)
                        video_url = fresh.get("video_url", video_url)
                        continue
                elif hls_resp.status_code == 502 and attempt < 4:
                    logger.warning(f"m3u8 decode attempt {attempt+1} returned 502, re-resolving (CDN node change)...")
                    await asyncio.sleep(0.5)
                    fresh = await resolve_video_url(source_url, force=True)
                    video_url = fresh.get("video_url", video_url)
                    continue
                else:
                    break
            return hls_resp

        # MP4/WebM etc.
        proxy_url = f"/api/proxy/stream?url={quote(video_url, safe='')}&source={quote(source_url, safe='')}"
        vid_format = resolved.get('format', '') or ('hls' if '.m3u8' in video_url else 'mp4')
        result = {
            "video_url": proxy_url,
            "original_url": video_url,
            "format": vid_format,
            "method": resolve_method,
            "page_url": source_url,
        }
        play_result_cache[video_id] = (time.time() + PLAY_RESULT_CACHE_TTL, result)
        return JSONResponse(result)

    # 4. not direct video link
    if video_url:
        result = {
            "video_url": video_url,
            "method": resolve_method,
            "page_url": source_url,
            "note": "not_direct_video"
        }
        play_result_cache[video_id] = (time.time() + PLAY_RESULT_CACHE_TTL, result)
        return JSONResponse(result)

    # 5. fallback
    if fallback_url:
        try:
            return await proxy_stream(request, fallback_url, source_url)
        except Exception:
            pass

    # Dead-link marking: verify source page is actually gone
    source_gone = False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            check = await client.head(source_url, headers={"User-Agent": "Mozilla/5.0"})
            if check.status_code in (404, 410, 451):
                source_gone = True
    except Exception:
        pass

    # Increment fail_count on every play failure
    FAIL_THRESHOLD = 5
    pool2 = await get_pool()
    async with pool2.acquire() as db:
        new_fail = await db.fetchval(
            "UPDATE videos SET fail_count = fail_count + 1, updated_at = now() WHERE id = $1 RETURNING fail_count",
            video_id
        )
        logger.info(f"Video {video_id} play failed, fail_count now {new_fail}")

    if source_gone:
        logger.warning(f"Video {video_id} source returned {check.status_code}, fail_count={new_fail}/{FAIL_THRESHOLD} (grace period, no immediate delete)")
    elif new_fail and new_fail >= FAIL_THRESHOLD:
        play_result_cache.pop(video_id, None)
        m3u8_cache.pop(video_id, None)
        pool3 = await get_pool()
        async with pool3.acquire() as db:
            await db.execute("DELETE FROM videos WHERE id=$1", video_id)
        logger.warning(f"Video {video_id} auto-removed: fail_count reached {new_fail}")
    else:
        logger.info(f"Video {video_id} resolve failed but source still reachable, keeping (fail={new_fail})")

    raise HTTPException(502, f"video resolve failed (tried: {resolve_method})")


@router.api_route("/api/resolve", methods=["GET", "HEAD"])
async def resolve_url(url: str, force: bool = False):
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL")
    pool = await get_pool()
    async with pool.acquire() as db:
        exists = await db.fetchval("SELECT 1 FROM videos WHERE url = $1 AND status='published'", url)
    if not exists:
        raise HTTPException(403, "URL not in allowed resolve scope")
    result = await resolve_video_url(url, force=force)
    if result["method"] == "failed":
        raise HTTPException(422, "Cannot resolve this video URL")
    return result


@router.post("/api/error-report")
async def error_report(request: Request):
    import logging
    logger = logging.getLogger("videohub.frontend_error")
    try:
        body = await request.json()
        logger.warning(f"FE_ERR page={body.get('page')} line={body.get('line')} msg={str(body.get('msg',''))[:200]} href={str(body.get('href',''))[:100]}")
    except:
        pass
    return {"ok": True}
