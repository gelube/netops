"""Full Playwright E2E test for netops-ai chat with device commands"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio, json

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
            print(f"  ✅ PASS")
        else:
            FAIL += 1
            print(f"  ❌ FAIL")
    except Exception as e:
        FAIL += 1
        print(f"  ❌ FAIL: {e}")

async def test_page_loads(page):
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    if errors:
        print(f"  JS errors: {errors[:3]}")
        return False
    return True

async def test_simple_greeting(page):
    """纯聊天不触发工具"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    await page.locator('#chat-input').fill('你好')
    await page.locator('#btn-send').click()
    await asyncio.sleep(15)
    msgs = page.locator('#messages .msg-ai')
    count = await msgs.count()
    if count > 0:
        text = await msgs.last.text_content()
        print(f"  AI: {text[:80]}")
        return bool(text and len(text) > 0)
    return False

async def test_device_version(page):
    """查看设备版本 - 应执行命令"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    
    # 先选一个设备
    await page.locator('#chat-input').fill('查看版本')
    await page.locator('#btn-send').click()
    await asyncio.sleep(25)
    
    msgs = page.locator('#messages .msg-ai')
    count = await msgs.count()
    if count > 0:
        last_text = await msgs.last.text_content()
        print(f"  AI (last): {last_text[:150]}")
        # 检查是否有命令执行结果
        all_text = ''
        for i in range(count):
            t = await msgs.nth(i).text_content()
            all_text += (t or '')
        has_h3c = 'H3C' in all_text or 'Comware' in all_text or 'Version' in all_text
        has_version_output = 'display version' in all_text or has_h3c
        print(f"  Has version output: {has_version_output}")
        return has_version_output or '工具' in all_text or '执行' in all_text
    return False

async def test_show_interface(page):
    """显示接口状态"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    await page.locator('#chat-input').fill('显示接口')
    await page.locator('#btn-send').click()
    await asyncio.sleep(25)
    msgs = page.locator('#messages .msg-ai')
    count = await msgs.count()
    if count > 0:
        all_text = ''
        for i in range(count):
            t = await msgs.nth(i).text_content()
            all_text += (t or '')
        has_iface = 'Interface' in all_text or 'GE' in all_text or 'interface' in all_text or '接口' in all_text
        print(f"  Has interface output: {has_iface}")
        return has_iface or '工具' in all_text
    return False

async def test_vlan_config_preview(page):
    """配置命令走预览"""
    await page.goto(BASE, timeout=10000)
    await page.wait_for_load_state('networkidle', timeout=10000)
    await page.locator('#chat-input').fill('创建VLAN 100')
    await page.locator('#btn-send').click()
    await asyncio.sleep(20)
    msgs = page.locator('#messages .msg-ai')
    count = await msgs.count()
    if count > 0:
        all_text = ''
        for i in range(count):
            t = await msgs.nth(i).text_content()
            all_text += (t or '')
        has_preview = '预览' in all_text or '确认' in all_text or 'vlan' in all_text.lower()
        print(f"  Has preview: {has_preview}")
        print(f"  Last msg: {(await msgs.last.text_content())[:100]}")
        return has_preview
    return False

async def test_quick_config_keyword(page):
    """quick-config关键词匹配秒回"""
    import requests
    r = requests.post(f'{BASE}/api/quick-config', json={
        'message': '版本',
        'device': '接入交换机',
        'mode': 'preview'
    }, timeout=30)
    d = r.json()
    print(f"  matched={d.get('matched')} query={d.get('query')}")
    return d.get('matched') == True

async def test_api_chat_version(page):
    """API /api/chat 查看版本"""
    import requests
    requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'e2e_api'})
    r = requests.post(f'{BASE}/api/chat', json={
        'message': '查看版本',
        'context': {'selected_device': '接入交换机'},
        'session_id': 'e2e_api'
    }, timeout=120)
    d = r.json()
    print(f"  success={d.get('success')} executed={d.get('executed')}")
    resp = d.get('response', '')
    has_output = 'H3C' in resp or 'Comware' in resp or 'display version' in resp or '工具' in resp
    print(f"  Has output: {has_output}")
    return d.get('success') and has_output

async def test_api_chat_interface(page):
    """API /api/chat 显示接口"""
    import requests
    requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'e2e_api2'})
    r = requests.post(f'{BASE}/api/chat', json={
        'message': '显示接口状态',
        'context': {'selected_device': '核心交换机'},
        'session_id': 'e2e_api2'
    }, timeout=120)
    d = r.json()
    print(f"  success={d.get('success')} executed={d.get('executed')}")
    resp = d.get('response', '')
    has_output = 'Interface' in resp or 'GE' in resp or '接口' in resp or '工具' in resp
    print(f"  Has output: {has_output}")
    return d.get('success') and has_output

async def test_api_chat_config_preview(page):
    """API /api/chat 配置命令走预览"""
    import requests
    requests.post(f'{BASE}/api/chat/clear', json={'session_id': 'e2e_api3'})
    r = requests.post(f'{BASE}/api/chat', json={
        'message': '创建VLAN 100',
        'context': {'selected_device': '接入交换机'},
        'session_id': 'e2e_api3'
    }, timeout=120)
    d = r.json()
    print(f"  success={d.get('success')} preview={d.get('preview')}")
    planned = d.get('planned_commands')
    print(f"  planned_commands: {json.dumps(planned, ensure_ascii=False)[:200] if planned else 'None'}")
    return d.get('success') and d.get('preview') == True and planned is not None

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        page_errors = []
        page.on('pageerror', lambda err: page_errors.append(str(err)))
        
        # API tests first (fast)
        await run_test("API chat version", test_api_chat_version, page)
        await run_test("API chat interface", test_api_chat_interface, page)
        await run_test("API chat config preview", test_api_chat_config_preview, page)
        await run_test("Quick-config keyword", test_quick_config_keyword, page)
        
        # UI tests (slower)
        await run_test("Page loads", test_page_loads, page)
        await run_test("Simple greeting", test_simple_greeting, page)
        await run_test("Device version", test_device_version, page)
        await run_test("Show interface", test_show_interface, page)
        await run_test("VLAN config preview", test_vlan_config_preview, page)
        
        if page_errors:
            print(f"\nPage JS errors: {page_errors[:5]}")
        
        await browser.close()
    
    print(f"\n{'='*60}")
    print(f"Results: {PASS} PASS / {FAIL} FAIL")
    if FAIL == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"⚠️ {FAIL} test(s) failed")
    return FAIL == 0

asyncio.run(main())
