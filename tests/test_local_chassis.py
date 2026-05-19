"""测试获取本地chassis_id"""
import sys
sys.path.insert(0, "Z:/netops-ai/web")
from netops_tools import NetOpsTools

tools = NetOpsTools("Z:/netops-ai/web/data/devices.json")

for dev_name in ["接入交换机", "核心交换机", "出口路"]:
    print(f"\n{'='*60}")
    print(f"Device: {dev_name}")
    
    # display lldp local-information
    r = tools.execute_tool("run_commands", {"device": dev_name, "commands": ["display lldp local-information"]})
    if r.get("success") and r.get("results"):
        output = r["results"][0].get("output", "")
        print(f"local-info output ({len(output)} chars):")
        print(output[:2000])
    else:
        print(f"failed: {r}")
