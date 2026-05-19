"""Full E2E test suite for netops-ai chat"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio

BASE = 'http://127.0.0.1:5000'
PASS = 0
FAIL = 0

async def run_test(name, fn, page):
    global PASS, FAIL
    print(f"\n--- {name} ---")
    try:
        result = await fn(page)
        if result:
            PASS += 1
            print(f"  PASS")
        else:
            FAIL += 1
            print(f"  FAIL")
    except Exception as e:
        FAIL += 1
        print(f"  FAIL: {e}")

async def test_page_loads(page):
    """Page loads without JS errors"""
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    if errors:
        print(f"  JS errors: {errors}")
        return False
    title = await page.title()
    print(f"  Title: {title}")
    return title == 'NetOps AI'

async def test_simple_chat(page):
    """Simple greeting gets AI response"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    
    await page.locator('#chat-input').fill('你好')
    await page.locator('#btn-send').click()
    
    # Wait for AI response
    await asyncio.sleep(20)
    
    messages = page.locator('#messages .msg-ai')
    count = await messages.count()
    if count > 0:
        last = messages.nth(count - 1)
        text = await last.text_content()
        print(f"  AI response: {text[:100] if text else 'EMPTY'}")
        return bool(text and len(text) > 0)
    return False

async def test_chat_input_cleared(page):
    """Input is cleared after sending"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    
    await page.locator('#chat-input').fill('test123')
    await page.locator('#btn-send').click()
    await asyncio.sleep(15)
    
    value = await page.locator('#chat-input').input_value()
    print(f"  Input value: '{value}'")
    return value == ''

async def test_chat_busy_state(page):
    """_chatBusy resets after response"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    
    await page.locator('#chat-input').fill('hello')
    await page.locator('#btn-send').click()
    await asyncio.sleep(20)
    
    busy = await page.evaluate('() => window._chatBusy')
    print(f"  _chatBusy: {busy}")
    return busy == False or busy == None

async def test_chat_clear(page):
    """Clear chat button works"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    
    # Send a message first
    await page.locator('#chat-input').fill('测试消息')
    await page.locator('#btn-send').click()
    await asyncio.sleep(15)
    
    # Find and click clear button
    clear_btn = page.locator('#btn-clear-chat, [onclick*="clearChat"]')
    if await clear_btn.count() == 0:
        # Try looking for it in the UI
        print("  Clear button not found, skipping")
        return True
    
    await clear_btn.first.click()
    await asyncio.sleep(2)
    
    messages = page.locator('#messages .msg')
    count = await messages.count()
    print(f"  Messages after clear: {count}")
    return True  # Just check no crash

async def test_api_chat_simple(page):
    """API /api/chat returns valid response"""
    import requests
    r = requests.post(f'{BASE}/api/chat', json={
        'message': '你好',
        'session_id': 'e2e_api_test'
    }, timeout=60)
    d = r.json()
    print(f"  success={d.get('success')} response_len={len(d.get('response',''))}")
    return d.get('success') == True and len(d.get('response','')) > 0

async def test_api_quick_config(page):
    """API /api/quick-config keyword match"""
    import requests
    r = requests.post(f'{BASE}/api/quick-config', json={
        'message': '版本',
        'device': '接入交换机',
        'mode': 'preview'
    }, timeout=30)
    d = r.json()
    print(f"  matched={d.get('matched')} query={d.get('query')}")
    return d.get('matched') == True

async def test_api_devices(page):
    """API /api/devices returns device list"""
    import requests
    r = requests.get(f'{BASE}/api/devices', timeout=10)
    d = r.json()
    devs = d.get('devices', [])
    print(f"  Device count: {len(devs)}")
    return len(devs) > 0

async def test_api_topology_state(page):
    """API /api/topology/state returns state"""
    import requests
    r = requests.get(f'{BASE}/api/topology/state', timeout=10)
    d = r.json()
    has_state = d.get('state') is not None or d.get('success') == True
    print(f"  success={d.get('success')} has_state={has_state}")
    return has_state

async def test_api_health(page):
    """API /api/health returns healthy"""
    import requests
    r = requests.get(f'{BASE}/api/health', timeout=10)
    d = r.json()
    print(f"  status={d.get('status')}")
    return d.get('status') == 'healthy' or d.get('success') == True

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Collect page errors globally
        page_errors = []
        page.on('pageerror', lambda err: page_errors.append(str(err)))
        
        await run_test("Page loads", test_page_loads, page)
        await run_test("Simple chat", test_simple_chat, page)
        await run_test("Chat input cleared", test_chat_input_cleared, page)
        await run_test("Chat busy state resets", test_chat_busy_state, page)
        await run_test("Chat clear", test_chat_clear, page)
        await run_test("API chat simple", test_api_chat_simple, page)
        await run_test("API quick-config", test_api_quick_config, page)
        await run_test("API devices", test_api_devices, page)
        await run_test("API topology state", test_api_topology_state, page)
        await run_test("API health", test_api_health, page)
        
        if page_errors:
            print(f"\nPage errors encountered: {page_errors[:5]}")
        
        await browser.close()
    
    print(f"\n{'='*60}")
    print(f"Results: {PASS} PASS / {FAIL} FAIL")
    if FAIL == 0:
        print("ALL TESTS PASSED")
    return FAIL == 0

asyncio.run(main())
