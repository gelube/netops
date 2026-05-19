"""E2E test for chat - check actual DOM"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio

async def test_chat():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        errors = []
        page.on('console', lambda msg: errors.append(f'[{msg.type}] {msg.text}') if msg.type in ('error', 'warning') else None)
        page.on('pageerror', lambda err: errors.append(f'[PAGE_ERROR] {err}'))
        
        await page.goto('http://127.0.0.1:5000', timeout=10000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        
        # Type and send
        await page.locator('#chat-input').fill('你好')
        await page.locator('#btn-send').click()
        
        # Wait a bit
        await asyncio.sleep(15)
        
        # Check ALL elements in messages box
        messages_box = page.locator('#messages')
        box_html = await messages_box.inner_html()
        print(f"Messages box HTML (first 1000): {box_html[:1000]}")
        print(f"Messages box HTML length: {len(box_html)}")
        
        # Also check input state
        chat_input = page.locator('#chat-input')
        input_value = await chat_input.input_value()
        print(f"Input value after send: '{input_value}'")
        
        # Check btn-send visibility
        send_btn = page.locator('#btn-send')
        stop_btn = page.locator('#btn-stop')
        print(f"Send btn visible: {await send_btn.is_visible()}")
        print(f"Stop btn visible: {await stop_btn.is_visible()}")
        
        # Check _chatBusy state
        chat_busy = await page.evaluate('() => window._chatBusy')
        print(f"_chatBusy: {chat_busy}")
        
        if errors:
            print(f"\nJS Errors: {errors[:10]}")
        
        await browser.close()

asyncio.run(test_chat())
