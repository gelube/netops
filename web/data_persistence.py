"""
NetOps AI 配置持久化模块
保存和加载设备拓扑、LLM配置等数据
"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path("Z:/netops-ai/web/data")
CONFIG_DIR.mkdir(exist_ok=True)

TOPOLOGY_FILE = CONFIG_DIR / "topology.json"
LLM_CONFIG_FILE = CONFIG_DIR / "llm_config.json"

def save_topology(topology_data):
    """保存拓扑数据"""
    try:
        with open(TOPOLOGY_FILE, 'w', encoding='utf-8') as f:
            json.dump(topology_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存拓扑失败: {e}")
        return False

def load_topology():
    """加载拓扑数据"""
    try:
        if TOPOLOGY_FILE.exists():
            with open(TOPOLOGY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载拓扑失败: {e}")
    return None

def save_llm_config(config_data):
    """保存LLM配置"""
    try:
        # 不保存敏感信息
        save_data = {
            'provider': config_data.get('provider'),
            'endpoint': config_data.get('endpoint'),
            'api_key': config_data.get('api_key', ''),
            'model': config_data.get('model')
        }
        with open(LLM_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存LLM配置失败: {e}")
        return False

def load_llm_config():
    """加载LLM配置"""
    try:
        if LLM_CONFIG_FILE.exists():
            with open(LLM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载LLM配置失败: {e}")
    return None
