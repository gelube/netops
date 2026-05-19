"""NetOps-AI Frontend E2E Tests v2 - fixed cache + fetch issues"""
import sys
import os
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"

def test_all():
    os.makedirs("Z:/netops-ai/tests/e2e_screenshots", exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            bypass_csp=True,
            ignore_https_errors=True,
        )
        page = ctx.new_page()
        
        # Clear cache
        errors = []
        def on_pageerror(err):
            errors.append(('PAGE_ERROR', str(err)))
        def on_console(msg):
            if msg.type == 'error':
                errors.append(('CONSOLE', msg.text[:200]))
        page.on('pageerror', on_pageerror)
        page.on('console', on_console)
        
        # Hard reload with cache bypass
        page.goto(BASE_URL, wait_until='networkidle', timeout=15000)
        page.reload(wait_until='networkidle', timeout=15000)
        page.wait_for_timeout(2000)
        page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/v2_index.png", full_page=True)
        
        # Test 1: Page title
        title = page.title()
        print(f"Title: {title}")
        
        # Test 2: JS works
        try:
            result = page.evaluate("1+1")
            print(f"JS eval works: 1+1 = {result}")
        except Exception as e:
            print(f"JS eval broken: {e}")
        
        # Test 3: API fetch from page context (same origin)
        try:
            api_result = page.evaluate("""async () => {
                const r = await fetch('/api/devices');
                return {status: r.status, ok: r.ok};
            }""")
            print(f"API /devices: status={api_result['status']}, ok={api_result['ok']}")
        except Exception as e:
            print(f"API fetch failed: {e}")
        
        # Test 4: Check for console errors
        real_errors = [e for e in errors if 'favicon' not in e[1].lower() and 'websocket' not in e[1].lower()]
        if real_errors:
            print(f"\nConsole errors ({len(real_errors)}):")
            for kind, msg in real_errors[:10]:
                print(f"  {kind}: {msg[:150]}")
        else:
            print("\nNo console errors!")
        
        # Test 5: Device tab
        device_tab = page.locator("text=设备, [data-tab*='device'], button:has-text('设备')").first
        if device_tab.is_visible():
            device_tab.click()
            page.wait_for_timeout(500)
            page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/v2_devices.png", full_page=True)
            print("Device tab: OK")
        else:
            print("Device tab: not found (may be default view)")
        
        # Test 6: Topology tab
        topo_tab = page.locator("text=拓扑, [data-tab*='topo'], button:has-text('拓扑')").first
        if topo_tab.is_visible():
            topo_tab.click()
            page.wait_for_timeout(500)
            page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/v2_topology.png", full_page=True)
            print("Topology tab: OK")
        
        # Test 7: Chat area visible
        chat_input = page.locator("textarea, input[type='text'][placeholder*='聊天'], #chat-input, .chat-input textarea").first
        chat_visible = chat_input.is_visible()
        print(f"Chat input visible: {chat_visible}")
        
        # Test 8: Add device button
        add_btn = page.locator("button:has-text('添加'), .add-device-btn, [onclick*='openAddDevice']").first
        add_visible = add_btn.is_visible()
        print(f"Add device button visible: {add_visible}")
        
        # Summary
        print(f"\n{'='*50}")
        print(f"Console errors: {len(real_errors)}")
        print(f"JS works: {'YES' if 'result' in dir() else 'NO'}")
        print(f"API works: {'YES' if api_result and api_result.get('ok') else 'NO'}")
        print(f"{'='*50}")
        
        browser.close()

if __name__ == "__main__":
    test_all()
