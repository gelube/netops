#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断知识库 - 积累诊断经验，快速定位问题
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
import os


@dataclass
class DiagnosisCase:
    """诊断案例"""
    id: str
    problem: str              # 问题描述："VLAN 10 上不了网"
    symptoms: List[str]       # 症状列表：["VLAN 未创建", "接口未加入"]
    root_cause: str           # 根因："接口未加入 VLAN"
    solution: str             # 解决方案："interface GE0/0/1 → port default vlan 10"
    device_type: str          # 设备类型："huawei"
    timestamp: str            # 时间戳
    success: bool             # 是否成功解决
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiagnosisCase":
        return cls(**data)


class KnowledgeBase:
    """知识库"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认路径：项目根目录下的 data/knowledge.db
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_dir = os.path.join(project_root, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "knowledge.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS diagnosis_cases (
                    id TEXT PRIMARY KEY,
                    problem TEXT NOT NULL,
                    symptoms TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    solution TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    success INTEGER NOT NULL
                )
            """)
            
            # 创建索引加速搜索
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_problem 
                ON diagnosis_cases(problem)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_device_type 
                ON diagnosis_cases(device_type)
            """)
            
            conn.commit()
    
    def save_case(self, case: DiagnosisCase) -> bool:
        """保存诊断案例"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO diagnosis_cases 
                    (id, problem, symptoms, root_cause, solution, device_type, timestamp, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    case.id,
                    case.problem,
                    json.dumps(case.symptoms, ensure_ascii=False),
                    case.root_cause,
                    case.solution,
                    case.device_type,
                    case.timestamp,
                    1 if case.success else 0
                ))
                conn.commit()
            return True
        except Exception as e:
            print(f"保存案例失败：{e}")
            return False
    
    def search_similar(self, problem: str, top_k: int = 5) -> List[DiagnosisCase]:
        """搜索相似案例（关键词匹配）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 提取关键词
                keywords = problem.split()
                
                # 构建查询
                query = "SELECT * FROM diagnosis_cases WHERE "
                conditions = []
                params = []
                
                for keyword in keywords:
                    conditions.append("problem LIKE ?")
                    params.append(f"%{keyword}%")
                
                query += " OR ".join(conditions)
                query += f" LIMIT {top_k}"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                cases = []
                for row in rows:
                    case = DiagnosisCase(
                        id=row[0],
                        problem=row[1],
                        symptoms=json.loads(row[2]),
                        root_cause=row[3],
                        solution=row[4],
                        device_type=row[5],
                        timestamp=row[6],
                        success=bool(row[7])
                    )
                    cases.append(case)
                
                return cases
        except Exception as e:
            print(f"搜索案例失败：{e}")
            return []
    
    def get_common_solutions(self, device_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """获取常见解决方案"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if device_type:
                    cursor.execute("""
                        SELECT root_cause, COUNT(*) as count
                        FROM diagnosis_cases
                        WHERE device_type = ? AND success = 1
                        GROUP BY root_cause
                        ORDER BY count DESC
                        LIMIT ?
                    """, (device_type, limit))
                else:
                    cursor.execute("""
                        SELECT root_cause, COUNT(*) as count
                        FROM diagnosis_cases
                        WHERE success = 1
                        GROUP BY root_cause
                        ORDER BY count DESC
                        LIMIT ?
                    """, (limit,))
                
                return [{"root_cause": row[0], "count": row[1]} for row in cursor.fetchall()]
        except Exception as e:
            print(f"获取常见解决方案失败：{e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 总案例数
                cursor.execute("SELECT COUNT(*) FROM diagnosis_cases")
                total = cursor.fetchone()[0]
                
                # 成功案例数
                cursor.execute("SELECT COUNT(*) FROM diagnosis_cases WHERE success = 1")
                success_count = cursor.fetchone()[0]
                
                # 按设备类型统计
                cursor.execute("""
                    SELECT device_type, COUNT(*) 
                    FROM diagnosis_cases 
                    GROUP BY device_type
                """)
                by_device = {row[0]: row[1] for row in cursor.fetchall()}
                
                return {
                    "total_cases": total,
                    "success_cases": success_count,
                    "success_rate": success_count / total if total > 0 else 0,
                    "by_device_type": by_device
                }
        except Exception as e:
            print(f"获取统计信息失败：{e}")
            return {}
