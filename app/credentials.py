#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备凭证加密存储模块
使用 keyring 或本地加密文件存储 SSH 凭证
"""
import os
import json
import base64
from typing import Optional, Dict, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DeviceCredential:
    """设备凭证"""
    hostname: str
    ip: str
    username: str
    password: str
    port: int = 22
    vendor: str = "huawei"


class CredentialManager:
    """凭证管理器"""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        初始化
        
        Args:
            storage_path: 加密文件存储路径（可选）
        """
        if storage_path is None:
            # 默认保存到项目 config 目录
            config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
            self.storage_path = os.path.join(config_dir, "credentials.json")
        else:
            self.storage_path = storage_path
        
        # 尝试使用 keyring（系统密钥环）
        self._use_keyring = False
        try:
            import keyring
            self._keyring_service = "netops-ai"
            self._use_keyring = True
        except ImportError:
            # keyring 不可用时，使用加密文件
            pass
        
        # 确保存储目录存在
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir:
            Path(storage_dir).mkdir(parents=True, exist_ok=True)
    
    def save_credential(self, cred: DeviceCredential) -> bool:
        """
        保存凭证
        
        Args:
            cred: 设备凭证
        
        Returns:
            是否成功
        """
        if self._use_keyring:
            import keyring
            
            # 存储到系统密钥环
            key_name = f"netops:{cred.hostname}"
            secret = json.dumps({
                "ip": cred.ip,
                "username": cred.username,
                "password": cred.password,
                "port": cred.port,
                "vendor": cred.vendor,
            })
            
            try:
                keyring.set_password(self._keyring_service, key_name, secret)
                return True
            except Exception as e:
                print(f"Keyring 保存失败：{e}")
                self._use_keyring = False
        
        # 降级到文件存储（加密）
        return self._save_to_file(cred)
    
    def get_credential(self, hostname: str) -> Optional[DeviceCredential]:
        """
        获取凭证
        
        Args:
            hostname: 设备主机名
        
        Returns:
            设备凭证，如果不存在则返回 None
        """
        if self._use_keyring:
            import keyring
            
            key_name = f"netops:{hostname}"
            try:
                secret = keyring.get_password(self._keyring_service, key_name)
                if secret:
                    data = json.loads(secret)
                    return DeviceCredential(
                        hostname=hostname,
                        ip=data.get("ip", ""),
                        username=data.get("username", ""),
                        password=data.get("password", ""),
                        port=data.get("port", 22),
                        vendor=data.get("vendor", "huawei"),
                    )
            except Exception:
                pass
        
        # 降级到文件读取
        return self._load_from_file(hostname)
    
    def list_hostnames(self) -> List[str]:
        """列出所有已保存的主机名"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return list(data.get("devices", {}).keys())
            except Exception:
                pass
        return []
    
    def delete_credential(self, hostname: str) -> bool:
        """删除凭证"""
        if self._use_keyring:
            import keyring
            key_name = f"netops:{hostname}"
            try:
                keyring.set_password(self._keyring_service, key_name, "")
                return True
            except Exception:
                pass
        
        # 从文件中删除
        return self._delete_from_file(hostname)
    
    def _save_to_file(self, cred: DeviceCredential) -> bool:
        """保存到加密文件（简单 base64 编码，非安全加密）"""
        try:
            # 加载现有数据
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"devices": {}}
            
            # 编码密码（注意：这不是真正的加密，只是避免明文）
            encoded_password = base64.b64encode(
                cred.password.encode("utf-8")
            ).decode("utf-8")
            
            # 保存
            data["devices"][cred.hostname] = {
                "ip": cred.ip,
                "username": cred.username,
                "password": encoded_password,  # 编码后的密码
                "port": cred.port,
                "vendor": cred.vendor,
            }
            
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 设置文件权限（仅当前用户可读写）
            os.chmod(self.storage_path, 0o600)
            
            return True
        except Exception as e:
            print(f"文件保存失败：{e}")
            return False
    
    def _load_from_file(self, hostname: str) -> Optional[DeviceCredential]:
        """从文件加载"""
        try:
            if not os.path.exists(self.storage_path):
                return None
            
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            device_data = data.get("devices", {}).get(hostname)
            if not device_data:
                return None
            
            # 解码密码
            encoded_password = device_data.get("password", "")
            password = base64.b64decode(
                encoded_password.encode("utf-8")
            ).decode("utf-8")
            
            return DeviceCredential(
                hostname=hostname,
                ip=device_data.get("ip", ""),
                username=device_data.get("username", ""),
                password=password,
                port=device_data.get("port", 22),
                vendor=device_data.get("vendor", "huawei"),
            )
        except Exception as e:
            print(f"文件加载失败：{e}")
            return None
    
    def _delete_from_file(self, hostname: str) -> bool:
        """从文件中删除"""
        try:
            if not os.path.exists(self.storage_path):
                return False
            
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if hostname in data.get("devices", {}):
                del data["devices"][hostname]
                
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return True
            return False
        except Exception:
            return False


# 全局凭证管理器实例
_cred_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """获取全局凭证管理器"""
    global _cred_manager
    if _cred_manager is None:
        _cred_manager = CredentialManager()
    return _cred_manager


def save_device_credential(hostname: str, ip: str, username: str, password: str, **kwargs) -> bool:
    """保存设备凭证（便捷函数）"""
    cred = DeviceCredential(
        hostname=hostname,
        ip=ip,
        username=username,
        password=password,
        **kwargs
    )
    return get_credential_manager().save_credential(cred)


def get_device_credential(hostname: str) -> Optional[DeviceCredential]:
    """获取设备凭证（便捷函数）"""
    return get_credential_manager().get_credential(hostname)
