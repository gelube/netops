// Thumbnail retry: IntersectionObserver retries on viewport entry, max 2 attempts
// New img loads in background; placeholder stays visible until img succeeds (no flicker)
var MAX_THUMB_RETRIES = 2;
var _thumbObserver = null;
if ('IntersectionObserver' in window) {
  _thumbObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (!entry.isIntersecting) return;
      var ph = entry.target;
      if (!ph.classList.contains('thumb-retry')) return;
      var origSrc = ph.getAttribute('data-retry-src');
      if (!origSrc) return;
      var count = parseInt(ph.getAttribute('data-retry-count') || '0', 10);
      _thumbObserver.unobserve(ph);
      if (count >= MAX_THUMB_RETRIES) return; // give up, keep 🎬
      ph.setAttribute('data-retry-count', String(count + 1));
      // Load new img in memory; only swap into DOM on success
      var newImg = document.createElement('img');
      newImg.className = 'thumb';
      newImg.setAttribute('data-src', origSrc);
      newImg.onload = function() { ph.replaceWith(newImg); };
      newImg.onerror = function() {
        // Keep placeholder, retry after delay
        if (_thumbObserver) setTimeout(function() { _thumbObserver.observe(ph); }, 500);
      };
      newImg.src = origSrc + (origSrc.indexOf('?') > -1 ? '&' : '?') + '_r=' + Date.now();
    });
  }, { rootMargin: '200px' });
}

function imgRetry(img) {
  var origSrc = img.getAttribute('data-src') || (img.src ? img.src.split('_r=')[0] : '');
  var ph = document.createElement('div');
  ph.className = 'thumb-placeholder thumb-retry';
  ph.innerHTML = '\uD83C\uDFAC';
  if (origSrc) {
    ph.setAttribute('data-retry-src', origSrc);
    ph.setAttribute('data-retry-count', '0');
    if (_thumbObserver) _thumbObserver.observe(ph);
  }
  img.replaceWith(ph);
}

// Format count: 12345 -> 12.3K
function formatCount(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(n || 0);
}
/* ── Frontend Logic ───────────────────────────────── */

const API = '';


// Inject canonical URL and og:url from main domain
(async function() {
    try {
        const r = await fetch(API + '/api/main-domain');
        const d = await r.json();
        if (d.url) {
            const path = window.location.pathname;
            const canonical = d.url + path + window.location.search;
            let link = document.querySelector('link[rel="canonical"]');
            if (!link) {
                link = document.createElement('link');
                link.rel = 'canonical';
                document.head.appendChild(link);
            }
            link.href = canonical;

            let og = document.querySelector('meta[property="og:url"]');
            if (!og) {
                og = document.createElement('meta');
                og.setAttribute('property', 'og:url');
                document.head.appendChild(og);
            }
            og.content = canonical;
        }
    } catch(e) {}
})();

// Cache shortlink status (avoid per-click async fetch — card.href needs sync string)
let _shortlinkEnabled = null;
async function _cacheShortlinkStatus() {
    try {
        const r = await fetch(API + '/api/shortlink/status');
        if (r.ok) _shortlinkEnabled = (await r.json()).enabled;
        else _shortlinkEnabled = false;
    } catch(e) { _shortlinkEnabled = false; }
}
// Sync: use cached shortlink status
function buildVideoUrl(v) {
    if (_shortlinkEnabled && v.short_code) return '/' + v.short_code;
    return '/player?v=' + Date.now() + '&id=' + v.id;
}
// Init: prefetch shortlink status on page load
_cacheShortlinkStatus();


// Get localized name from i18n object, fallback to default name
function localizedName(item) {
  const lang = localStorage.getItem('vh_lang') || 'en';
  if (item.name_i18n && item.name_i18n[lang]) return item.name_i18n[lang];
  return item.name;
}

// Localize a category name string using the mapping built from loadCategories
function localizeCategory(name) {
  if (!name) return t('uncategorized');
  const lang = localStorage.getItem('vh_lang') || 'en';
  // Dynamic mapping from API (loaded by loadCategories)
  const mapping = window._catI18n && window._catI18n[name];
  if (mapping && mapping[lang]) return mapping[lang];
  return name;
}

let currentPage = 1;
let currentSort = 'newest';
let currentSearch = '';
let currentCategory = '';
let currentTag = '';
let vrOnly = false;

// ── Scroll Position & State Persistence ────────────────
const NAV_STATE_KEY = 'vh_nav_state';

function saveNavState() {
  const state = {
    page: currentPage,
    sort: currentSort,
    search: currentSearch,
    category: currentCategory,
    tag: currentTag,
    vrOnly: vrOnly,
    scrollY: window.scrollY,
    ts: Date.now()
  };
  sessionStorage.setItem(NAV_STATE_KEY, JSON.stringify(state));
}

let _pendingScrollRestore = null;
function restoreNavState() {
  try {
    const raw = sessionStorage.getItem(NAV_STATE_KEY);
    if (!raw) return false;
    const state = JSON.parse(raw);
    // Only restore if within 30 minutes
    if (Date.now() - state.ts > 30 * 60 * 1000) {
      sessionStorage.removeItem(NAV_STATE_KEY);
      return false;
    }
    currentPage = state.page || 1;
    currentSort = state.sort || 'newest';
    currentSearch = state.search || '';
    currentCategory = state.category || '';
    if (state.tag) currentTag = state.tag;
    vrOnly = state.vrOnly || false;
    // Populate search input
    const si = document.getElementById('searchInput');
    if (si && currentSearch) si.value = currentSearch;
    // Defer scroll restoration until after videos are rendered
    _pendingScrollRestore = state.scrollY || 0;
    sessionStorage.removeItem(NAV_STATE_KEY);
    return true;
  } catch(e) {
    return false;
  }
}

