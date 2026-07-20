"""Apple CMS standard API site crawler."""
import asyncio
import httpx
import json
import time
import logging
from urllib.parse import urlparse
from typing import Optional

from database import get_pool, _d
from ._common import (
    _cancellable_sleep, _get_site_config,
    _norm_site, classify_by_title, map_category, _get_random_uploader_id,
    _download_thumb_to_local,
)
from ._tasks import _active_tasks, _update_site_status

logger = logging.getLogger('spider.cms')

try:
    from crypto import cryptojs_decrypt
except ImportError:
    cryptojs_decrypt = None

async def crawl_apple_cms_site(

    site_url: str,

    *,

    site_type: str = "apple_cms",

    provide_url: str = "",

    url_template: str = "",

    max_pages: int = 10,

    max_videos: int = 200,

    category: str = "",

    crawl_delay: float = 2.0,

    item_delay: float = 0.3,

    site_id: int = 0,

) -> dict:

    """Crawl a site using Apple CMS standard API.

    Uses ac=videolist to get full data (thumbnail + m3u8) in a single pass,

    avoiding the old two-phase list->detail approach.

    """

    domain = urlparse(site_url).netloc.replace('www.', '')

    cms_config = {"site_type": site_type, "provide_url": provide_url, "url_template": url_template} if site_type == "apple_cms" else {}

    # Also try loading provide_url from DB if not provided

    if not cms_config.get("provide_url"):

        try:

            _pool = await get_pool()

            async with _pool.acquire() as _db:

                _row = await _db.fetchrow("SELECT provide_url, url_template FROM sites WHERE url LIKE $1", f"%{domain}%")

                if _row and _row.get("provide_url"):

                    cms_config["provide_url"] = _row["provide_url"]

                    if not cms_config.get("url_template") and _row.get("url_template"):

                        cms_config["url_template"] = _row["url_template"]

        except:

            pass

    if not cms_config:

        logger.error(f"[cms-spider] No apple_cms config for {domain}")

        return {"status": "error", "phase": "No config for this domain"}

    task_id = f"cms_crawl_{int(time.time()*1000)}"

    task = {

        "id": task_id, "url": site_url, "status": "running", "phase": "Initializing",

        "discovered": 0, "added": 0, "skipped": 0, "errors": 0,

        "current_page": "", "pages_crawled": 0,

        "updated_at": time.time(), "created_at": time.time(),

    }

    _active_tasks[task_id] = task

    pool = await get_pool()

    site_default, site_cat_map = '', {}

    try:

        site_id, site_default, site_cat_map, site_cfg_name, site_title_clean = await _get_site_config(site_url, site_id=site_id)

    except Exception:

        pass

    # Merge static config's category_map with DB one (static takes priority)

    static_cats = cms_config.get('category_map', {})

    if static_cats:

        site_cat_map = {**site_cat_map, **static_cats}

    if not site_default:

        site_default = cms_config.get('default_category', '')

    provide_url = cms_config['provide_url']

    url_template = cms_config['url_template']

    site_name = _norm_site(domain)

    all_records: list[dict] = []

    seen_ids: set[str] = set()

    ssl_ctx = ssl.create_default_context()

    ssl_ctx.check_hostname = False

    ssl_ctx.verify_mode = ssl.CERT_NONE

    async with httpx.AsyncClient(

        headers={"User-Agent": _get_ua()},

        follow_redirects=True, timeout=20, verify=ssl_ctx,

    ) as client:

        # Single phase: use ac=videolist to get full data per page

        for page in range(1, max_pages + 1):

            if task_id in _stop_signals:

                task["status"] = "stopped"

                await _update_site_status(task.get("url", ""), "stopped")

                _stop_signals.discard(task_id)

                break

            task["phase"] = f"Fetching page {page}"

            task["updated_at"] = time.time()

            task["pages_crawled"] = page

            try:

                r = await client.get(provide_url, params={"ac": "videolist", "pg": str(page)}, timeout=15)

                if r.status_code != 200:

                    logger.warning(f"[cms-spider] Page {page}: HTTP {r.status_code}")

                    continue

                data = r.json()

                video_list = data.get('list', [])

                if not video_list:

                    logger.info(f"[cms-spider] {domain} page {page}: empty list, stopping")

                    break

                pagecount = data.get('pagecount', 1)

                for v in video_list:

                    vid = str(v.get('vod_id', ''))

                    if vid and vid not in seen_ids:

                        seen_ids.add(vid)

                        # Parse play URL from vod_play_url format: "label$url\nlabel$url"

                        play_raw = v.get('vod_play_url', '')

                        m3u8_url = ''

                        for segment in play_raw.split('#') if '#' in play_raw else play_raw.split('\n'):

                            segment = segment.strip()

                            if '$' in segment:

                                _, url = segment.rsplit('$', 1)

                            else:

                                url = segment

                            if '.m3u8' in url:

                                m3u8_url = url.replace('\\/', '/').strip()

                                break

                            elif url.startswith('http') and not m3u8_url:

                                m3u8_url = url.replace('\\/', '/').strip()

                        # Tags from vod_class or vod_tag

                        raw_tags = v.get('vod_class', '') or v.get('vod_tag', '')

                        if isinstance(raw_tags, str):

                            tags = [t.strip() for t in raw_tags.replace(',', '\uff0c').split('\uff0c') if t.strip()][:10]

                        else:

                            tags = []

                        all_records.append({

                            'vod_id': vid,

                            'vod_name': v.get('vod_name', 'Untitled'),

                            'vod_pic': v.get('vod_pic', ''),

                            'vod_pic_thumb': v.get('vod_pic_thumb', ''),

                            'm3u8_url': m3u8_url,

                            'type_name': v.get('type_name', ''),

                            'tags': tags,

                            'duration': v.get('vod_duration', ''),

                        })

                task["discovered"] = len(all_records)

                task["updated_at"] = time.time()

                task["phase"] = f"Discovered {len(all_records)} videos (page {page}/{pagecount})"

                task["updated_at"] = time.time()

                if len(all_records) >= max_videos:

                    break

                if page >= pagecount:

                    break

                await _cancellable_sleep(crawl_delay, task_id)

            except Exception as e:

                logger.warning(f"[cms-spider] Page {page} error: {e}")

                task["errors"] += 1

                continue

    # Insert into DB

    all_records = all_records[:max_videos]

    task["phase"] = f"Inserting {len(all_records)} videos"

    task["updated_at"] = time.time()

    existing = set()

    urls = [url_template.format(vod_id=r['vod_id']) for r in all_records]

    if urls:

        async with pool.acquire() as db:

            rows = await db.fetch("SELECT url FROM videos WHERE url = ANY($1::text[])", urls)

            existing = {r['url'] for r in rows}

    for rec in all_records:
        if task_id in _stop_signals: break

        video_url = url_template.format(vod_id=rec['vod_id'])

        if video_url in existing:

            task["skipped"] += 1

            continue

        thumb = rec.get('vod_pic_thumb', '') or rec.get('vod_pic', '')

        cat_raw = rec.get('type_name', '')

        cat = map_category(cat_raw, rec.get('tags', []), '', rec.get('vod_name', ''), site_default=site_default, site_category_map=site_cat_map, duration=rec.get('duration', ''))

        if task_id in _stop_signals:

            task["status"] = "stopped"

            task["phase"] = "Manually stopped"

            task["updated_at"] = time.time()

            _stop_signals.discard(task_id)

            break


        # Download thumbnail to local image_cache
        _lt = ''
        thumb_url = rec.get('vod_pic_thumb', '') or rec.get('vod_pic', '')
        if thumb_url and thumb_url.startswith('http'):
            try:
                _lt = await _download_thumb_to_local(thumb_url, source_url=video_url)
            except Exception as e:
                logger.debug(f"Thumb download skip: {e}")
        if _lt:
            thumb = _lt

        try:

            async with pool.acquire() as db:

                # Extract tags from title for clustering
                try:
                    from ._common import clean_video_title
                    rec["vod_name"] = clean_video_title(rec.get("vod_name",""), site_name, site_title_clean)
                except Exception as _e:
                    logger.warning(f"clean title error: {_e}")
                try:
                    from ._common import extract_tags_from_title
                    _et = rec.get("tags", "[]")
                    if isinstance(_et, str): import json as _j; _et = _j.loads(_et)
                    rec["tags"] = extract_tags_from_title(rec.get("vod_name", ""), _et, 'equirectangular' if site_default == 'VR' else 'auto')
                except Exception as _e:
                    logger.warning(f"extract tags error: {_e}")

                _uid = await _get_random_uploader_id(db)
                vid = await db.fetchval(

                    """INSERT INTO videos (url, title, description, thumbnail, video_url, duration, site_name, vr_mode, category, tags, auto_fetched, status, site_id, uploader_id)

                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,1,'published',$11,$12) RETURNING id""",

                    video_url, (rec.get('vod_name', '') or 'Untitled')[:200], '', thumb,

                    rec.get('m3u8_url', ''), rec.get('duration', ''), site_name,

                    'equirectangular' if site_default == 'VR' else 'auto', cat,

                    json.dumps(rec.get('tags', []), ensure_ascii=False),

                    site_id,

                _uid,
                )
                if vid:

                    task["added"] += 1

                    task["updated_at"] = time.time()

                    row = {
                        "id": vid,
                        "url": video_url,
                        "thumbnail": thumb,
                        "duration": rec.get("duration", ""),
                    }
                    try:
                        from thumb_refresher import trigger_keyframe_if_needed
                        await trigger_keyframe_if_needed(pool, row)
                    except Exception as trigger_error:
                        logger.debug(f"trigger_keyframe skipped: {trigger_error}")

                else:

                    task["skipped"] = task.get("skipped",0) + 1

        except Exception as e:

            if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():

                task["skipped"] += 1

            else:

                logger.warning(f"[cms-spider] insert error: {e}")

                task["errors"] += 1

        await _cancellable_sleep(item_delay, task_id)

    task["status"] = "done"

    await _update_site_status(task.get("url", ""), "done")

    task["phase"] = f"Done! Found {task['discovered']}, added {task['added']}, skipped {task['skipped']}"

    task["updated_at"] = time.time()

    task["updated_at"] = time.time()

    await _update_site_status(task.get("url", ""), "done")

    return task
