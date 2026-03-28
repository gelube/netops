#!/usr/bin/env python3
"""
测试意图解析器
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.llm.config import LLMConfig, LLMClient
from app.nl_router.parser import IntentParser


# 测试用例
TEST_CASES = [
    # MCP 工具调用类
    ("查一下 SW-Core 的配置", "query_config"),
    ("SW-Core 的邻居有哪些", "query_neighbors"),
    ("查看最近的告警事件", "query_events"),
    ("从 10.10.10.1 到 8.8.8.8 的路径是什么", "query_path"),
    ("搜索核心交换机", "query_device"),
    ("对 SW-Core 运行诊断", "run_diagnosis"),
    
    # 本地配置执行类
    ("给 SW-Core 的 1-4 口配 VLAN 10", "config_vlan"),
    ("把 GE0/0/1 的 IP 改成 192.168.1.1", "config_interface"),
    ("添加一条默认路由到 10.0.0.1", "config_routing"),
    ("禁止 192.168.1.100 访问服务器", "config_acl"),
    
    # 故障排查类
    ("VLAN 10 上不了网", "diagnose_vlan"),
    ("路由不通，帮我查一下", "diagnose_routing"),
    ("为什么 ping 不通网关", "diagnose_connectivity"),
]


async def test_parser():
    """测试意图解析"""
    
    # 配置 LLM（根据实际情况修改）
    llm_config = LLMConfig(
        provider="openai",
        endpoint="http://localhost:11434/v1",  # Ollama
        api_key="ollama",
        model="qwen2.5:7b"
    )
    
    # 测试连接
    print("🔍 测试 LLM 连接...")
    try:
        llm_client = LLMClient(llm_config)
        models = llm_client.list_models()
        print(f"✅ LLM 连接成功，可用模型：{models[:5]}")
    except Exception as e:
        print(f"❌ LLM 连接失败：{e}")
        print("请修改 test_nl_parser.py 中的 LLM 配置")
        return
    
    # 初始化解析器
    parser = IntentParser(llm_client)
    
    # 执行测试
    print("\n" + "="*60)
    print("开始测试意图解析")
    print("="*60 + "\n")
    
    passed = 0
    failed = 0
    
    for user_input, expected_intent in TEST_CASES:
        print(f"输入：{user_input}")
        print(f"期望：{expected_intent}")
        
        try:
            result = await parser.parse(user_input)
            actual_intent = result.intent_type
            
            if actual_intent == expected_intent:
                print(f"✅ 通过 (置信度：{result.confidence})")
                passed += 1
            else:
                print(f"❌ 失败 - 实际：{actual_intent}")
                failed += 1
            
            # 打印详细参数
            if result.parameters:
                print(f"   参数：{result.parameters}")
            if result.mcp_tool:
                print(f"   MCP 工具：{result.mcp_tool}")
        
        except Exception as e:
            print(f"❌ 异常：{e}")
            failed += 1
        
        print("-"*60)
    
    # 统计
    print("\n" + "="*60)
    print(f"测试完成：通过 {passed}/{len(TEST_CASES)}, 失败 {failed}/{len(TEST_CASES)}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_parser())
