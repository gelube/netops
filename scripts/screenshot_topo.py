"""Screenshot the topology to check lights"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        await page.goto('http://127.0.0.1:5000', timeout=10000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        # Wait a bit for rendering
        await asyncio.sleep(2)
        await page.screenshot(path=r'Z:\netops-ai\screenshot.png', full_page=True)
        
        # Check node status elements
        status_els = await page.query_selector_all('.node-status')
        for el in status_els:
            cls = await el.get_attribute('class')
            print(f"node-status class: {cls}")
        
        # Check chip elements
        chips = await page.query_selector_all('.chip.ok')
        print(f"Found {len(chips)} ok chips")
        
        await browser.close()

asyncio.run(main())
