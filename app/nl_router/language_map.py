#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通俗语言 → 专业术语映射
帮助非专业用户的自然语言理解
"""
from typing import Dict, Optional, Any
import re
import json
import os


class LanguageMapper:
    """通俗语言映射器"""
    
    def __init__(self, config_path: Optional[str] = None):
        # 部门/区域 → VLAN ID 映射（可配置）
        self.department_vlan_map = self._load_departments(config_path)
        
        # 位置 → 接口范围映射（可配置）
        self.location_interface_map = self._load_locations(config_path)
        
        # 加载默认值（如果配置文件不存在）
        if not self.department_vlan_map:
            self.department_vlan_map = {
                "财务": 10, "财务室": 10, "财务部": 10,
                "人事": 20, "人事部": 20, "行政": 20, "行政部": 20,
                "技术": 30, "技术部": 30, "研发": 30, "研发部": 30,
                "访客": 100, "来宾": 100, "会议室": 100,
                "监控": 200, "监控室": 200, "安防": 200,
            }
        
        if not self.location_interface_map:
            self.location_interface_map = {
                "1 楼": "1-12", "二楼": "13-24", "三楼": "25-36",
                "前台": "1-2", "前台网络": "1-2",
            }
        
        # 通俗说法 → 专业动作映射
        self.action_map = {
            "配": "config", "配置": "config", "开通": "config",
            "通上": "config", "通上网": "config",
            "开个口子": "config_interface", "开个端口": "config_interface",
            "封掉": "block", "封禁": "block", "禁止": "block",
            "允许": "allow", "放行": "allow",
            "上不了网": "no_internet", "连不上": "no_connection",
            "没网了": "no_internet", "网络断了": "no_internet",
            "不通": "unreachable", "ping 不通": "unreachable",
        }
        
        # 设备类型通俗说法
        self.device_type_map = {
            "主交换机": "core_switch", "核心交换机": "core_switch",
            "接入交换机": "access_switch", "路由器": "router",
            "防火墙": "firewall",
        }
    
    def _load_departments(self, config_path: Optional[str] = None) -> Dict[str, int]:
        """从配置文件加载部门-VLAN 映射"""
        if not config_path:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config", "departments.json"
            )
        
        if not os.path.exists(config_path):
            return {}
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("departments", {})
        except Exception:
            return {}
    
    def _load_locations(self, config_path: Optional[str] = None) -> Dict[str, str]:
        """从配置文件加载位置 - 接口映射"""
        if not config_path:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config", "departments.json"
            )
        
        if not os.path.exists(config_path):
            return {}
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("locations", {})
        except Exception:
            return {}
    
    def parse_user_input(self, user_input: str) -> Dict[str, Any]:
        """解析用户通俗语言"""
        result = {
            "intent_hints": {},
            "parameters": {},
            "extracted_info": {},
        }
        
        # 1. 提取部门/区域信息 → 推断 VLAN
        for dept, vlan_id in self.department_vlan_map.items():
            if dept in user_input:
                result["parameters"]["vlan_id"] = vlan_id
                result["extracted_info"]["department"] = dept
                result["extracted_info"]["department_vlan"] = vlan_id
                break
        
        # 2. 提取位置信息 → 推断接口范围
        for location, interface_range in self.location_interface_map.items():
            if location in user_input:
                result["parameters"]["interfaces"] = [interface_range]
                result["extracted_info"]["location"] = location
                break
        
        # 3. 提取接口范围（通俗说法）
        interface_patterns = [
            r"(\d+) 号 (?:口 | 端口)",
            r"(\d+) 到 (\d+) 号？(?:口 | 端口)",
            r"(\d+)-(\d+) 号？(?:口 | 端口)",
            r"前 (\d+) 个 (?:口 | 端口)",
            r"(\d+) 口",
        ]
        
        for pattern in interface_patterns:
            match = re.search(pattern, user_input)
            if match:
                if len(match.groups()) == 2:
                    start, end = match.groups()
                    result["parameters"]["interfaces"] = [f"{start}-{end}"]
                else:
                    result["parameters"]["interfaces"] = [match.group(1)]
                break
        
        # 4. 提取动作意图
        for phrase, action in self.action_map.items():
            if phrase in user_input:
                result["intent_hints"]["action"] = action
                break
        
        # 5. 提取 IP 地址
        ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        ip_matches = re.findall(ip_pattern, user_input)
        if ip_matches:
            result["extracted_info"]["ip_addresses"] = ip_matches
            
            if "封" in user_input or "禁" in user_input:
                result["parameters"]["target_ip"] = ip_matches[0]
            elif "源" in user_input or "从" in user_input:
                result["parameters"]["source_ip"] = ip_matches[0]
            elif "目标" in user_input or "到" in user_input:
                result["parameters"]["dest_ip"] = ip_matches[0]
        
        # 6. 提取设备名（中文）
        device_patterns = [
            r"(?:给 | 把 | 在)\s*([\w-]+)\s*(?:的 | 上 | 配 | 配个)",
            r"([\w-]+) 交换机", r"([\w-]+) 路由",
        ]
        
        for pattern in device_patterns:
            match = re.search(pattern, user_input)
            if match:
                result["parameters"]["device_hostname"] = match.group(1)
                break
        
        # 7. 提取网络名称
        network_patterns = [r"(\w+) 网络", r"(\w+) 的网"]
        for pattern in network_patterns:
            match = re.search(pattern, user_input)
            if match:
                network_name = match.group(1)
                result["extracted_info"]["network_name"] = network_name
                if network_name in self.department_vlan_map:
                    result["parameters"]["vlan_id"] = self.department_vlan_map[network_name]
                break
        
        return result
    
    def get_vlan_id_by_department(self, department: str) -> Optional[int]:
        """根据部门名获取 VLAN ID"""
        for dept, vlan_id in self.department_vlan_map.items():
            if dept in department:
                return vlan_id
        return None
    
    def get_interface_range(self, location: str) -> Optional[str]:
        """根据位置获取接口范围"""
        return self.location_interface_map.get(location)
    
    def add_department_vlan_mapping(self, department: str, vlan_id: int, save: bool = False):
        """添加部门-VLAN 映射"""
        self.department_vlan_map[department] = vlan_id
        if save:
            self._save_mappings()
    
    def add_location_interface_mapping(self, location: str, interface_range: str, save: bool = False):
        """添加位置 - 接口映射"""
        self.location_interface_map[location] = interface_range
        if save:
            self._save_mappings()
    
    def _save_mappings(self):
        """保存映射到配置文件"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "departments.json"
        )
        
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"departments": {}, "locations": {}}
            
            data["departments"] = self.department_vlan_map
            data["locations"] = self.location_interface_map
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败：{e}")


# 全局映射器实例
_mapper: Optional[LanguageMapper] = None


def get_language_mapper() -> LanguageMapper:
    """获取全局语言映射器"""
    global _mapper
    if _mapper is None:
        _mapper = LanguageMapper()
    return _mapper


def parse_natural_language(user_input: str) -> Dict[str, Any]:
    """解析自然语言（便捷函数）"""
    return get_language_mapper().parse_user_input(user_input)
