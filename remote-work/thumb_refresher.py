"""

Event-driven thumbnail recovery with an optional manual backfill pass.

Scans videos whose thumbnail is empty, a dead external URL, or a local
/image_cache path whose file is missing on disk, and re-resolves them via
yt-dlp (through resolver.resolve_video_url), downloading the result into the
local image_cache.

Newly inserted videos trigger recovery immediately. A batch pass remains
available through the admin endpoint or by running this module directly:

    docker exec videohub-api python3 /app/backend/thumb_refresher.py

Per-video logic mirrors the lazy refresh in routers/videos.py (the /api/play
handler), without a periodic scanner.

"""

import asyncio

import logging

import os

logger = logging.getLogger("app")

MAX_PER_CYCLE = 50

PER_VIDEO_DELAY = 2.0

_manual_running = False


def _local_thumb_exists(thumb: str) -> bool:
    """True if a /image_cache/... thumbnail path has a real file on disk."""
    from proxy import IMAGE_CACHE_DIR
    if not thumb or not thumb.startswith("/image_cache/"):
        return False
    disk = thumb.replace("/image_cache", IMAGE_CACHE_DIR, 1)
    try:
        return os.path.isfile(disk) and os.path.getsize(disk) > 0
    except OSError:
        return False


async def _set_thumb(pool, vid: int, path: str) -> None:
    async with pool.acquire() as db:
        await db.execute(
            "UPDATE videos SET thumbnail=$1, updated_at=now() WHERE id=$2",
            path, vid
        )


async def _extract_keyframe(video_url: str, headers: dict = None, duration=None) -> str:
    """Extract a key frame from a video stream using ffmpeg.

    Seeks to 15 seconds to skip black intro frames.
    Returns a local /image_cache/... path on success, empty string on failure.
    """
    import tempfile, os, hashlib, subprocess, shutil
    from proxy import IMAGE_CACHE_DIR

    # Slow seek (-ss after -i) works with HLS and accurately targets 15s.
    seek = 15.0

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="_kf_", suffix=".jpg")
    os.close(tmp_fd)

    # Prefer resolved headers (Referer/UA) - CDN streams often require the
    # source-site Referer, not the CDN host.
    if headers:
        header_blob = "\r\n".join(f"{k}: {v}" for k, v in headers.items())
        input_opts = ["-headers", header_blob]
    else:
        input_opts = ["-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"]

    # Accurate seek after input works with HLS and avoids black intro frames.
    cmd = [
        "ffmpeg", "-y",
        *input_opts,
        "-i", video_url,
        "-ss", str(seek),
        "-frames:v", "1",
        "-update", "1",
        "-q:v", "2",
        "-t", "20",
        tmp_path,
    ]

    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if proc.returncode != 0:
            logger.debug(f"keyframe: ffmpeg failed for {video_url[:60]}: {proc.stderr.decode()[:300]}")
            return ""

        if not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) < 500:
            return ""

        h = hashlib.md5(video_url.encode()).hexdigest()
        sub = h[:2]
        dest_dir = os.path.join(IMAGE_CACHE_DIR, sub)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{h}.jpg")
        shutil.move(tmp_path, dest)

        logger.info(f"keyframe: extracted from {video_url[:60]} -> {dest}")
        return f"/image_cache/{sub}/{h}.jpg"

    except subprocess.TimeoutExpired:
        logger.debug(f"keyframe: timeout for {video_url[:60]}")
        return ""
    except Exception as e:
        logger.debug(f"keyframe: error for {video_url[:60]}: {e}")
        return ""
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


async def _refresh_one(pool, video) -> str:
    """Refresh a single video's thumbnail.

    Strategy:
      - Empty/NULL thumbnail (never got one at crawl time): resolve the source
        to a playable stream and extract a key frame directly. Re-resolving
        for a thumbnail that was never there is pointless.
      - http external thumbnail: download & localize it first (it may still be
        alive and is higher quality than a frame). If the download fails, fall
        straight through to keyframe extraction in the same cycle.
      - local /image_cache/ path but file missing on disk: treat as empty,
        extract a key frame.

    Returns one of: 'updated', 'skipped', 'failed'.
    """
    from resolver import resolve_video_url
    from spiders._common import _download_thumb_to_local

    vid = video["id"]
    src = video["url"] or ""
    cur = video["thumbnail"] or ""

    # 1. External http thumbnail: prefer it - download & localize.
    if cur.startswith("http"):
        try:
            local = await _download_thumb_to_local(cur, source_url=src)
            if local:
                await _set_thumb(pool, vid, local)
                return "updated"
        except Exception as e:
            logger.debug(f"thumb_refresh: localize-existing failed for {vid}: {e}")
        # Download failed - fall through to keyframe extraction below.

    # 2. Empty, local file missing, or external download failed -> keyframe.
    try:
        resolved = await resolve_video_url(src, force=True)
    except Exception as e:
        logger.warning(f"thumb_refresh: resolve failed for {vid}: {e}")
        return "failed"

    video_stream = (resolved or {}).get("video_url", "")
    if not video_stream:
        logger.debug(f"thumb_refresh: no video_url for {vid} ({src[:60]})")
        return "failed"

    headers = (resolved or {}).get("headers") or None
    duration = video.get("duration")
    try:
        kf_path = await _extract_keyframe(video_stream, headers=headers, duration=duration)
    except Exception as e:
        logger.debug(f"thumb_refresh: keyframe error for {vid}: {e}")
        return "failed"

    if not kf_path:
        return "failed"

    await _set_thumb(pool, vid, kf_path)
    return "updated"


