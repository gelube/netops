"""E2E test for chat - using Playwright"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio

async def test_chat():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Collect console errors
        errors = []
        page.on('console', lambda msg: errors.append(f'[CONSOLE {msg.type}] {msg.text}') if msg.type in ('error', 'warning') else None)
        page.on('pageerror', lambda err: errors.append(f'[PAGE ERROR] {err}'))
        
        print("1. Loading page...")
        await page.goto('http://127.0.0.1:5000', timeout=10000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        print(f"   Title: {await page.title()}")
        
        # Check for JS errors
        if errors:
            print(f"   JS Errors on load: {errors[:5]}")
        
        # Type a message
        print("\n2. Typing chat message...")
        chat_input = page.locator('#chat-input')
        await chat_input.fill('你好')
        
        # Click send
        print("3. Clicking send...")
        send_btn = page.locator('#btn-send')
        await send_btn.click()
        
        # Wait for AI response
        print("4. Waiting for response...")
        try:
            # Wait up to 60s for an AI message to appear
            await page.wait_for_selector('.chat-msg.ai', timeout=60000)
            msgs = page.locator('.chat-msg.ai')
            count = await msgs.count()
            print(f"   AI messages appeared: {count}")
            if count > 0:
                last = msgs.nth(count - 1)
                text = await last.text_content()
                print(f"   Last AI msg: {text[:200] if text else 'EMPTY'}")
        except Exception as e:
            print(f"   Timeout waiting for AI response: {e}")
            # Check chat-messages container
            chat_container = page.locator('#chat-messages')
            html = await chat_container.inner_html()
            print(f"   Chat container HTML (first 500): {html[:500]}")
        
        # Check for any new errors
        if errors:
            print(f"\n   All JS errors: {errors}")
        
        await browser.close()
        print("\nTest complete!")

asyncio.run(test_chat())
