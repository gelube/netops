#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审计日志 - 记录所有操作，满足合规要求
"""
import json
from datetime import date
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from app.logger import get_logger

log = get_logger(__name__)


@dataclass
class AuditEntry:
    """审计日志条目"""
    timestamp: str           # ISO 格式时间戳
    user_id: str             # 用户标识
    action: str              # 操作类型：config_vlan, diagnose, backup 等
    target: str              # 操作目标：设备名/IP
    details: Dict[str, Any]  # 操作详情
    result: str              # 结果：success / failed
    error: str = ""          # 错误信息（如果有）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        return cls(**data)


class AuditLogger:
    """审计日志器"""

    def __init__(self, log_dir: str = None):
        if log_dir is None:
            # 默认路径：项目根目录下的 logs/audit
            project_root = Path(__file__).parent.parent.parent
            log_dir = project_root / "logs" / "audit"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> bool:
        """记录审计日志"""
        try:
            # 按日期分文件
            log_file = self.log_dir / f"{entry.timestamp[:10]}.jsonl"

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

            return True
        except Exception as e:
            log.error("记录审计日志失败", error=str(e))
            return False

    def query(
        self,
        query_date: date = None,
        user_id: str = None,
        action: str = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """查询审计日志"""
        entries = []

        try:
            # 确定要查询的文件
            if query_date:
                log_files = [self.log_dir / f"{query_date}.jsonl"]
            else:
                log_files = sorted(self.log_dir.glob("*.jsonl"), reverse=True)

            for log_file in log_files:
                if not log_file.exists():
                    continue

                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            entry = AuditEntry.from_dict(data)

                            # 过滤条件
                            if user_id and entry.user_id != user_id:
                                continue
                            if action and entry.action != action:
                                continue

                            entries.append(entry)

                            if len(entries) >= limit:
                                return entries
                        except Exception:
                            log.debug("解析审计日志行失败，跳过")
                            continue
        except Exception as e:
            log.error("查询审计日志失败", error=str(e))

        return entries

    def export(
        self,
        start_date: date,
        end_date: date,
        format: str = "csv",
        output_path: str = None
    ) -> Optional[str]:
        """导出审计日志"""
        try:
            entries = []

            # 收集日期范围内的日志
            current_date = start_date
            while current_date <= end_date:
                log_file = self.log_dir / f"{current_date}.jsonl"
                if log_file.exists():
                    with open(log_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                data = json.loads(line.strip())
                                entries.append(AuditEntry.from_dict(data))
                            except Exception:
                                log.debug("解析审计日志行失败，跳过")
                                continue
                current_date = date(
                    current_date.year,
                    current_date.month,
                    current_date.day + 1
                )

            if not entries:
                return None

            # 确定输出路径
            if output_path is None:
                output_path = self.log_dir.parent / f"audit_export_{start_date}_{end_date}.{format}"

            # 导出
            if format == "csv":
                import csv
                with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        "timestamp", "user_id", "action", "target", "details", "result", "error"
                    ])
                    writer.writeheader()
                    for entry in entries:
                        row = entry.to_dict()
                        row["details"] = json.dumps(row["details"], ensure_ascii=False)
                        writer.writerow(row)

            elif format == "json":
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump([e.to_dict() for e in entries], f, ensure_ascii=False, indent=2)

            return str(output_path)
        except Exception as e:
            log.error("导出审计日志失败", error=str(e))
            return None

    def get_summary(self, query_date: date = None) -> Dict[str, Any]:
        """获取日志摘要统计"""
        entries = self.query(query_date=query_date, limit=10000)

        if not entries:
            return {"total": 0}

        # 统计
        by_action = {}
        by_result = {"success": 0, "failed": 0}
        by_user = {}

        for entry in entries:
            by_action[entry.action] = by_action.get(entry.action, 0) + 1
            by_result[entry.result] = by_result.get(entry.result, 0) + 1
            by_user[entry.user_id] = by_user.get(entry.user_id, 0) + 1

        return {
            "total": len(entries),
            "by_action": by_action,
            "by_result": by_result,
            "by_user": by_user,
        }
