#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实设备测试脚本（简单测试）
"""
import socket
import time


def test_basic_connection(ip: str, port: int):
    """测试基本连接"""
    print(f"\n{'='*60}")
    print(f"测试设备：{ip}:{port}")
    print(f"{'='*60}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, port))
        
        if result == 0:
            print("[OK] 端口可达")
            
            # 尝试读取欢迎信息
            sock.settimeout(2)
            try:
                data = sock.recv(1024)
                if data:
                    print(f"欢迎信息：{data.decode('ascii', errors='ignore')[:200]}")
            except socket.timeout:
                print("[WARN] 无欢迎信息（正常）")
            
            sock.close()
            return True
        else:
            print(f"[FAIL] 端口不可达（错误码：{result}）")
            return False
    
    except Exception as e:
        print(f"[FAIL] 连接失败：{e}")
        return False


def test_natural_language_parsing():
    """测试自然语言解析（不依赖设备）"""
    print(f"\n{'='*60}")
    print("测试自然语言解析")
    print(f"{'='*60}")
    
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app.nl_router.language_map import parse_natural_language
    import json
    
    test_cases = [
        "财务部的电脑上不了网",
        "把访客网络的口子开到 1-8",
        "1 号到 4 号口都通上网",
        "封掉 192.168.1.100",
    ]
    
    for test in test_cases:
        print(f"\n输入：{test}")
        result = parse_natural_language(test)
        print(f"解析结果：{json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    print("""
+------------------------------------------------------------+
|                                                            |
|        NetOps AI - 真实设备测试                            |
|                                                            |
+------------------------------------------------------------+
""")
    
    # 测试连接
    test_basic_connection("127.0.0.1", 30001)
    test_basic_connection("127.0.0.1", 30002)
    
    # 测试自然语言解析
    test_natural_language_parsing()
    
    print("\n[OK] 所有测试完成！")
