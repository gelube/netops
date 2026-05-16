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
            pass

        # 尝试使用 cryptography（Fernet 对称加密）
        self._fernet = None
        self._use_fernet = False
        if not self._use_keyring:
            try:
                from cryptography.fernet import Fernet
                key_path = os.path.join(os.path.dirname(self.storage_path), ".netops_key")
                if os.path.exists(key_path):
                    with open(key_path, "rb") as f:
                        key = f.read()
                else:
                    key = Fernet.generate_key()
                    os.makedirs(os.path.dirname(key_path), exist_ok=True)
                    with open(key_path, "wb") as f:
                        f.write(key)
                    # 仅当前用户可读写
                    os.chmod(key_path, 0o600)
                self._fernet = Fernet(key)
                self._use_fernet = True
            except ImportError:
                # cryptography 不可用，降级到 base64（不安全）
                import warnings
                warnings.warn(
                    "[NetOps-AI] cryptography 未安装，凭证将以 base64 存储（非加密）。"
                    "建议: pip install cryptography",
                    stacklevel=2,
                )

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
        """保存到加密文件（Fernet加密 或 base64编码降级）"""
        try:
            # 加载现有数据
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"devices": {}}

            # 加密或编码密码
            if self._use_fernet and self._fernet:
                encoded_password = self._fernet.encrypt(cred.password.encode("utf-8")).decode("utf-8")
                storage_mode = "fernet"
            else:
                encoded_password = base64.b64encode(cred.password.encode("utf-8")).decode("utf-8")
                storage_mode = "base64"  # 非安全，仅避免明文

            # 保存
            data["devices"][cred.hostname] = {
                "ip": cred.ip,
                "username": cred.username,
                "password": encoded_password,
                "_encoding": storage_mode,  # 标记编码方式，读取时自动识别
                "port": cred.port,
                "vendor": cred.vendor,
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # 设置文件权限（仅当前用户可读写）
            try:
                os.chmod(self.storage_path, 0o600)
            except OSError:
                pass

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

            # 根据编码方式解密/解码密码
            encoded_password = device_data.get("password", "")
            encoding = device_data.get("_encoding", "base64")  # 旧数据默认 base64

            if encoding == "fernet" and self._fernet:
                password = self._fernet.decrypt(encoded_password.encode("utf-8")).decode("utf-8")
            else:
                password = base64.b64decode(encoded_password.encode("utf-8")).decode("utf-8")

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
