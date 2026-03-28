#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetOps AI - 自然语言入口（纯 SSH 模式）
"""
import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.llm.config import LLMConfig, LLMClient
from app.nl_router.executor import NLExecutor
from app.credentials import get_credential_manager, DeviceCredential


async def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        NETOPS AI - 自然语言网络运维                      ║
║        Pure SSH Mode                                     ║
║                                                          ║
║                    Version 2.0.0                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

示例命令:
  • "查一下 SW-Core 的配置"
  • "给 SW-Core (IP: 192.168.1.1) 的 1-4 口配 VLAN 10"
  • "VLAN 10 上不了网，帮我查一下"
  • "从 10.10.10.1 到 8.8.8.8 的路径是什么"

输入 'quit' 退出

""")
    
    # 初始化 LLM 客户端
    llm_config = LLMConfig(
        provider="openai",
        endpoint="http://localhost:11434/v1",  # Ollama 本地模型
        api_key="ollama",
        model="qwen2.5:7b"
    )
    
    llm_client = LLMClient(llm_config)
    
    # 初始化凭证管理器
    cred_manager = get_credential_manager()
    
    # 初始化执行器（纯 SSH 模式）
    executor = NLExecutor(llm_client=llm_client, credential_manager=cred_manager)
    
    # 交互式命令行
    while True:
        try:
            user_input = input("\n🔹 NetOps> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 再见")
                break
            
            # 特殊命令：保存凭证
            if user_input.startswith("!save "):
                # !save hostname ip username password
                parts = user_input[4:].split()
                if len(parts) >= 4:
                    hostname, ip, username, password = parts[:4]
                    port = int(parts[4]) if len(parts) > 4 else 22
                    
                    from app.credentials import save_device_credential
                    if save_device_credential(hostname, ip, username, password, port=port):
                        print(f"✅ 已保存 {hostname} 的凭证")
                    else:
                        print("❌ 保存失败")
                else:
                    print("用法：!save hostname ip username password [port]")
                continue
            
            # 特殊命令：列出凭证
            if user_input == "!list":
                hostnames = cred_manager.list_hostnames()
                if hostnames:
                    print("已保存的设备:")
                    for h in hostnames:
                        print(f"  - {h}")
                else:
                    print("未保存任何设备")
                continue
            
            # 执行自然语言请求
            result = await executor.execute(user_input)
            
            # 输出结果
            if result.success:
                if result.requires_confirmation:
                    print("\n⚠️  待确认配置:")
                    print(result.confirmation_details)
                    
                    confirm = input("\n是否执行？(y/n): ").strip().lower()
                    if confirm in ["y", "yes"]:
                        # 需要凭证
                        if result.data.get("batch"):
                            # 批量配置
                            print("⚠️  批量配置需要每台设备的凭证")
                            print("请先用 !save 命令保存凭证")
                        else:
                            device_ip = result.data.get("device_ip", "")
                            device = result.data.get("device", "")
                            
                            # 尝试从凭证管理器获取
                            cred = cred_manager.get_credential(device) if device else None
                            
                            if cred:
                                # 已有凭证，直接执行
                                exec_result = await executor.confirm_and_execute(
                                    confirmed=True,
                                    device_data=result.data,
                                    username=cred.username,
                                    password=cred.password,
                                )
                            else:
                                # 需要输入凭证
                                print(f"\n需要 {device} ({device_ip}) 的 SSH 凭证:")
                                username = input("用户名：").strip()
                                password = input("密码：").strip()
                                
                                save = input("是否保存凭证？(y/n): ").strip().lower()
                                
                                exec_result = await executor.confirm_and_execute(
                                    confirmed=True,
                                    device_data=result.data,
                                    username=username,
                                    password=password,
                                )
                                
                                if save == "y" and device:
                                    from app.credentials import save_device_credential
                                    if save_device_credential(device, device_ip, username, password):
                                        print("✅ 凭证已保存")
                            
                            print(f"\n{exec_result.message}")
                    else:
                        print("❌ 已取消")
                else:
                    print(f"\n✅ {result.message}")
                    if result.data:
                        # 诊断报告
                        if isinstance(result.data, dict) and "steps" in result.data:
                            print("\n诊断步骤:")
                            for step in result.data.get("steps", []):
                                status_icon = "✅" if step.get("status") == "PASS" else "❌"
                                print(f"  {status_icon} {step.get('step')}: {step.get('message')}")
                            
                            if result.data.get("root_cause"):
                                print(f"\n根因：{result.data['root_cause']}")
                            if result.data.get("suggestions"):
                                print("\n建议:")
                                for sug in result.data["suggestions"]:
                                    print(f"  • {sug}")
                        else:
                            print(result.data)
            else:
                print(f"\n❌ {result.message}")
        
        except KeyboardInterrupt:
            print("\n👋 再见")
            break
        except Exception as e:
            print(f"\n❌ 错误：{e}")


if __name__ == "__main__":
    asyncio.run(main())
   asyncio.run(main())
