"""测试LLDP输出格式"""
import sys
sys.path.insert(0, "Z:/netops-ai/web")
from netops_tools import NetOpsTools

tools = NetOpsTools("Z:/netops-ai/web/data/devices.json")

# 测试3台设备的LLDP输出
for dev_name in ["接入交换机", "核心交换机", "出口路"]:
    print(f"\n{'='*60}")
    print(f"Device: {dev_name}")
    print('='*60)
    
    # Try list format
    r = tools.execute_tool("run_commands", {"device": dev_name, "commands": ["display lldp neighbor-information list"]})
    if r.get("success") and r.get("results"):
        output = r["results"][0].get("output", "")
        print(f"[list] output ({len(output)} chars):")
        print(output[:2000])
    else:
        print(f"[list] failed: {r}")
    
    # Try verbose/list format
    r2 = tools.execute_tool("run_commands", {"device": dev_name, "commands": ["display lldp neighbor-information"]})
    if r2.get("success") and r2.get("results"):
        output2 = r2["results"][0].get("output", "")
        print(f"\n[verbose] output ({len(output2)} chars):")
        print(output2[:3000])
    else:
        print(f"[verbose] failed: {r2}")
