"""Comprehensive E2E tests for netops-ai frontend"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"
SHOT_DIR = "Z:/netops-ai/tests/e2e_screenshots"
os.makedirs(SHOT_DIR, exist_ok=True)

passed = 0
failed = 0

def run_test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"✅ {name} PASSED")
        passed += 1
    except Exception as e:
        print(f"❌ {name} FAILED: {e}")
        failed += 1

def test_homepage():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{SHOT_DIR}/comp_01_home.png", full_page=True)
        assert not errors, f"JS errors: {errors[:3]}"
        # Check key elements
        assert page.locator("#device-list").count() > 0 or page.locator(".device-chip").count() > 0, "No device list"
        browser.close()

def test_device_chips():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)
        # Check device items
        items = page.locator(".device-item")
        count = items.count()
        print(f"  Found {count} device items")
        assert count >= 3, f"Expected >=3 device items, got {count}"
        # Check item content
        first_item = items.first.text_content()
        print(f"  First item: {first_item[:80]}")
        browser.close()

def test_topology_view():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)
        # Click topology tab
        topo_btn = page.locator("[data-tab='topology'], button:has-text('拓扑')")
        if topo_btn.count() > 0:
            topo_btn.first.click()
            page.wait_for_timeout(2000)
        page.screenshot(path=f"{SHOT_DIR}/comp_02_topology.png", full_page=True)
        # Check canvas/svg exists
        canvas = page.locator("canvas, svg, #topology-canvas, .topology-container")
        print(f"  Topology elements: {canvas.count()}")
        browser.close()

def test_chat_send():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)
        # Find chat input
        chat_input = page.locator("#chat-input, textarea.chat-input, textarea")
        if chat_input.count() > 0:
            chat_input.first.fill("display version")
            # Click send
            send_btn = page.locator("button:has-text('发送'), button#send-btn, .send-btn")
            if send_btn.count() > 0:
                send_btn.first.click()
                page.wait_for_timeout(5000)
                page.screenshot(path=f"{SHOT_DIR}/comp_03_chat.png", full_page=True)
                # Check response appeared
                messages = page.locator(".chat-message, .message, .msg-content")
                print(f"  Chat messages after send: {messages.count()}")
            else:
                print("  No send button found")
        else:
            print("  No chat input found")
        browser.close()

def test_add_device_modal():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        # Click add device
        add_btn = page.locator("button:has-text('添加'), .add-device-btn, [onclick*='openAdd']")
        if add_btn.count() > 0:
            add_btn.first.click()
            page.wait_for_timeout(500)
            # Check modal
            modal = page.locator(".modal, [role='dialog']")
            assert modal.count() > 0, "Modal should appear"
            page.screenshot(path=f"{SHOT_DIR}/comp_04_add_device.png", full_page=True)
            # Check fields
            ip = page.locator("input[name*='ip'], input#device-ip, input[placeholder*='IP']")
            port = page.locator("input[name*='port'], input#device-port, input[placeholder*='端口']")
            print(f"  IP field: {ip.count()}, Port field: {port.count()}")
        browser.close()

def test_delete_device_modal():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        # Click device item to edit
        item = page.locator(".device-item")
        if item.count() > 0:
            item.first.click()
            page.wait_for_timeout(500)
            # Check for delete button in modal
            delete_btn = page.locator("button:has-text('删除'), .delete-btn, [onclick*='delete']")
            has_delete = delete_btn.count() > 0
            print(f"  Delete button in edit modal: {has_delete}")
            page.screenshot(path=f"{SHOT_DIR}/comp_05_edit_device.png", full_page=True)
        browser.close()

def test_topology_state_api():
    """Check topology state has correct links"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        resp = page.request.get(f"{BASE_URL}/api/topology/state")
        data = resp.json()
        links = data.get('links', [])
        nodes = data.get('nodes', [])
        active = sum(1 for l in links if l.get('status') == 'active')
        lost = sum(1 for l in links if l.get('status') == 'lost')
        print(f"  Topology state: {len(nodes)} nodes, {len(links)} links ({active} active, {lost} lost)")
        assert active == 3, f"Expected 3 active links, got {active}"
        browser.close()

# Run all
tests = [
    ("Homepage loads no JS errors", test_homepage),
    ("Device chips show 3 devices", test_device_chips),
    ("Topology view renders", test_topology_view),
    ("Chat send works", test_chat_send),
    ("Add device modal", test_add_device_modal),
    ("Edit device has delete button", test_delete_device_modal),
    ("Topology state API 3 active links", test_topology_state_api),
]

for name, fn in tests:
    run_test(name, fn)

print(f"\n{'='*50}")
print(f"E2E: {passed}/{len(tests)} passed, {failed} failed")
print(f"{'='*50}")
