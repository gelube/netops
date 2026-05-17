#!/usr/bin/env python3
"""
配置diff工具 — 配置变更前后对比
"""
import difflib
import re
from datetime import datetime
from typing import Dict, List
from pathlib import Path


class ConfigDiff:
    """配置对比工具"""

    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir) if storage_dir else None
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_config(self, device_ip: str, config: str, label: str = "") -> str:
        """保存设备配置快照"""
        if not self.storage_dir:
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label_suffix = f"_{label}" if label else ""
        filename = f"{device_ip}_{timestamp}{label_suffix}.cfg"
        filepath = self.storage_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(config)

        return str(filepath)

    def diff_configs(self, old_config: str, new_config: str,
                     context_lines: int = 3) -> Dict:
        """
        对比两个配置

        Returns:
            {
                'has_changes': bool,
                'added': [lines],
                'removed': [lines],
                'modified': [lines],
                'unified_diff': str,
                'html_diff': str,
                'summary': str,
            }
        """
        old_lines = old_config.splitlines(keepends=True)
        new_lines = new_config.splitlines(keepends=True)

        # unified diff
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile='before', tofile='after',
            n=context_lines,
        ))

        # HTML diff
        html_diff = difflib.HtmlDiff().make_table(
            old_lines, new_lines,
            fromdesc='变更前', todesc='变更后',
        )

        # 分类变更
        added = []
        removed = []
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                added.append(line[1:].strip())
            elif line.startswith('-') and not line.startswith('---'):
                removed.append(line[1:].strip())

        has_changes = bool(added or removed)

        # 生成摘要
        summary_parts = []
        if added:
            summary_parts.append(f"+{len(added)}行")
        if removed:
            summary_parts.append(f"-{len(removed)}行")
        summary = " ".join(summary_parts) if summary_parts else "无变更"

        return {
            'has_changes': has_changes,
            'added': added,
            'removed': removed,
            'unified_diff': ''.join(diff),
            'html_diff': html_diff,
            'summary': summary,
        }

    def diff_sections(self, old_config: str, new_config: str) -> List[Dict]:
        """
        按配置段落对比（以 ! 或 # 分隔）
        返回有变更的段落列表
        """
        old_sections = self._parse_sections(old_config)
        new_sections = self._parse_sections(new_config)

        changes = []
        all_keys = set(list(old_sections.keys()) + list(new_sections.keys()))

        for key in sorted(all_keys):
            old_text = old_sections.get(key, "")
            new_text = new_sections.get(key, "")

            if old_text != new_text:
                diff_result = self.diff_configs(old_text, new_text, context_lines=1)
                changes.append({
                    'section': key,
                    'type': 'added' if not old_text else 'removed' if not new_text else 'modified',
                    'diff': diff_result['unified_diff'],
                    'summary': diff_result['summary'],
                })

        return changes

    def get_config_history(self, device_ip: str, limit: int = 10) -> List[Dict]:
        """获取设备配置快照历史"""
        if not self.storage_dir:
            return []

        configs = []
        pattern = f"{device_ip}_*.cfg"
        for filepath in sorted(self.storage_dir.glob(pattern), reverse=True)[:limit]:
            # 解析时间戳
            name = filepath.stem
            parts = name.split('_')
            if len(parts) >= 3:
                timestamp_str = f"{parts[1]}_{parts[2]}"
                label = parts[3] if len(parts) > 3 else ""
            else:
                timestamp_str = ""
                label = ""

            stat = filepath.stat()
            configs.append({
                'filename': filepath.name,
                'timestamp': timestamp_str,
                'label': label,
                'size': stat.st_size,
                'path': str(filepath),
            })

        return configs

    def load_config_file(self, filepath: str) -> str:
        """加载配置文件内容"""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_sections(self, config: str) -> Dict[str, str]:
        """按段落解析配置"""
        sections = {}
        current_key = "header"
        current_lines = []

        for line in config.splitlines():
            # 华为: 以 # 开头的配置段
            # 思科: 以 ! 开头的配置段
            stripped = line.strip()
            if stripped in ('!', '#') or (stripped.startswith('#') and not stripped.startswith('#!')):
                if current_lines:
                    sections[current_key] = '\n'.join(current_lines)
                current_key = stripped
                current_lines = [line]
            elif re.match(r'^(interface|vlan|acl|route-policy|ospf|bgp|aaa|radius|snmp|ntp|ssh|telnet|user-interface|console|monitor|line)', stripped, re.IGNORECASE):
                if current_lines:
                    sections[current_key] = '\n'.join(current_lines)
                current_key = stripped
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_key] = '\n'.join(current_lines)

        return sections
