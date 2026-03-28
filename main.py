#!/usr/bin/env python3
"""
NetOps AI - 网络工程师智能助手
主入口文件
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ui import run_app


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        NETOPS AI - 网络工程师智能助手                    ║
║        Network Engineer AI Assistant                     ║
║                                                          ║
║                    Version 1.0.0                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # 启动TUI应用
    run_app()


if __name__ == "__main__":
    main()