#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断知识库 - 积累诊断经验，快速定位问题

v2: FTS5全文搜索 + 同义词扩展 + 中文分词预处理
"""
import sqlite3
import json
import re
import os
from typing import List, Dict, Any
from dataclasses import dataclass, asdict, field

from app.logger import get_logger

log = get_logger(__name__)


@dataclass
class DiagnosisCase:
    """诊断案例"""
    id: str
    problem: str
    symptoms: List[str]
    root_cause: str
    solution: str
    device_type: str
    timestamp: str
    success: bool
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiagnosisCase":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_row(cls, row: tuple, columns: tuple) -> "DiagnosisCase":
        m = dict(zip(columns, row))
        return cls(
            id=m['id'], problem=m['problem'],
            symptoms=json.loads(m.get('symptoms', '[]')),
            root_cause=m.get('root_cause', ''),
            solution=m.get('solution', ''),
            device_type=m.get('device_type', ''),
            timestamp=m.get('timestamp', ''),
            success=bool(m.get('success', 0)),
            tags=json.loads(m.get('tags', '[]')),
        )


# ===== 同义词扩展 =====
_SYNONYM_GROUPS = [
    ["ping", "不通", "无法访问", "连不上", "上不了网", "不可达", "超时", "timeout", "unreachable"],
    ["vlan", "虚拟局域网", "vlan隔离"],
    ["接口", "interface", "端口", "port", "网口"],
    ["路由", "route", "路由表", "routing", "静态路由", "默认路由", "默认网关"],
    ["ospf", "最短路径", "邻居", "neighbor"],
    ["arp", "地址解析", "mac地址", "mac表"],
    ["stp", "生成树", "spanning tree", "环路", "广播风暴"],
    ["acl", "访问控制", "access-list", "过滤", "封禁"],
    ["华为", "huawei", "vrp"],
    ["思科", "cisco", "ios"],
    ["华三", "h3c", "comware"],
]

_SYNONYM_INDEX: Dict[str, int] = {}
for _i, _group in enumerate(_SYNONYM_GROUPS):
    for _word in _group:
        _SYNONYM_INDEX[_word.lower()] = _i


def _expand_query(query: str) -> str:
    """查询扩展：同义词组 → OR表达式"""
    tokens = re.findall(r'[a-zA-Z]+\d*|\d+[a-zA-Z]*|[\u4e00-\u9fff]+', query.lower())
    expanded = []
    seen = set()
    for t in tokens:
        g = _SYNONYM_INDEX.get(t)
        if g is not None and g not in seen:
            seen.add(g)
            syns = _SYNONYM_GROUPS[g][:5]
            expanded.append('(' + ' OR '.join(syns) + ')')
        else:
            expanded.append(t)
    return ' '.join(expanded)


def _tokenize_chinese(text: str) -> str:
    """中文分词预处理：CJK字符间加空格，使FTS5默认tokenizer能索引"""
    result = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            result.append(' ' + ch + ' ')
        else:
            result.append(ch)
    return re.sub(r'\s+', ' ', ''.join(result)).strip()


def _build_fts_query(text: str) -> str:
    """
    构建FTS5查询：中文按字切分后用AND连接（提升精确度）
    英文词保持原样

    "VLAN不通" → "VLAN AND 不 AND 通"
    "ping连不上网关" → "ping AND 连 AND 不 AND 上 AND 网 AND 关"

    注意：保留"不"字，因为"不通"、"上不了网"中的"不"是否定语义关键词
    """
    # 分词
    tokens = re.findall(r'[a-zA-Z]+\d*|\d+[a-zA-Z]*|[\u4e00-\u9fff]', text.lower())
    # 过滤停用词（保留"不"，它是否定语义关键词）
    stopwords = {'的', '了', '是', '在', '有', '和', '与', '或', '一', '个', '这', '那', '上', '下'}
    filtered = [t for t in tokens if t not in stopwords]
    if not filtered:
        # 全被过滤了，用原始token
        filtered = tokens
    return ' AND '.join(filtered)


class KnowledgeBase:
    """知识库 v2 — FTS5全文搜索 + 同义词扩展"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_dir = os.path.join(project_root, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "knowledge.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS diagnosis_cases (
                    id TEXT PRIMARY KEY,
                    problem TEXT NOT NULL,
                    symptoms TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    solution TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]'
                )
            """)
            # FTS5：存case_id做关联，内容做分词预处理
            c.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts
                USING fts5(case_id, content_text)
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_device ON diagnosis_cases(device_type)")
            conn.commit()

    def save_case(self, case: DiagnosisCase) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                symptoms_json = json.dumps(case.symptoms, ensure_ascii=False)
                tags_json = json.dumps(case.tags, ensure_ascii=False)
                c.execute("""
                    INSERT OR REPLACE INTO diagnosis_cases
                    (id, problem, symptoms, root_cause, solution, device_type, timestamp, success, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (case.id, case.problem, symptoms_json, case.root_cause,
                      case.solution, case.device_type, case.timestamp,
                      1 if case.success else 0, tags_json))

                # 更新FTS
                symptoms_text = ' '.join(case.symptoms) if isinstance(case.symptoms, list) else str(case.symptoms)
                tags_text = ' '.join(case.tags) if isinstance(case.tags, list) else str(case.tags)
                full_text = f"{case.problem} {case.root_cause} {symptoms_text} {tags_text}"
                tokenized = _tokenize_chinese(full_text)
                c.execute("DELETE FROM cases_fts WHERE case_id = ?", (case.id,))
                c.execute("INSERT INTO cases_fts(case_id, content_text) VALUES (?, ?)",
                          (case.id, tokenized))
                conn.commit()
            return True
        except Exception as e:
            log.error("保存案例失败", error=str(e))
            return False

    def search(self, query: str, top_k: int = 5, device_type: str = None) -> List[Dict[str, Any]]:
        """
        语义增强搜索：
        1. 同义词扩展
        2. 中文分词预处理
        3. FTS5匹配 → 取case_id → 查主表
        4. 回退到LIKE搜索
        """
        try:
            expanded = _expand_query(query)
            tokenized_query = _build_fts_query(expanded)

            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()

                # FTS5搜索取case_id列表
                try:
                    c.execute("""
                        SELECT case_id FROM cases_fts
                        WHERE cases_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    """, (tokenized_query, top_k))
                    case_ids = [row[0] for row in c.fetchall()]
                except Exception:
                    case_ids = []

                # 从主表取完整数据
                results = []
                if case_ids:
                    placeholders = ','.join('?' * len(case_ids))
                    sql = f"""
                        SELECT * FROM diagnosis_cases
                        WHERE id IN ({placeholders})
                    """
                    params = list(case_ids)
                    if device_type:
                        sql += " AND device_type = ?"
                        params.append(device_type)
                    c.execute(sql, params)
                    columns = tuple(desc[0] for desc in c.description)
                    for row in c.fetchall():
                        case = DiagnosisCase.from_row(row, columns)
                        results.append(case.to_dict())

                # FTS没结果时回退LIKE
                if not results:
                    results = self._fallback_like_search(conn, query, top_k, device_type)

                return results
        except Exception:
            return self._fallback_like_search(None, query, top_k, device_type)

    def _fallback_like_search(self, conn, query: str, top_k: int = 5,
                               device_type: str = None) -> List[Dict[str, Any]]:
        """回退到LIKE搜索"""
        try:
            if conn is None:
                conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            keywords = re.findall(r'[a-zA-Z]+\d*|\d+[a-zA-Z]*|[\u4e00-\u9fff]+', query)

            conditions = []
            params = []
            for kw in keywords:
                conditions.append("(problem LIKE ? OR root_cause LIKE ? OR symptoms LIKE ?)")
                params.extend([f"%{kw}%"] * 3)

            where = " AND ".join(conditions) if conditions else "1=1"
            if device_type:
                where += " AND device_type = ?"
                params.append(device_type)

            c.execute(f"SELECT * FROM diagnosis_cases WHERE {where} ORDER BY timestamp DESC LIMIT ?",
                      params + [top_k])
            columns = tuple(desc[0] for desc in c.description)
            return [DiagnosisCase.from_row(row, columns).to_dict() for row in c.fetchall()]
        except Exception as e:
            log.warning("回退搜索失败", error=str(e))
            return []

    def search_similar(self, problem: str, top_k: int = 5) -> List[DiagnosisCase]:
        """兼容旧接口 — 返回DiagnosisCase列表"""
        results = self.search(problem, top_k)
        cases = []
        for r in results:
            try:
                # 过滤掉非DiagnosisCase字段
                valid_keys = DiagnosisCase.__dataclass_fields__.keys()
                filtered = {k: v for k, v in r.items() if k in valid_keys}
                cases.append(DiagnosisCase(**filtered))
            except Exception as e:
                log.debug("跳过无效案例记录", error=str(e))
                continue
        return cases

    def get_common_solutions(self, device_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                if device_type:
                    c.execute("""
                        SELECT root_cause, COUNT(*) as cnt
                        FROM diagnosis_cases WHERE device_type = ? AND success = 1
                        GROUP BY root_cause ORDER BY cnt DESC LIMIT ?
                    """, (device_type, limit))
                else:
                    c.execute("""
                        SELECT root_cause, COUNT(*) as cnt
                        FROM diagnosis_cases WHERE success = 1
                        GROUP BY root_cause ORDER BY cnt DESC LIMIT ?
                    """, (limit,))
                return [{"root_cause": row[0], "count": row[1]} for row in c.fetchall()]
        except Exception:
            return []

    def get_stats(self) -> Dict[str, Any]:
        return self.get_statistics()

    def get_statistics(self) -> Dict[str, Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM diagnosis_cases")
                total = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM diagnosis_cases WHERE success = 1")
                success = c.fetchone()[0]
                c.execute("SELECT device_type, COUNT(*) FROM diagnosis_cases GROUP BY device_type")
                by_device = {row[0]: row[1] for row in c.fetchall()}
                return {
                    "total": total, "categories": len(by_device),
                    "success_rate": round(success / total, 2) if total > 0 else 0,
                    "by_device_type": by_device,
                }
        except Exception:
            return {"total": 0, "categories": 0}
