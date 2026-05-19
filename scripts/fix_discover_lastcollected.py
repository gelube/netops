"""Fix: discover should update last_collected for devices it successfully contacted"""
import sys

filepath = r'Z:\netops-ai\web\blueprints\topology.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# After "清理临时标记", before "写回devices.json前", add last_collected update
old = """    # 清理临时标记
    for d in devices:
        d.pop("_lldp_status", None)

    # 写回devices.json前，重新读取文件合并可能被ping更新的last_collected"""

new = """    # 清理临时标记，更新last_collected（discover成功连接的设备视为在线）
    from datetime import datetime
    for d in devices:
        d.pop("_lldp_status", None)
        # LLDP采集成功的设备（非offline跳过）说明连接正常
        if d.get("_lldp_status", "") != "offline":
            if not d.get("facts"):
                d["facts"] = {}
            d["facts"]["last_collected"] = datetime.now().isoformat()

    # 写回devices.json前，重新读取文件合并可能被ping更新的last_collected"""

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: added last_collected update in discover")
else:
    print("ERROR: target text not found")
    # Show nearby text for debugging
    idx = content.find("清理临时标记")
    if idx >= 0:
        print(content[idx-100:idx+300])
