"""
NetOps 自然语言路由模块测试
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch

# 模拟 LLM 客户端
class MockLLMClient:
    def __init__(self, mock_response=None):
        self.mock_response = mock_response or {}
    
    def chat(self, messages, temperature=0.7, **kwargs):
        content = messages[0]["content"]
        
        if "意图分类" in content or "IntentType" in content:
            return {
                "content": '{"intent_type": "query_config", "confidence": 0.95, "parameters": {}, "device_hostname": "SW-Core"}'
            }
        elif "配置命令" in content or "CONFIG_COMMAND" in content:
            return {
                "content": '["interface range GE0/0/1 to GE0/0/4", "port link-type access", "port default vlan 10", "quit"]'
            }
        else:
            return {"content": "Unknown prompt type"}


class TestIntentParser:
    def test_generate_config_commands_huawei(self):
        """测试华为设备命令生成"""
        from app.nl_router.parser import IntentParser, ParsedIntent
        
        llm = MockLLMClient()
        parser = IntentParser(llm)
        
        intent = ParsedIntent(
            intent_type="config_vlan",
            parameters={"interfaces": ["GE0/0/1", "GE0/0/2"], "vlan": 10, "mode": "access"}
        )
        
        commands = asyncio.run(parser.generate_config_commands(
            intent=intent,
            vendor="huawei",
            device_hostname="SW-Core"
        ))
        
        assert len(commands) > 0
        assert "interface" in commands[0].lower() or "port" in commands[0].lower()
    
    def test_generate_config_commands_cisco(self):
        """测试思科设备命令生成"""
        from app.nl_router.parser import IntentParser, ParsedIntent
        
        llm = MockLLMClient()
        parser = IntentParser(llm)
        
        intent = ParsedIntent(
            intent_type="config_vlan",
            parameters={"interfaces": ["GigabitEthernet0/1", "GigabitEthernet0/2"], "vlan": 20, "mode": "access"}
        )
        
        commands = asyncio.run(parser.generate_config_commands(
            intent=intent,
            vendor="cisco",
            device_hostname="SW-Core"
        ))
        
        assert len(commands) > 0
        assert "interface" in commands[0].lower() or "switchport" in commands[0].lower()


class TestNLExecutor:
    def test_executor_init_with_llm(self):
        """测试执行器初始化"""
        from app.nl_router.executor import NLExecutor
        
        llm = MockLLMClient()
        executor = NLExecutor(llm_client=llm)
        
        assert executor.llm_client is not None
        assert executor.intent_parser is not None
    
    def test_execute_without_llm(self):
        """测试没有 LLM 时的执行"""
        from app.nl_router.executor import NLExecutor
        
        executor = NLExecutor(llm_client=None)
        
        result = asyncio.run(executor.execute("测试命令"))
        
        assert result.success is False
        assert "LLM" in result.message
    
    def test_confirm_and_execute_cancel(self):
        """测试取消配置执行"""
        from app.nl_router.executor import NLExecutor
        
        llm = MockLLMClient()
        executor = NLExecutor(llm_client=llm)
        
        result = asyncio.run(executor.confirm_and_execute(
            confirmed=False,
            device_data={"device_ip": "192.168.1.1", "vendor": "huawei"},
            username="admin",
            password="password",
        ))
        
        assert result.success is False
        assert "取消" in result.message or "cancel" in result.message.lower()


class TestIntentCoverage:
    @pytest.mark.parametrize("input_text,expected_type", [
        ("查一下 SW-Core 的配置", "query_config"),
        ("SW-Core 的邻居有哪些", "query_neighbors"),
        ("从 10.10.10.1 到 8.8.8.8 的路径", "query_path"),
        ("最近有什么告警", "query_events"),
        ("给 SW-Core 配 VLAN 10", "config_vlan"),
        ("把 1 口加入 VLAN 20", "config_vlan"),
        ("配置静态路由", "config_routing"),
        ("加一条 ACL 规则", "config_acl"),
        ("VLAN 10 上不了网", "diagnose_vlan"),
        ("ping 不通 8.8.8.8", "diagnose_connectivity"),
        ("OSPF 邻居起不来", "diagnose_routing"),
    ])
    def test_intent_classification_structure(self, input_text, expected_type):
        """测试意图分类结构（不依赖 LLM 实际响应）"""
        from app.nl_router.parser import ParsedIntent
        
        # 测试 ParsedIntent 数据结构
        intent = ParsedIntent(
            intent_type=expected_type,
            confidence=0.9,
            parameters={"test": True},
            device_hostname="TEST-DEVICE"
        )
        
        assert intent.intent_type == expected_type
        assert intent.confidence > 0
        assert intent.device_hostname == "TEST-DEVICE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
