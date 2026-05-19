"""测试获取本地chassis_id with screen-length disable"""
import sys
sys.path.insert(0, "Z:/netops-ai/web")
from netops_tools import NetOpsTools

tools = NetOpsTools("Z:/netops-ai/web/data/devices.json")

for dev_name in ["接入交换机", "核心交换机", "出口路"]:
    print(f"\n{'='*60}")
    print(f"Device: {dev_name}")
    
    r = tools.execute_tool("run_commands", {"device": dev_name, "commands": ["screen-length disable", "display lldp local-information"]})
    if r.get("success") and r.get("results"):
        for res in r["results"]:
            output = res.get("output", "")
            if "Chassis ID" in output:
                # Extract chassis ID
                import re
                m = re.search(r"Chassis ID\s*:\s*(\S+)", output)
                if m:
                    print(f"  Local Chassis ID: {m.group(1)}")
                m2 = re.search(r"System name\s*:\s*(\S+)", output)
                if m2:
                    print(f"  System name: {m2.group(1)}")
    else:
        print(f"  failed: {r}")
