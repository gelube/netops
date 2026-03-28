import asyncio
from copaw.providers.provider_manager import ProviderManager

async def main():
    pm = ProviderManager()
    print("当前模型:", pm.get_active_model())
    
    # 切换到 aliyun-codingplan 的 qwen3.5-plus
    await pm.activate_model('aliyun-codingplan', 'qwen3.5-plus')
    print("新模型:", pm.get_active_model())

asyncio.run(main())