// Universal ad injector: sets innerHTML then re-executes all <script> tags
function injectAd(el, html) {
  if (!el || !html) return;
  var code = Array.isArray(html) ? html.join('') : html;
  code = code.replace(/\\\//g, '/');
  // Anti-block: backend rewrites URLs to /_adp/ when use_proxy=1, frontend respects that
  el.innerHTML = code;
  el.style.display = 'block';
  // Src interceptor removed - backend handles URL rewriting via use_proxy flag
  // Parallel script execution (faster than serial chain)
  var scripts = el.querySelectorAll('script');
  scripts.forEach(function(s) {
    var ns = document.createElement('script');
    if (s.src) { ns.src = s.src; ns.async = true; }
    else { ns.textContent = s.textContent; }
    if (s.type) ns.type = s.type;
    s.replaceWith(ns);
  });
  // Style iframes to fill width
  el.querySelectorAll('iframe[src]').forEach(function(f) {
    f.style.width = '100%'; f.style.maxWidth = '100%';
  });
  el.querySelectorAll('.aads-ad-container').forEach(function(d) { d.style.width = '100%'; d.style.maxWidth = '100%'; });
  el.querySelectorAll('.aads-ad-container iframe').forEach(function(f) { f.style.width = '100%'; f.style.maxWidth = '100%'; });
}

// Ad loader - popup ads pre-injected first so scripts start loading ASAP
async function loadBoost() {
  try {
    const r = await fetch(`${API}/api/feed/html`);
    const slotMap = await r.json();

    // 0. Pre-inject popup ad FIRST (script needs time to load, overlay shown later)
    if (slotMap.popup) {
      var popupAds = Array.isArray(slotMap.popup) ? slotMap.popup : [slotMap.popup];
      window._popupQueue = popupAds.filter(function(h){return h && h.trim();});
      window._popupIdx = 0;
      if (window._popupQueue.length > 0) {
        var bpo = document.getElementById('bpo');
        if (bpo) { bpo.innerHTML = ''; injectAd(bpo, window._popupQueue[0]); }
      }
    }

    // 1. Critical ads: inject immediately (header, footer)
    if (slotMap.header) injectAd(document.getElementById('bh'), slotMap.header);
    if (slotMap.footer) injectAd(document.getElementById('bft'), slotMap.footer);
    // Feed ad: defer injection via IntersectionObserver (don't block first render)
    if (slotMap.feed) {
      window._feedAd = Array.isArray(slotMap.feed) ? slotMap.feed.join('') : slotMap.feed;
      // Use requestIdleCallback or setTimeout to defer feed ad injection
      var fillFeedAds = function() {
        document.querySelectorAll('.feed-ad-card[data-feed-slot]').forEach(function(el) {
          if (!el.innerHTML.trim()) { injectAd(el, getFeedAdHTML()); }
        });
      };
      if (window.requestIdleCallback) {
        window.requestIdleCallback(fillFeedAds, {timeout: 2000});
      } else {
        setTimeout(fillFeedAds, 300);
      }
    }
    // 2. Sidebar ads
    if (slotMap.sidebar) {
      var items = Array.isArray(slotMap.sidebar) ? slotMap.sidebar : [slotMap.sidebar];
      items.forEach(function(h, i) { injectAd(document.getElementById('bs-' + (i + 1)), h); });
    }
    // 3. Right sidebar
    if (slotMap.right_sidebar) {
      var items = Array.isArray(slotMap.right_sidebar) ? slotMap.right_sidebar : [slotMap.right_sidebar];
      items.forEach(function(h, i) { injectAd(document.getElementById('rs-' + (i + 1)), h); });
    }
    // 4. Show popup overlay AFTER other ads are injected (gives popup ad script time to render)
    if (window._popupQueue && window._popupQueue.length > 0) {
      setTimeout(function() {
        var overlay = document.getElementById('popupOverlay');
        if (overlay) overlay.style.display = 'flex';
      }, 500);
    }
    // Popunder (multiple ads supported)
    if (slotMap.popunder) {
      var puAds = Array.isArray(slotMap.popunder) ? slotMap.popunder : [slotMap.popunder];
      puAds.forEach(function(code) { if (code && code.trim()) initPop({ ad_code: code }); });
    }
  } catch(e) { console.error('[App] ad load failed:', e); }
}

function renderBoost(slot, ad) {
  // Map slot name to DOM element ID (renamed from ad-* to slot-* during anti-blocker refactor)
  const SLOT_ID_MAP = { sidebar: 'bs', header: 'bh', feed: 'bf', footer: 'bft', player_top: 'bt', player_bot: 'bb', player_pause: 'bp', popup: 'bpo' };
  const slotId = SLOT_ID_MAP[slot] || `slot-${slot.replace('_', '-')}`;
  let el = document.getElementById(slotId) || document.getElementById(`box-${slot}`) || document.getElementById(`box-${slot.replace('_', '-')}`);
  console.log('[App] renderBoost slot=', slot, 'slotId=', slotId, 'el=', el ? 'FOUND' : 'NOT FOUND', 'ad=', ad ? ad.id : 'null');
  if (!el || !ad) return;
  // Track impression for custom ads only
  if (!ad.network && ad.id) {
    fetch(`${API}/api/v/${ad.id}`, {method:'POST'}).catch(()=>{});
  }

  if (ad.ad_type === 'code' || ad.network) {
    // Network ad or custom code ad - inject HTML/JS
    const code = ad.ad_code || ad.network_code || '';
    if (code) {
      const wrapper = document.createElement('div');
      if (ad.network) wrapper.className = 'ec-j25kz3';
      el.appendChild(wrapper);
      el.style.display = 'block';
      injectAd(wrapper, code);
    } else {
      const name = ad.title || ad.network_name || '';
      el.innerHTML += `<div class="cb-5b1272"><span class="ct-15khaf">${t('label_promo')}</span><div class="ci-n5qo5a">${name}</div></div>`;
    }
  } else if (ad.ad_type === 'image') {
    // Data URIs (SVG placeholders) don't need proxy
    const isDataUri = ad.image_url && ad.image_url.startsWith('data:');
    const imgUrl = ad.image_url ? (isDataUri ? ad.image_url : `/api/proxy/image?url=${encodeURIComponent(ad.image_url)}`) : '';
    // Use server-side redirect to avoid blockers seeing destination domain
    const goUrl = ad.redirect_url || (ad.link_url ? ad.link_url : '');
    const link = goUrl ? `<a href="${goUrl}" target="_blank" rel="noopener" onclick="trackBoostClick(${ad.id})">` : '';
    const linkEnd = goUrl ? '</a>' : '';
    if (imgUrl) {
      el.innerHTML = `<span class="ct-15khaf">${t('label_promo')}</span>${link}<img src="${imgUrl}" alt="${ad.title}" style="width:100%;aspect-ratio:16/9;object-fit:cover;display:block;border-radius:6px">${linkEnd}`;
      el.style.display = 'block';
    } else {
      const title = ad.title || '';
      el.innerHTML = `<div class="cb-5b1272"><span class="ct-15khaf">${t('label_promo')}</span><div class="ci-n5qo5a">${title}</div></div>`;
    }
  } else if (ad.ad_type === 'native') {
    el.innerHTML = `<div class="cn-81gv42" onclick="trackBoostClick(${ad.id})"><div class="cx-qynaat"><h4>${ad.title}<span class="cd-h2hcke">${t('promote_badge')}</span></h4></div></div>`;
    el.style.display = 'block';
  } else if (ad.ad_type === 'popunder' || ad.ad_type === 'preroll') {
    return;
  }

}

function trackBoostClick(adId) {
  fetch(`${API}/api/go/${adId}`, {method:'POST'}).catch(()=>{});
}

// Mobile nav panel helpers
function toggleMobileCats() {
  var cats = document.getElementById('mobileNavCats');
  var icon = document.getElementById('mnavExpandIcon');
  if (!cats) return;
  var expanded = cats.style.display === 'block';
  cats.style.display = expanded ? 'none' : 'block';
  if (icon) {
    icon.innerHTML = expanded
      ? '<path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
      : '<path d="M4 10l4-4 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
  }
}
function closeMobileCats() {
  var cats = document.getElementById('mobileNavCats');
  var icon = document.getElementById('mnavExpandIcon');
  if (cats) cats.style.display = 'none';
  if (icon) icon.innerHTML = '<path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
}
function selectMobileCat(catName) {
  setCategory(catName);
  // Update active state in mobile cat row
  var items = document.querySelectorAll('#mnavCats .mnav-cat-item');
  items.forEach(function(it) {
    var onclick = it.getAttribute('onclick') || '';
    var m = onclick.match(/selectMobileCat\('([^']*)'\)/);
    if (m && m[1] === catName) it.classList.add('active');
    else it.classList.remove('active');
  });
  // Update "All" active state
  var allItem = document.querySelector('#mnavCats .mnav-cat-item:first-child');
  if (allItem) {
    if (!catName) allItem.classList.add('active');
    else allItem.classList.remove('active');
  }
  // Fetch and render subcategories
  getCats().then(function(cats){
    renderMobileSub(cats);
  }).catch(function(){});
}
function renderMobileSub(cats) {
  var sub = document.getElementById('mnavSub');
  if (!sub) return;
  var curCat = cats.find(function(c){ return c.name === currentCategory; });
  if (curCat && curCat.tags && curCat.tags.length) {
    var sh = '<div class="mnav-sub-row">';
    curCat.tags.forEach(function(tg) {
      var disp = localizeTag(tg.tag);
      if (!disp) return;
      var ta = currentTag === tg.tag ? ' active' : '';
      var ts = tg.tag.replace(/"/g, '&quot;');
      sh += '<a href="javascript:void(0)" class="mnav-sub-item' + ta + '" data-tag="' + ts + '" onclick="setTag(this.dataset.tag)">' + disp + '</a>';
    });
    sh += '</div>';
    sub.innerHTML = sh;
    sub.style.display = 'block';
  } else {
    sub.innerHTML = '';
    sub.style.display = 'none';
  }
}

// Cached categories promise (avoids redundant /api/categories fetches)
let _catsPromise = null;
function getCats() {
  if (!_catsPromise) {
    _catsPromise = fetch(API + '/api/categories').then(function(r) {
      if (!r.ok) throw new Error('categories ' + r.status);
      return r.json();
    });
    // Reset on failure so subsequent callers retry
    _catsPromise.catch(function() { _catsPromise = null; });
  }
  return _catsPromise;
}

// Category bar
async function loadCategories() {
  try {
    const cats = await getCats();
    window._catI18n = {};
    cats.forEach(c => { if (c.name_i18n && Object.keys(c.name_i18n).length) window._catI18n[c.name] = c.name_i18n; });

    // Render mobile nav panel
    var mnp = document.getElementById('mnavCats');
    if (mnp) {
      var mh = '';
      mh += '<div class="mnav-cat-row">';
      var allAct = !currentCategory && !currentTag ? ' active' : '';
      mh += '<a href="javascript:void(0)" class="mnav-cat-item' + allAct + '" onclick="selectMobileCat(\'\')">' + t('all') + '</a>';
      cats.forEach(function(c) {
        var act = currentCategory === c.name ? ' active' : '';
        var lbl = localizeCategory(c.name);
        var cn = c.name.replace(/['"]/g, '\\$&');
        var hasSub = c.tags && c.tags.length ? ' has-sub' : '';
        mh += '<a href="javascript:void(0)" class="mnav-cat-item' + act + hasSub + '" onclick="selectMobileCat(\'' + cn + '\')">' + lbl + '</a>';
      });
      mh += '</div>';
      mnp.innerHTML = mh;
    }
    // Sort into mobile nav
    var mns = document.getElementById('mnavSort');
    if (mns) {
      var sorts = [
        {key:'newest', lbl:t('sort_most_recent')},
        {key:'most_viewed', lbl:t('sort_most_viewed')},
        {key:'top_rated', lbl:t('sort_top_rated')},
        {key:'likes', lbl:t('sort_most_liked')},
        {key:'favorites', lbl:t('sort_most_favorited')},
        {key:'weekly', lbl:t('sort_weekly_top')},
        {key:'monthly', lbl:t('sort_monthly_top')},
        {key:'longest', lbl:t('sort_longest')},
        {key:'shortest', lbl:t('sort_shortest')}
      ];
      var sh = '<div class="mnav-sort-row">';
      sorts.forEach(function(s) {
        var act = currentSort === s.key ? ' active' : '';
        sh += '<a href="javascript:void(0)" class="mnav-sort-item' + act + '" onclick="setSort(\'' + s.key + '\'); closeMobileCats()">' + s.lbl + '</a>';
      });
      sh += '</div>';
      mns.innerHTML = sh;
    }
    // Subcategories for current category
    renderMobileSub(cats);
  } catch(e) { console.error('[App] Failed to load categories:', e); }
}
let _loadAbort = null;
let _loadReqId = 0;
let _loadDebounceTimer = null;

function loadVideosDebounced() {
  clearTimeout(_loadDebounceTimer);
  _loadDebounceTimer = setTimeout(() => loadVideos(), 200);
}

function getFeedAdHTML() {
  if (!window._feedAd) return '';
  var html = window._feedAd;
  var m = html.match(/data-aa="([^"]+)"/);
  if (m) {
    var ids = m[1].split(',').map(function(s){return s.trim();}).filter(Boolean);
    if (ids.length > 1) {
      var pick = ids[Math.floor(Math.random() * ids.length)];
      html = html.replace(/data-aa="[^"]+"/, 'data-aa="' + pick + '"');
      html = html.replace(/\/(\d+)\//, '/' + pick + '/');
    }
  }
  return html;
}

async function loadVideos() {
  const grid = document.getElementById('videoGrid');
  if (!grid) return;

  // Cancel any in-flight request
  if (_loadAbort) { try { _loadAbort.abort(); } catch(e){} }
  _loadAbort = new AbortController();
  const reqId = ++_loadReqId;

  // Show loading overlay without clearing existing content
  const existing = grid.querySelector('.loading-overlay');
  if (!existing) {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.style.cssText = 'position:absolute;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:100;color:#fff;font-size:14px;pointer-events:none';
    overlay.textContent = t('loading');
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'position:relative';
    grid.style.position = 'relative';
    grid.appendChild(wrapper);
    while (wrapper.nextSibling) wrapper.parentNode.removeChild(wrapper.nextSibling);
    wrapper.appendChild(overlay);
  }

  const params = new URLSearchParams({
    page: currentPage, size: 24, sort: currentSort,
  });
  if (currentCategory) params.set('category', currentCategory);
  if (currentTag) params.set('tag', currentTag);
  if (vrOnly) params.set('vr_only', 'true');
  if (currentSearch) params.set('search', currentSearch);

  try {
    const r = await fetch(`${API}/api/videos?${params}`, { signal: _loadAbort.signal });
    if (r.status === 429) {
      if (reqId === _loadReqId) grid.innerHTML = `<div class="loading" data-i18n="request_frequent">${t('request_frequent')}</div>`;
      setTimeout(() => loadVideos(), 2000);
      return;
    }
    const data = await r.json();

    // Ignore stale response — a newer request has been issued
    if (reqId !== _loadReqId) return;

    const videos = Array.isArray(data) ? data : (data.items || []);
    window._videoTotal = data.total || videos.length;
    // Release old failed-thumbnail placeholders before rebuilding (avoid observer leak)
    if (_thumbObserver) _thumbObserver.disconnect();
    grid.innerHTML = '';

    if (!videos.length) {
      grid.innerHTML = `<div class="loading" data-i18n="no_videos">${t('no_videos')}</div>`;
      return;
    }

    // Feed ad with multi-ID rotation
    // Mix native promos into video grid
    const nativePromos = (window._nativeBoost || [])
      .filter(a => a.slot === 'feed' && a.enabled !== 0 && !a.network);
    let npIdx = 0;

    // Insert 6 feed ad placeholder cards (filled by loadBoost)
    for (let adI = 0; adI < 6; adI++) {
      const adCard = document.createElement('div');
      adCard.className = 'video-card feed-ad-card';
      adCard.setAttribute('data-feed-slot', adI);
      grid.appendChild(adCard);
    }
    videos.forEach((v, i) => {
      const card = document.createElement('a');
      card.className = 'video-card';
      card.href = buildVideoUrl(v);
      // Save nav state before navigating to player
      card.addEventListener('click', function(e) {
        saveNavState();
      });

      const thumbUrl = v.thumbnail ? (v.thumbnail.startsWith('/image_cache/') ? v.thumbnail : v.thumbnail.startsWith('data:') ? '' : `/api/proxy/image?url=${encodeURIComponent(v.thumbnail)}&source=${encodeURIComponent(v.url)}`) : '';
      const thumbHtml = thumbUrl
        ? `<img class="thumb" src="${escUrl(thumbUrl)}" data-src="${escUrl(thumbUrl)}" loading="lazy" onerror="imgRetry(this)">`
        : `<div class="thumb-placeholder">🎬</div>`;

      const vrBadge = v.vr_mode === 'equirectangular' ? '<span class="vr-badge">VR</span>' : '';
      const _fmtDur = (d) => {
    if (!d) return '';
    const m = d.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
    if (m) {
      const h = parseInt(m[1]||0), mi = parseInt(m[2]||0), s = parseInt(m[3]||0);
      return h ? `${h}:${String(mi).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${mi}:${String(s).padStart(2,'0')}`;
    }
    return d;
  };
      const durBadge = v.duration ? `<span class="duration-badge">${_fmtDur(v.duration)}</span>` : '';
      
      card.innerHTML = `${thumbHtml}${vrBadge}
        <div class="info">
          <h3>${esc(v.title || t('no_title'))}</h3>
          <div class="meta">
            <span>${esc(localizeCategory(v.category))}</span>
            <span>${timeAgo(v.created_at)}</span>
            ${durBadge}
          </div>
          <div class="card-bottom">
            <button class="card-like-btn" data-vid="${Number(v.id)||0}" onclick="event.stopPropagation();event.preventDefault();toggleCardLike(${Number(v.id)||0})">
              <svg class="icon-outline" viewBox="0 0 24 24" width="13" height="13"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="none" stroke="currentColor" stroke-width="2"/></svg>
              <svg class="icon-filled" viewBox="0 0 24 24" width="13" height="13" style="display:none"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="currentColor"/></svg>
              <span class="card-like-count">${formatCount(v.likes || 0)}</span>
            </button>
            <button class="card-fav-btn" data-vid="${Number(v.id)||0}" onclick="event.stopPropagation();event.preventDefault();toggleCardFav(${Number(v.id)||0})">
              <svg class="icon-outline" viewBox="0 0 24 24" width="13" height="13"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="none" stroke="currentColor" stroke-width="2"/></svg>
              <svg class="icon-filled" viewBox="0 0 24 24" width="13" height="13" style="display:none"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="currentColor"/></svg>
              <span class="card-fav-count">${formatCount(v.favorites || 0)}</span>
            </button>
            <span class="card-views-count">
              <svg viewBox="0 0 24 24" width="13" height="13"><path d="M12 4.5C7 4.5 2.7 7.6 1 12c1.7 4.4 6 7.5 11 7.5s9.3-3.1 11-7.5c-1.7-4.4-6-7.5-11-7.5zm0 12.5c-2.8 0-5-2.2-5-5s2.2-5 5-5 5 2.2 5 5-2.2 5-5 5zm0-8c-1.7 0-3 1.3-3 3s1.3 3 3 3 3-1.3 3-3-1.3-3-3-3z" fill="currentColor"/></svg>
              ${formatCount(v.views || 0)}
            </span>
            <a href="${escUrl('/channel/' + encodeURIComponent(v.uploader_slug || ''))}" class="uploader-link" onclick="event.stopPropagation()">${esc(v.uploader_name || 'Anonymous')}</a>${v.uploader_verified ? '<span class="verified-badge">✓</span>' : ''}
          </div>
        </div>`;
      grid.appendChild(card);

   // Insert feed ad every 8 videos (placeholder, filled by loadBoost)
      if ((i + 1) % 8 === 0) {
        {
          const adCard = document.createElement('div');
          adCard.className = 'video-card feed-ad-card';
          adCard.setAttribute('data-feed-slot', 'mid-' + i);
          grid.appendChild(adCard);
        }
        if (npIdx < nativePromos.length) {
          const np = nativePromos[npIdx++];
          const npCard = document.createElement('a');
          npCard.className = 'video-card';
          npCard.href = np.redirect_url || np.link_url || '#';
          npCard.target = '_blank';
          npCard.rel = 'noopener';
          const npThumb = np.image_url ? `/api/proxy/image?url=${encodeURIComponent(np.image_url)}` : '';
          const npThumbHtml = npThumb ? `<img class="thumb" src="${npThumb}" data-src="${npThumb}" loading="lazy" onerror="imgRetry(this)">` : '';
          npCard.innerHTML = `${npThumbHtml}<div class="info"><h3>${np.title || ''}</h3><div class="meta"><span>${t('label_promo') || 'Promoted'}</span></div></div>`;
          npCard.addEventListener('click', () => { fetch(`${API}/api/go/${np.id}`, {method:'POST'}).catch(()=>{}); });
          grid.appendChild(npCard);
        }
      }
    });
    updateAllCardStates();
    renderPagination();
    // Restore scroll position after videos are rendered (returning from player)
    if (_pendingScrollRestore !== null) {
      const y = _pendingScrollRestore;
      _pendingScrollRestore = null;
      requestAnimationFrame(() => window.scrollTo(0, y));
    }
  } catch(e) {
    if (e.name === 'AbortError') return;  // request was cancelled, ignore
    if (reqId === _loadReqId) grid.innerHTML = `<div class="loading" data-i18n="load_failed">${t('load_failed')}</div>`;
  }
}

function renderPagination() {
  const pag = document.getElementById('pagination');
  if (!pag) return;
  const totalPages = Math.ceil((window._videoTotal || 0) / 24);
  pag.innerHTML = '';
  if (totalPages <= 1) return;

  const mkBtn = (text, page, disabled = false) => {
    const btn = document.createElement('button');
    btn.textContent = text;
    btn.disabled = disabled;
    btn.className = page === currentPage ? 'active' : '';
    btn.onclick = () => { currentPage = page; loadVideos(); window.scrollTo(0,0); };
    return btn;
  };

  // First page
  pag.appendChild(mkBtn('«', 1, currentPage <= 1));
  // Prev
  pag.appendChild(mkBtn(t('prev_page'), currentPage - 1, currentPage <= 1));
  const start = Math.max(2, currentPage - 3);
  const end = Math.min(totalPages - 1, currentPage + 3);
  if (start > 2) {
    const dots = document.createElement('span');
    dots.className = 'page-dots'; dots.textContent = '...';
    pag.appendChild(dots);
  }
  for (let i = start; i <= end; i++) pag.appendChild(mkBtn(i, i));
  if (end < totalPages - 1) {
    const dots = document.createElement('span');
    dots.className = 'page-dots'; dots.textContent = '...';
    pag.appendChild(dots);
  }
  // Next
  pag.appendChild(mkBtn(t('next_page'), currentPage + 1, currentPage >= totalPages));
  // Last page
  pag.appendChild(mkBtn('»', totalPages, currentPage >= totalPages));
  // Page info + jump
  const info = document.createElement('span');
  info.className = 'page-info';
  info.textContent = ' ' + currentPage + ' / ' + totalPages + ' ';
  pag.appendChild(info);
  const jumpWrap = document.createElement('span');
  jumpWrap.className = 'page-jump';
  const jumpInput = document.createElement('input');
  jumpInput.type = 'number';
  jumpInput.min = 1;
  jumpInput.max = totalPages;
  jumpInput.className = 'page-jump-input';
  jumpInput.placeholder = '#';
  jumpInput.onkeydown = (e) => {
    if (e.key === 'Enter') {
      let p = parseInt(jumpInput.value);
      if (p >= 1 && p <= totalPages) { currentPage = p; loadVideos(); window.scrollTo(0,0); }
      jumpInput.value = '';
    }
  };
  jumpWrap.appendChild(document.createTextNode('跳至'));
  jumpWrap.appendChild(jumpInput);
  jumpWrap.appendChild(document.createTextNode('页'));
  pag.appendChild(jumpWrap);
}

// Search
function doSearch(e) {
  e.preventDefault();
  currentSearch = document.getElementById('searchInput').value.trim();
  currentPage = 1;
  loadVideos().then(() => {
    currentSearch = '';
    document.getElementById('searchInput').value = '';
  });
}

// Sort
function setSort(sort) {
  currentSort = sort;
  currentPage = 1;
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.toggle('active', b.dataset.sort === sort));
  // Update mobile sort active state
  document.querySelectorAll('#mnavSort .mnav-sort-item').forEach(function(it) {
    var onclick = it.getAttribute('onclick') || '';
    if (onclick.includes("'" + sort + "'")) it.classList.add('active');
    else it.classList.remove('active');
  });
  loadVideosDebounced();
}

// Category
function setCategory(cat) {
  // "All" (empty cat) always resets all filters and reloads
  if (cat === '') {
    currentCategory = '';
    currentTag = '';
    vrOnly = false;
    currentPage = 1;
    // Update mobile cat active states
    document.querySelectorAll('#mnavCats .mnav-cat-item').forEach(function(it) {
      it.classList.remove('active');
    });
    var allItem = document.querySelector('#mnavCats .mnav-cat-item:first-child');
    if (allItem) allItem.classList.add('active');
    // Clear sub
    var sub = document.getElementById('mnavSub');
    if (sub) { sub.innerHTML = ''; sub.style.display = 'none'; }
    loadVideosDebounced();
    loadTagSidebar();
    return;
  }
  if (currentCategory === cat) {
    // Same category clicked: if a tag is active, clear it and show all videos
    if (currentTag) {
      currentTag = '';
      currentPage = 1;
      loadVideosDebounced();
      loadTagSidebar();
      return;
    }
    // No tag active — just toggle expand/collapse in sidebar
    var hdr = document.querySelector('[data-cat="' + cat + '"]');
    if (hdr) {
      var body = hdr.nextElementSibling;
      var arrow = hdr.querySelector('.arrow');
      var collapsed = hdr.dataset.collapsed === '1';
      if (collapsed) { if (body) body.style.display=''; if (arrow) arrow.textContent='▼'; hdr.dataset.collapsed='0'; }
      else { if (body) body.style.display='none'; if (arrow) arrow.textContent='▶'; hdr.dataset.collapsed='1'; }
    }
    return;
  }
  currentCategory = cat;
  currentTag = '';
  vrOnly = false;
  currentPage = 1;
  loadVideosDebounced();
  loadTagSidebar();
}

function setTag(tag) {
  currentTag = (currentTag === tag) ? '' : tag;
  currentPage = 1;
  // Update mobile sub active state
  document.querySelectorAll('#mnavSub .mnav-sub-item').forEach(function(it) {
    var dt = it.getAttribute('data-tag') || '';
    if (dt === tag) it.classList.add('active');
    else it.classList.remove('active');
  });
  loadVideosDebounced();
  loadTagSidebar();
}
// Quality sidebar: VR toggle (based on vr_mode, cross-category)
function setVrOnly() {
  vrOnly = !vrOnly;
  if (vrOnly) { currentCategory = ''; currentTag = ''; }
  currentPage = 1;
  loadVideosDebounced();
  loadTagSidebar();
}
// Quality sidebar: resolution/fps/ai tag (cross-category, clears category)
function setQualityTag(tag) {
  currentCategory = '';
  vrOnly = false;
  currentTag = (currentTag === tag) ? '' : tag;
  currentPage = 1;
  loadVideosDebounced();
  loadTagSidebar();
}

// Time ago
function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return t('minute_ago').replace('{n}', mins);
  const hours = Math.floor(mins / 60);
  if (hours < 24) return t('hour_ago').replace('{n}', hours);
  const days = Math.floor(hours / 24);
  if (days < 30) return t('day_ago').replace('{n}', days);
  return dateStr.slice(0, 10);
}

// ── Popunder Ad Logic ────────────────────────────────────
let boostPop = null;
let popunderShown = false;
const POPUNDER_COOLDOWN_KEY = 'vh_popunder_ts';
const POPUNDER_COOLDOWN_MS = 30 * 60 * 1000;


function showNextPopup() {
  var queue = window._popupQueue || [];
  var idx = window._popupIdx || 0;
  if (idx >= queue.length) return;
  var bpo = document.getElementById('bpo');
  var overlay = document.getElementById('popupOverlay');
  if (!bpo || !overlay) return;
  // idx 0 already pre-injected in loadBoost, just show
  if (idx === 0) { overlay.style.display = 'flex'; return; }
  bpo.innerHTML = '';
  injectAd(bpo, queue[idx]);
  setTimeout(function() { overlay.style.display = 'flex'; }, 300);
}

function closePopupAd() {
  var overlay = document.getElementById('popupOverlay');
  if (overlay) overlay.style.display = 'none';
  window._popupIdx = (window._popupIdx || 0) + 1;
  var queue = window._popupQueue || [];
  if (window._popupIdx < queue.length) {
    setTimeout(showNextPopup, 300);
  }
}

var _popQueue = [];
function initPop(ad) {
  _popQueue.push(ad);
  const lastTs = parseInt(localStorage.getItem(POPUNDER_COOLDOWN_KEY) || '0');
  if (Date.now() - lastTs < POPUNDER_COOLDOWN_MS) return;

  document.addEventListener('click', handlePopunder, true);
}

function handlePopunder(e) {
  if (popunderShown) return;
  const tag = e.target.tagName;
  if (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(tag)) return;
  if (e.target.closest('video') || e.target.closest('.cpo-mkxg6k') || e.target.closest('.po-t5g8qk')) return;

  popunderShown = true;
  document.removeEventListener('click', handlePopunder, true);

  _popQueue.forEach(function(ad) {
    var url = ad.redirect_url || ad.link_url || '';
    var adCode = ad.ad_code || '';
    if (!url && !adCode) return;
    var win = window.open('', '_blank');
    if (win) {
      if (url) {
        win.location = url;
      } else if (adCode) {
        win.document.open();
        win.document.write('<html><head><title></title></head><body>' + adCode + '</body></html>');
        win.document.close();
      }
      try { win.blur(); window.focus(); } catch(_) {}
    }
    if (ad.id) {
      fetch(API + '/api/v/' + ad.id, {method:'POST'}).catch(function(){});
      fetch(API + '/api/go/' + ad.id, {method:'POST'}).catch(function(){});
    }
  });

  localStorage.setItem(POPUNDER_COOLDOWN_KEY, String(Date.now()));
}

// ── Re-apply i18n on language change ─────────────────────
window.addEventListener('langchange', function() {
  loadCategories().then(function() {
    return loadTagSidebar();
  }).then(function() {
    loadVideos();
  });
});

// ── Ad-blocker detection ───────────────────────────────────
function checkShield(cb) {
  // DOM bait only — network probe (e.g. googlesyndication.com) fails in China due to GFW, causing false positives
  const bait = document.createElement('div');
  bait.innerHTML = '&nbsp;';
  bait.className = 'sz-wu0swg cb-5b1272 ct-15khaf ci-n5qo5a cbn-fy4f7b pc-3grlq5 cn-81gv42 cd-h2hcke ec-j25kz3';
  bait.style.cssText = 'position:absolute;top:-9999px;left:-9999px;height:1px;width:1px;overflow:hidden;';
  document.body.appendChild(bait);
  setTimeout(() => {
    const blocked = bait.offsetHeight === 0 || bait.offsetParent === null;
    bait.remove();
    cb(blocked);
  }, 250);
}

function showShieldMsg() {
  document.querySelectorAll('.sz-wu0swg').forEach(slot => {
    if (!slot.children.length || (slot.children.length === 1 && slot.children[0].classList.contains('cb-5b1272'))) {
      slot.innerHTML = '<div style="text-align:center;padding:16px;margin:8px auto;background:rgba(255,71,87,.08);border:1px solid rgba(255,71,87,.2);border-radius:8px;max-width:728px">' +
        '<div style="font-size:20px;margin-bottom:6px">🛡️</div>' +
        '<div style="color:#ff6b7a;font-size:14px;font-weight:600" data-i18n="blocker_notice_title">Support us by disabling your ad blocker</div>' +
        '<div style="color:#888;font-size:12px;margin-top:4px" data-i18n="blocker_notice_sub">Ads keep this site free. Please whitelist us!</div>' +
        '</div>';
    }
  });
}

// ── Init ──────────────────────────────────────────────────
(function() {
  // Try to restore navigation state from previous visit (e.g. back from player)
  const restored = restoreNavState();

  const p = new URLSearchParams(location.search);
  if (p.get('sort')) currentSort = p.get('sort');
  if (p.get('category')) currentCategory = p.get('category');
  if (p.get('tag')) currentTag = p.get('tag');
  if (p.get('vr_only') === '1') vrOnly = true;
  if (p.get('q')) {
    currentSearch = p.get('q');
    const si = document.getElementById('searchInput');
    if (si) si.value = currentSearch;
  }

  // Highlight active nav
  document.querySelectorAll('.sort-btn').forEach(b => {
    if (b.dataset.sort === currentSort) b.classList.add('active');
  });

  // Parallelize: video grid (LCP) and ads load simultaneously
  Promise.all([
    loadCategories().then(function() { loadTagSidebar(); }),
    loadVideos(),
    loadBoost()  // ads load in parallel, not blocking video render
  ]);

  // Blocker detection disabled — bait CSS classes may be styled hidden by our own CSS, causing false positives
  // setTimeout(() => {
  //   checkShield(blocked => {
  //     if (blocked) showShieldMsg();
  //   });
  // }, 1500);
})();

// Handle bfcache restore — re-init when page is restored from back/forward cache
window.addEventListener('pageshow', function(event) {
  if (event.persisted) {
    // Page restored from bfcache — reload sidebar and videos
    loadCategories();
    loadTagSidebar();
    loadVideos();
  }
});
// Card Like/Fav (homepage)

// Tag Sidebar
async function loadTagSidebar() {
  try {
    var [cats, rq] = await Promise.all([
      getCats(),
      fetch(API + '/api/quality')
    ]);
    if (!Array.isArray(cats)) return;
    var qualityItems = rq.ok ? await rq.json() : [];

    var box = document.getElementById('tagSidebar');
    if (!box) return;

    var totalVideos = 0;
    cats.forEach(function(c) { totalVideos += c.video_count; });
    var html = '';

    // All category (top of sidebar) - simple link, not collapsible
    var allActive = !currentCategory && !currentTag && !vrOnly;
    html += '<div class="tag-section">';
    html += '<div class="tag-section-header' + (allActive ? ' cat-active' : '') + '" onclick="setCategory(\'\')">'
      + t('all') + ' <span class="tag-count">(' + totalVideos + ')</span></div>';
    html += '</div>';

    // Quality section (dynamic from /api/quality; VR merged here)
    html += '<div class="tag-section">';
    html += '<div class="tag-section-header" data-collapsed="0"><span>' + t('quality_label') + '</span><span class="arrow">▼</span></div>';
    html += '<div class="tag-section-body">';
    qualityItems.forEach(function(q) {
      var dim = q.count === 0 ? 'opacity:0.4;cursor:default' : '';
      if (q.type === 'vr_only') {
        var act = vrOnly ? ' tag-active' : '';
        html += '<a href="javascript:void(0)" class="tag-side-link' + act + '" style="' + dim + '" onclick="setVrOnly()">' + q.label + ' <span class="tag-count">(' + q.count + ')</span></a>';
      } else {
        var act = (currentTag === q.tag && !currentCategory) ? ' tag-active' : '';
        html += '<a href="javascript:void(0)" class="tag-side-link' + act + '" style="' + dim + '" onclick="setQualityTag(\'' + q.tag + '\')">' + q.label + ' <span class="tag-count">(' + q.count + ')</span></a>';
      }
    });
    html += '</div></div>';

    // Categories with sub-tags
    cats.forEach(function(c) {
      var isActive = currentCategory === c.name;
      var expanded = isActive ? '0' : '1';
      html += '<div class="tag-section">';
      html += '<div class="tag-section-header' + (isActive ? ' cat-active' : '') + '" data-collapsed="' + expanded + '" data-cat="' + c.name + '" onclick="setCategory(this.dataset.cat)">';
      html += localizeCategory(c.name) + ' <span class="tag-count">(' + c.video_count + ')</span><span class="arrow">' + (expanded === '0' ? '▼' : '▶') + '</span>';
      html += '</div>';

      if (c.tags && c.tags.length) {
        html += '<div class="tag-section-body" style="' + (expanded === '1' ? 'display:none' : '') + '">';
        c.tags.forEach(function(tg) {
          var disp = localizeTag(tg.tag);
          if (!disp) return;
          var tagActive = currentTag === tg.tag && isActive;
          html += '<a href="javascript:void(0)" class="tag-side-link' + (tagActive ? ' tag-active' : '') + '" data-tag="' + tg.tag.replace(/"/g, '&quot;') + '" onclick="setTag(this.dataset.tag)">' + disp + ' <span class="tag-count">' + tg.count + '</span></a>';
        });
        html += '</div>';
      } else if (c.video_count === 0) {
        html += '<div class="tag-section-body" style="display:none"></div>';
      } else {
        html += '<div class="tag-section-body" style="display:none"></div>';
      }
      html += '</div>';
    });

    box.innerHTML = html;
    box.style.display = 'block';

    // Collapsible headers — but don't double-trigger from setCategory
    box.querySelectorAll('.tag-section-header').forEach(function(hdr) {
      if (hdr.dataset.cat) return; // category headers handled by setCategory
      hdr.addEventListener('click', function() {
        var body = this.nextElementSibling;
        var arrow = this.querySelector('.arrow');
        var collapsed = this.dataset.collapsed === '1';
        if (collapsed) {
          if (body) body.style.display = '';
          if (arrow) arrow.textContent = '▼';
          this.dataset.collapsed = '0';
        } else {
          if (body) body.style.display = 'none';
          if (arrow) arrow.textContent = '▶';
          this.dataset.collapsed = '1';
        }
      });
    });
  } catch(e) { console.error('loadTagSidebar error:', e); }
}

// Card Like/Fav (homepage) - standalone, uses localStorage
function toggleCardLike(vid) {
  var key = 'vhLikes';
  var data = JSON.parse(localStorage.getItem(key) || '{}');
  var isLiking = !data[vid];
  if (isLiking) { data[vid] = 1; } else { delete data[vid]; }
  localStorage.setItem(key, JSON.stringify(data));
  updateCardBtnState(vid, 'like', !!data[vid]);
  var url = isLiking ? '/api/videos/'+vid+'/like' : '/api/videos/'+vid+'/unlike';
  fetch(url, {method:'POST'}).then(function(r){return r.json();}).then(function(d){
    var span = document.querySelector('.card-like-btn[data-vid="'+vid+'"] .card-like-count');
    if (span) span.textContent = formatCount(d.likes||0);
  }).catch(function(){});
}
function toggleCardFav(vid) {
  var key = 'vhFavs';
  var data = JSON.parse(localStorage.getItem(key) || '{}');
  var isFaving = !data[vid];
  if (isFaving) { data[vid] = 1; } else { delete data[vid]; }
  localStorage.setItem(key, JSON.stringify(data));
  updateCardBtnState(vid, 'fav', !!data[vid]);
  var url = isFaving ? '/api/videos/'+vid+'/favorite' : '/api/videos/'+vid+'/unfavorite';
  fetch(url, {method:'POST'}).then(function(r){return r.json();}).then(function(d){
    var span = document.querySelector('.card-fav-btn[data-vid="'+vid+'"] .card-fav-count');
    if (span) span.textContent = formatCount(d.favorites||0);
  }).catch(function(){});
}
function updateCardBtnState(vid, type, active) {
  var sel = type === 'like' ? '.card-like-btn' : '.card-fav-btn';
  var btn = document.querySelector(sel + '[data-vid="'+vid+'"]');
  if (!btn) return;
  var outline = btn.querySelector('.icon-outline');
  var filled = btn.querySelector('.icon-filled');
  if (active) {
    if (outline) outline.style.display = 'none';
    if (filled) filled.style.display = '';
    btn.style.color = type === 'like' ? '#e50914' : '#ffc107';
  } else {
    if (outline) outline.style.display = '';
    if (filled) filled.style.display = 'none';
    btn.style.color = '#888';
  }
}
function updateAllCardStates() {
  var likes = JSON.parse(localStorage.getItem('vhLikes') || '{}');
  var favs = JSON.parse(localStorage.getItem('vhFavs') || '{}');
  document.querySelectorAll('.card-like-btn').forEach(function(btn) {
    var vid = parseInt(btn.dataset.vid);
    updateCardBtnState(vid, 'like', !!likes[vid]);
  });
  document.querySelectorAll('.card-fav-btn').forEach(function(btn) {
    var vid = parseInt(btn.dataset.vid);
    updateCardBtnState(vid, 'fav', !!favs[vid]);
  });
}

function filterByTag(tag) {
  window.location.href = "/tags/" + encodeURIComponent(tag);
}
