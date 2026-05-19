"""E2E test for chat - with screenshots"""
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
        
        print("1. Loading page...")
        await page.goto('http://127.0.0.1:5000', timeout=10000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        
        # Screenshot initial state
        await page.screenshot(path='Z:/netops-ai/tests/e2e_screenshots/chat_01_initial.png')
        print("   Screenshot saved: chat_01_initial.png")
        
        # Check what tabs/buttons exist
        tabs = page.locator('.tab-btn, [data-tab], nav button, .nav-btn')
        tab_count = await tabs.count()
        print(f"   Tab buttons found: {tab_count}")
        for i in range(min(tab_count, 10)):
            txt = await tabs.nth(i).text_content()
            print(f"     Tab {i}: {txt}")
        
        # Look for chat panel
        chat_panel = page.locator('#chat-panel, #chat, .chat-panel, .chat-section')
        panel_count = await chat_panel.count()
        print(f"   Chat panels found: {panel_count}")
        
        # Check if chat-input exists
        chat_input = page.locator('#chat-input')
        input_visible = await chat_input.is_visible()
        print(f"   Chat input visible: {input_visible}")
        
        # Try clicking chat tab if exists
        chat_tab = page.locator('text=对话').first
        if await chat_tab.is_visible():
            print("   Clicking chat tab...")
            await chat_tab.click()
            await asyncio.sleep(1)
            await page.screenshot(path='Z:/netops-ai/tests/e2e_screenshots/chat_02_after_tab.png')
        
        # Check chat input again
        input_visible = await chat_input.is_visible()
        print(f"   Chat input visible after tab click: {input_visible}")
        
        if input_visible:
            print("\n2. Typing message...")
            await chat_input.fill('你好')
            await page.screenshot(path='Z:/netops-ai/tests/e2e_screenshots/chat_03_typed.png')
            
            print("3. Clicking send...")
            await page.locator('#btn-send').click()
            
            # Wait for response
            print("4. Waiting 30s for response...")
            await asyncio.sleep(30)
            await page.screenshot(path='Z:/netops-ai/tests/e2e_screenshots/chat_04_response.png')
            
            # Check chat messages
            chat_msgs = page.locator('.chat-msg')
            msg_count = await chat_msgs.count()
            print(f"   Chat messages: {msg_count}")
            for i in range(min(msg_count, 5)):
                cls = await chat_msgs.nth(i).get_attribute('class')
                txt = await chat_msgs.nth(i).text_content()
                print(f"   Msg {i}: class={cls}, text={txt[:100] if txt else 'EMPTY'}")
        else:
            print("   Chat input NOT visible! Taking screenshot...")
            await page.screenshot(path='Z:/netops-ai/tests/e2e_screenshots/chat_02_no_input.png')
        
        if errors:
            print(f"\n   JS Errors: {errors[:10]}")
        
        await browser.close()
        print("\nDone!")

asyncio.run(test_chat())
