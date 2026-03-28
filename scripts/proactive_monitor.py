#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetOps Proactive Monitor - 主动监控和自检脚本
"""
import sys
import os
import subprocess
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class ProactiveMonitor:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.notes_dir = self.project_root / "notes"
        self.logs_dir = self.project_root / "logs"
        self.notes_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.heartbeat_log = self.notes_dir / "heartbeat-log.md"
    
    def run_all_checks(self) -> dict:
        results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "issues": [],
            "suggestions": []
        }
        
        print("=" * 60)
        print("        NetOps AI - Proactive Health Check")
        print("=" * 60)
        print()
        
        print("[CHECK] Running tests...")
        results["checks"]["tests"] = self._run_tests()
        
        print("[CHECK] Checking code quality...")
        results["checks"]["code_quality"] = self._check_code_quality()
        
        print("[CHECK] Checking docs sync...")
        results["checks"]["docs_sync"] = self._check_docs_sync()
        
        print("[CHECK] Checking TODO list...")
        results["checks"]["todo_status"] = self._check_todo_status()
        
        print("[CHECK] Checking tech debt...")
        results["checks"]["tech_debt"] = self._check_tech_debt()
        
        print("[INFO] Generating suggestions...")
        results["suggestions"] = self._generate_suggestions()
        
        self._log_results(results)
        
        print()
        print("=" * 60)
        self._print_summary(results)
        
        return results
    
    def _run_tests(self) -> dict:
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/test_nl_router.py", "-v", "--tb=short"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout + result.stderr
            
            # 从输出中解析结果
            passed = "passed" in output.lower() and "failed" not in output.lower()
            
            if "passed" in output.lower():
                import re
                match = re.search(r"(\d+) passed", output)
                passed_count = int(match.group(1)) if match else 0
            else:
                passed_count = 0
            
            return {
                "status": "PASS" if passed else "FAIL",
                "passed": passed,
                "test_count": passed_count,
                "output": output[-500:] if len(output) > 500 else output
            }
        
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT", "passed": False, "error": "Test timeout"}
        except FileNotFoundError:
            return {"status": "NO_PYTEST", "passed": False, "error": "pytest not installed"}
        except Exception as e:
            return {"status": "ERROR", "passed": False, "error": str(e)}
    
    def _check_code_quality(self) -> dict:
        issues = []
        
        try:
            result = subprocess.run(
                ["ruff", "check", "app/nl_router/", "--quiet"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout.strip():
                issues.append(f"Ruff found {len(result.stdout.strip().split(chr(10)))} issues")
        except FileNotFoundError:
            issues.append("Ruff not installed, suggest: pip install ruff")
        except Exception as e:
            issues.append(f"Ruff check failed: {e}")
        
        nl_router_path = self.project_root / "app" / "nl_router"
        if nl_router_path.exists():
            parser_py = nl_router_path / "parser.py"
            if parser_py.exists():
                size = parser_py.stat().st_size
                if size > 10000:
                    issues.append(f"parser.py too large ({size} bytes), consider splitting")
            
            for py_file in nl_router_path.glob("*.py"):
                content = py_file.read_text(encoding="utf-8")
                todo_count = content.count("TODO")
                if todo_count > 5:
                    issues.append(f"{py_file.name} has {todo_count} TODOs")
        
        return {"status": "OK" if not issues else "ISSUES", "issues": issues}
    
    def _check_docs_sync(self) -> dict:
        issues = []
        
        readme = self.project_root / "README.md"
        if not readme.exists():
            issues.append("README.md does not exist")
        else:
            content = readme.read_text(encoding="utf-8")
            if "nl_router" not in content.lower():
                issues.append("README.md does not mention nl_router module")
            if "main_nl.py" not in content:
                issues.append("README.md does not mention natural language entry")
        
        skill_md = self.project_root / "skills" / "netops-nl-router" / "SKILL.md"
        if not skill_md.exists():
            issues.append("SKILL.md does not exist")
        
        return {"status": "OK" if not issues else "ISSUES", "issues": issues}
    
    def _check_todo_status(self) -> dict:
        todos = []
        
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            for i, line in enumerate(lines, 1):
                if "TODO" in line:
                    todo_text = line.split("TODO")[-1].strip().strip(":")
                    todos.append({
                        "file": str(py_file.relative_to(self.project_root)),
                        "line": i,
                        "text": todo_text
                    })
        
        return {
            "status": f"TODO: {len(todos)} items",
            "count": len(todos),
            "todos": todos[:10]
        }
    
    def _check_tech_debt(self) -> dict:
        debts = []
        
        executor_py = self.project_root / "app" / "nl_router" / "executor.py"
        if executor_py.exists():
            content = executor_py.read_text(encoding="utf-8")
            
            if "mcp_client=None" in content:
                debts.append("NetBrain MCP client not integrated (placeholder)")
            
            if "# TODO: from MCP get device details" in content or "# TODO: 从 MCP 获取设备详情" in content:
                debts.append("Device details fetch not implemented")
            
            if "pass  # to be implemented" in content.lower() or "# 待实现" in content:
                debts.append("Diagnosis workflow not fully implemented")
        
        test_file = self.project_root / "tests" / "test_nl_router.py"
        if test_file.exists():
            content = test_file.read_text(encoding="utf-8")
            test_count = content.count("def test_")
            if test_count < 5:
                debts.append(f"Few test cases ({test_count}), suggest adding more")
        
        return {"status": "OK" if not debts else "DEBT", "debts": debts}
    
    def _generate_suggestions(self) -> list:
        return [
            {
                "type": "feature",
                "priority": "high",
                "title": "Integrate NetBrain MCP client",
                "description": "Current MCP client is placeholder, needs real integration"
            },
            {
                "type": "feature",
                "priority": "medium",
                "title": "Implement VLAN diagnosis workflow",
                "description": "Combine MCP tools to auto-check VLAN config"
            },
            {
                "type": "security",
                "priority": "high",
                "title": "Encrypt device credentials",
                "description": "SSH credentials are plaintext, use keyring"
            },
            {
                "type": "docs",
                "priority": "low",
                "title": "Add demo video",
                "description": "Record GIF showing natural language config"
            }
        ]
    
    def _log_results(self, results: dict) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        with open(self.heartbeat_log, "a", encoding="utf-8") as f:
            f.write(f"\n## {timestamp}\n\n")
            
            tests = results["checks"].get("tests", {})
            f.write(f"- Tests: {tests.get('status', 'unknown')}\n")
            
            code = results["checks"].get("code_quality", {})
            f.write(f"- Code Quality: {code.get('status', 'unknown')}\n")
            
            docs = results["checks"].get("docs_sync", {})
            f.write(f"- Docs Sync: {docs.get('status', 'unknown')}\n")
            
            todo = results["checks"].get("todo_status", {})
            f.write(f"- TODO: {todo.get('count', 0)} items\n")
            
            debt = results["checks"].get("tech_debt", {})
            f.write(f"- Tech Debt: {debt.get('status', 'unknown')}\n")
            
            f.write(f"- Suggestions: {len(results['suggestions'])}\n")
            
            all_issues = []
            for check_name, check_data in results["checks"].items():
                if "issues" in check_data:
                    all_issues.extend(check_data["issues"])
            
            if all_issues:
                f.write("\n**Issues:**\n")
                for issue in all_issues[:5]:
                    f.write(f"- {issue}\n")
            
            f.write("\n")
    
    def _print_summary(self, results: dict) -> None:
        checks = results["checks"]
        
        score = 0
        total = 0
        
        for check_name, check_data in checks.items():
            total += 1
            if check_data.get("status") == "OK" or check_data.get("passed") is True:
                score += 1
        
        health_pct = int((score / total) * 100) if total > 0 else 0
        
        print(f"Health Score: {health_pct}%")
        print()
        
        all_issues = []
        for check_name, check_data in checks.items():
            if "issues" in check_data and check_data["issues"]:
                all_issues.extend(check_data["issues"])
        
        if all_issues:
            print("ISSUES FOUND:")
            for issue in all_issues[:5]:
                print(f"  - {issue}")
            print()
        
        if results["suggestions"]:
            print("SUGGESTIONS:")
            for i, sug in enumerate(results["suggestions"][:3], 1):
                print(f"  {i}. [{sug['priority']}] {sug['title']}")
            print()
        
        print("NEXT STEPS:")
        if checks.get("tests", {}).get("passed") is False:
            print("  1. Fix failing tests")
        if checks.get("tech_debt", {}).get("debts"):
            print("  2. Address tech debt")
        if results["suggestions"]:
            print(f"  3. Consider: {results['suggestions'][0]['title']}")


def main():
    monitor = ProactiveMonitor()
    results = monitor.run_all_checks()
    
    # 只有测试失败才退出 1
    tests = results["checks"].get("tests", {})
    if tests.get("passed") is False and tests.get("status") == "FAIL":
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
