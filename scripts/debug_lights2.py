"""Debug: run the exact JS logic in browser context"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('http://127.0.0.1:5000', timeout=10000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        await asyncio.sleep(2)
        
        result = await page.evaluate('''() => {
            // Check topologyState nodes
            if (typeof topologyState === 'undefined') return 'topologyState undefined';
            const nodes = topologyState.nodes || [];
            return nodes.map(n => {
                const lc = n.facts && n.facts.last_collected;
                const ls = lc ? new Date(lc).getTime() : 0;
                const online = ls && (Date.now() - ls < 3600000);
                return {
                    name: n.remark || n.name,
                    last_collected: lc,
                    timestamp: ls,
                    diff_ms: Date.now() - ls,
                    online: online
                };
            });
        }''')
        print("topologyState nodes:")
        for r in result:
            print(f"  {r['name']}: lc={r['last_collected'][:25] if r['last_collected'] else 'None'} diff={r['diff_ms']}ms online={r['online']}")
        
        await browser.close()

asyncio.run(main())
