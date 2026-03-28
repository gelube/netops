#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置备份和回滚模块
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ConfigBackup:
    """配置备份"""
    hostname: str
    timestamp: str
    config_hash: str
    config_content: str
    backup_path: str
    comment: str = ""


class ConfigBackupManager:
    """配置备份管理器"""
    
    def __init__(self, backup_dir: Optional[str] = None):
        """
        初始化
        
        Args:
            backup_dir: 备份目录
        """
        if backup_dir is None:
            # 默认保存到项目 backups 目录
            base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")
            os.makedirs(base_dir, exist_ok=True)
            self.backup_dir = os.path.join(base_dir, datetime.now().strftime("%Y-%m-%d"))
        else:
            self.backup_dir = backup_dir
        
        # 确保备份目录存在
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)
        
        # 索引文件
        self.index_path = os.path.join(
            os.path.dirname(self.backup_dir),
            "backup_index.json"
        )
    
    def backup_config(
        self,
        hostname: str,
        config_content: str,
        comment: str = "",
    ) -> ConfigBackup:
        """
        备份配置
        
        Args:
            hostname: 设备主机名
            config_content: 配置内容
            comment: 备份备注
        
        Returns:
            ConfigBackup
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_hash = hashlib.sha256(config_content.encode("utf-8")).hexdigest()
        
        # 生成备份文件名
        filename = f"{hostname}_{timestamp}.cfg"
        backup_path = os.path.join(self.backup_dir, filename)
        
        # 保存配置
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        
        # 创建备份记录
        backup = ConfigBackup(
            hostname=hostname,
            timestamp=timestamp,
            config_hash=config_hash,
            config_content=config_content,
            backup_path=backup_path,
            comment=comment,
        )
        
        # 更新索引
        self._add_to_index(backup)
        
        return backup
    
    def get_backups(self, hostname: str, limit: int = 10) -> List[ConfigBackup]:
        """
        获取设备的备份历史
        
        Args:
            hostname: 设备主机名
            limit: 返回数量限制
        
        Returns:
            备份列表（按时间倒序）
        """
        index = self._load_index()
        backups = index.get(hostname, [])
        
        # 按时间倒序
        backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # 返回最近的 limit 个
        result = []
        for b in backups[:limit]:
            result.append(ConfigBackup(
                hostname=hostname,
                timestamp=b["timestamp"],
                config_hash=b["config_hash"],
                config_content="",  # 不加载内容
                backup_path=b["backup_path"],
                comment=b.get("comment", ""),
            ))
        
        return result
    
    def restore_backup(self, backup: ConfigBackup) -> str:
        """
        恢复备份（返回配置内容）
        
        Args:
            backup: 备份记录
        
        Returns:
            配置内容
        """
        # 从备份文件读取
        if os.path.exists(backup.backup_path):
            with open(backup.backup_path, "r", encoding="utf-8") as f:
                return f.read()
        
        # 如果备份文件不存在，尝试从索引加载内容
        index = self._load_index()
        backups = index.get(backup.hostname, [])
        
        for b in backups:
            if b["timestamp"] == backup.timestamp:
                return b.get("config_content", "")
        
        raise FileNotFoundError(f"备份文件不存在：{backup.backup_path}")
    
    def compare_backups(
        self,
        backup1: ConfigBackup,
        backup2: ConfigBackup,
    ) -> Dict[str, Any]:
        """
        比较两个备份的差异
        
        Args:
            backup1: 备份 1
            backup2: 备份 2
        
        Returns:
            差异报告
        """
        # 加载配置内容
        config1 = self.restore_backup(backup1)
        config2 = self.restore_backup(backup2)
        
        lines1 = set(config1.split("\n"))
        lines2 = set(config2.split("\n"))
        
        added = lines2 - lines1
        removed = lines1 - lines2
        
        return {
            "backup1": {
                "timestamp": backup1.timestamp,
                "hash": backup1.config_hash,
            },
            "backup2": {
                "timestamp": backup2.timestamp,
                "hash": backup2.config_hash,
            },
            "added_lines": list(added),
            "removed_lines": list(removed),
            "total_changes": len(added) + len(removed),
        }
    
    def _add_to_index(self, backup: ConfigBackup) -> None:
        """添加到索引"""
        index = self._load_index()
        
        if backup.hostname not in index:
            index[backup.hostname] = []
        
        index[backup.hostname].append({
            "timestamp": backup.timestamp,
            "config_hash": backup.config_hash,
            "backup_path": backup.backup_path,
            "comment": backup.comment,
            # 也保存内容到索引（方便快速访问）
            "config_content": backup.config_content,
        })
        
        self._save_index(index)
    
    def _load_index(self) -> Dict[str, List[Dict]]:
        """加载索引"""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_index(self, index: Dict[str, List[Dict]]) -> None:
        """保存索引"""
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)


# 便捷函数
_backup_manager: Optional[ConfigBackupManager] = None


def get_backup_manager() -> ConfigBackupManager:
    """获取全局备份管理器"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = ConfigBackupManager()
    return _backup_manager


def backup_device_config(hostname: str, config: str, comment: str = "") -> ConfigBackup:
    """备份设备配置"""
    return get_backup_manager().backup_config(hostname, config, comment)


def get_device_backups(hostname: str, limit: int = 10) -> List[ConfigBackup]:
    """获取设备备份历史"""
    return get_backup_manager().get_backups(hostname, limit)
