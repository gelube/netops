"""Debug: check what frontend actually gets from topology/state API"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Intercept API responses
        api_data = {}
        async def handle_response(response):
            if '/api/topology/state' in response.url:
                try:
                    api_data['topology'] = await response.json()
                except:
                    pass
            if '/api/devices' in response.url and 'ping' not in response.url:
                try:
                    api_data['devices'] = await response.json()
                except:
                    pass
        
        page.on('response', handle_response)
        await page.goto('http://127.0.0.1:5000', timeout=10000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        await asyncio.sleep(2)
        
        # Evaluate JS to check what the frontend sees
        result = await page.evaluate('''() => {
            const nodes = document.querySelectorAll('.topo-node');
            const info = [];
            nodes.forEach(n => {
                const status = n.querySelector('.node-status');
                const remark = n.querySelector('.node-remark');
                info.push({
                    name: remark ? remark.textContent : '?',
                    statusClass: status ? status.className : '?'
                });
            });
            return info;
        }''')
        print("Frontend nodes:")
        for r in result:
            print(f"  {r['name']}: {r['statusClass']}")
        
        # Check API data
        if 'topology' in api_data:
            for n in api_data['topology'].get('nodes', []):
                lc = n.get('facts', {}).get('last_collected', '?')
                print(f"API node {n.get('remark','?')} last_collected={lc}")
        
        await browser.close()

asyncio.run(main())