async def _gather_candidates(pool) -> list:
    """Collect videos needing a thumbnail refresh, capped at MAX_PER_CYCLE.

    Three categories:
      - empty / NULL thumbnail           (always candidates)
      - external http thumbnail          (may be dead -> re-localize/resolve)
      - local /image_cache thumb whose file is missing on disk
    Empties first, then oldest by updated_at.
    """
    async with pool.acquire() as db:
        rows_a = await db.fetch(
            """
            SELECT id, url, thumbnail, duration FROM videos
            WHERE thumbnail IS NULL OR thumbnail = '' OR thumbnail LIKE 'http%'
            ORDER BY (thumbnail = '') DESC, updated_at ASC
            LIMIT $1
            """,
            MAX_PER_CYCLE,
        )
        # Local thumbs: fetch a batch, then keep only those missing on disk.
        rows_b = await db.fetch(
            """
            SELECT id, url, thumbnail, duration FROM videos
            WHERE thumbnail LIKE '/image_cache/%'
            ORDER BY updated_at ASC
            LIMIT $1
            """,
            MAX_PER_CYCLE,
        )

    seen = set()
    candidates = []
    for row in list(rows_a) + list(rows_b):
        vid = row["id"]
        if vid in seen:
            continue
        seen.add(vid)
        thumb = row["thumbnail"] or ""
        # Local thumb that still exists on disk is healthy - skip.
        if thumb.startswith("/image_cache/") and _local_thumb_exists(thumb):
            continue
        candidates.append(row)
        if len(candidates) >= MAX_PER_CYCLE:
            break
    return candidates


async def _refresh_cycle() -> dict:
    """Run one backfill pass. Safe to call concurrently with the loop."""
    from database import get_pool

    pool = await get_pool()
    candidates = await _gather_candidates(pool)
    stats = {"total": len(candidates), "updated": 0, "skipped": 0, "failed": 0}

    if not candidates:
        logger.info("thumb_refresh: no candidates needing refresh")
        return stats

    logger.info(f"thumb_refresh: {len(candidates)} candidates")

    for i, row in enumerate(candidates):
        vid = row["id"]
        src = (row["url"] or "")[:60]
        try:
            result = await _refresh_one(pool, row)
            stats[result] += 1
            logger.info(f"thumb_refresh [{i+1}/{len(candidates)}] id={vid} ({src}) -> {result}")
        except Exception as e:
            stats["failed"] += 1
            logger.warning(f"thumb_refresh [{i+1}/{len(candidates)}] id={vid} error: {e}")
        # Rate-limit: don't hammer source servers / yt-dlp.
        await asyncio.sleep(PER_VIDEO_DELAY)

    logger.info(
        f"thumb_refresh cycle done: {stats['updated']} updated, "
        f"{stats['skipped']} skipped, {stats['failed']} failed / {stats['total']} total"
    )
    return stats


async def trigger_manual_refresh() -> bool:
    """Kick off one refresh cycle in the background. Returns False if one is
    already running (caller may respond 409)."""
    global _manual_running
    if _manual_running:
        return False
    _manual_running = True

    async def _wrapped():
        global _manual_running
        try:
            await _refresh_cycle()
        except Exception as e:
            logger.error(f"thumb_refresh manual error: {e}", exc_info=True)
        finally:
            _manual_running = False

    asyncio.create_task(_wrapped())
    return True




_thumb_semaphore = asyncio.Semaphore(3)


async def _refresh_one_bounded(pool, video) -> None:
    """Wrapper bounding concurrent keyframe extractions triggered on insert."""
    async with _thumb_semaphore:
        try:
            await _refresh_one(pool, video)
        except Exception as e:
            logger.warning(f"triggered keyframe error: {e}")


async def trigger_keyframe_if_needed(pool, video) -> None:
    """Recover a freshly inserted video's thumbnail immediately.

    External thumbnails are localized first; recovery falls back to extracting
    the 15-second video frame only when localization fails.
    """
    try:
        thumb = video["thumbnail"] or ""
    except Exception:
        thumb = ""
    if thumb.startswith("/image_cache/"):
        return
    try:
        vid = video["id"]
    except Exception:
        vid = "?"
    try:
        asyncio.create_task(_refresh_one_bounded(pool, video))
        logger.info(f"thumb_refresh: triggered keyframe for new video id={vid}")
    except Exception as e:
        logger.warning(f"trigger_keyframe failed: {e}")


if __name__ == "__main__":
    import asyncio as _asyncio
    from database import init_db

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    async def _main():
        await init_db()
        await _refresh_cycle()

    _asyncio.run(_main())
