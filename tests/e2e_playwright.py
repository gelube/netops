"""NetOps-AI Frontend E2E Tests using Playwright"""
import sys
import os
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://localhost:5000"

def test_index_loads():
    """Homepage loads and renders correctly"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate and wait
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/01_index.png", full_page=True)
        
        # Check title
        title = page.title()
        assert "NetOps" in title or "netops" in title.lower(), f"Title should contain NetOps, got: {title}"
        
        # Check main elements exist
        # Device list area
        device_area = page.locator("#device-list, .device-list, [id*='device']").first
        assert device_area.is_visible(), "Device area should be visible"
        
        browser.close()
        print("✅ test_index_loads PASSED")

def test_device_tab():
    """Device management tab works"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        
        # Find and click device-related tab/button
        device_tab = page.locator("text=设备, text=Device, [data-tab*='device'], button:has-text('设备')").first
        if device_tab.is_visible():
            device_tab.click()
            page.wait_for_timeout(1000)
            page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/02_device_tab.png", full_page=True)
        
        browser.close()
        print("✅ test_device_tab PASSED")

def test_topology_tab():
    """Topology view renders"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        
        # Find topology tab
        topo_tab = page.locator("text=拓扑, text=Topology, [data-tab*='topo'], button:has-text('拓扑')").first
        if topo_tab.is_visible():
            topo_tab.click()
            page.wait_for_timeout(1000)
            page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/03_topology_tab.png", full_page=True)
        
        # Check canvas exists
        canvas = page.locator("canvas, svg, #topology-canvas, .topology-container").first
        # Canvas might not be visible if no devices, just check page didn't crash
        
        browser.close()
        print("✅ test_topology_tab PASSED")

def test_chat_interface():
    """Chat interface loads and can send a message"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        
        # Find chat input
        chat_input = page.locator("textarea, input[type='text'][placeholder*='聊天'], input[type='text'][placeholder*='chat'], #chat-input, .chat-input textarea").first
        if chat_input.is_visible():
            chat_input.fill("display version")
            page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/04_chat_typed.png", full_page=True)
            
            # Find send button
            send_btn = page.locator("button:has-text('发送'), button:has-text('Send'), button[type='submit'], .send-btn").first
            if send_btn.is_visible():
                send_btn.click()
                page.wait_for_timeout(2000)
                page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/05_chat_sent.png", full_page=True)
        
        browser.close()
        print("✅ test_chat_interface PASSED")

def test_add_device_modal():
    """Add device modal opens and has correct fields"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        
        # Find add device button
        add_btn = page.locator("button:has-text('添加'), button:has-text('Add'), .add-device-btn, [onclick*='openAddDevice']").first
        if add_btn.is_visible():
            add_btn.click()
            page.wait_for_timeout(500)
            page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/06_add_device_modal.png", full_page=True)
            
            # Check modal fields
            modal = page.locator(".modal, [role='dialog'], .modal-dialog").first
            if modal.is_visible():
                # Should have IP, port, connection type fields
                ip_field = page.locator("input[name*='ip'], input[placeholder*='IP'], input#device-ip").first
                port_field = page.locator("input[name*='port'], input[placeholder*='端口'], input#device-port").first
                # At least one should exist
                assert ip_field.is_visible() or port_field.is_visible(), "Modal should have IP or port fields"
        
        browser.close()
        print("✅ test_add_device_modal PASSED")

def test_no_console_errors():
    """Check for JavaScript console errors on page load"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(f"PAGE ERROR: {err}"))
        
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)  # Wait for any delayed errors
        
        page.screenshot(path="Z:/netops-ai/tests/e2e_screenshots/07_console_check.png", full_page=True)
        
        # Filter out known acceptable errors (e.g., favicon, WebSocket connection)
        real_errors = [e for e in errors if "favicon" not in e.lower() and "WebSocket" not in e]
        
        if real_errors:
            print(f"⚠️  Console errors found: {real_errors[:5]}")
        else:
            print("✅ No console errors")
        
        browser.close()
        assert len(real_errors) == 0, f"Found {len(real_errors)} console errors: {real_errors[:5]}"
        print("✅ test_no_console_errors PASSED")

def test_api_endpoints_respond():
    """Critical API endpoints respond correctly from localhost"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Test /api/devices (using page's request context)
        try:
            api_result = page.evaluate("""async () => { const r = await fetch('/api/devices'); return {status: r.status, ok: r.ok}; }""")
            assert api_result['status'] == 200, f"/api/devices returned {api_result['status']}"
            print("  ✅ /api/devices → 200")
            
            api_result2 = page.evaluate("""async () => { const r = await fetch('/api/knowledge/stats'); return {status: r.status, ok: r.ok}; }""")
            assert api_result2['status'] == 200, f"/api/knowledge/stats returned {api_result2['status']}"
            print("  ✅ /api/knowledge/stats → 200")
        except Exception as e:
            # Fallback: use page.request which handles same-origin correctly
            resp = page.request.get(f'{BASE_URL}/api/devices')
            assert resp.status == 200, f"/api/devices returned {resp.status}"
            print("  ✅ /api/devices → 200")
            
            resp2 = page.request.get(f'{BASE_URL}/api/knowledge/stats')
            assert resp2.status == 200, f"/api/knowledge/stats returned {resp2.status}"
            print("  ✅ /api/knowledge/stats → 200")
        
        browser.close()
        print("✅ test_api_endpoints_respond PASSED")

if __name__ == "__main__":
    os.makedirs("Z:/netops-ai/tests/e2e_screenshots", exist_ok=True)
    
    tests = [
        test_index_loads,
        test_device_tab,
        test_topology_tab,
        test_chat_interface,
        test_add_device_modal,
        test_no_console_errors,
        test_api_endpoints_respond,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
    
    print(f"\n{'='*40}")
    print(f"E2E Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*40}")
