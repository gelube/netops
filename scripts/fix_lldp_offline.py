import re

path = r'Z:\netops-ai\web\blueprints\topology.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add online check at the start of the loop in ensure_lldp_on_all_devices
# Find the loop start and add online check after name check
old_loop = '''    for d in devices:
        name = d.get("remark") or d.get("name")
        if not name:
            continue

        if d.get("lldp_neighbors") and not force:'''

new_loop = '''    for d in devices:
        name = d.get("remark") or d.get("name")
        if not name:
            continue

        # 跳过离线设备（TCP端口检测）
        _ip = d.get("ip", "")
        _port = d.get("port", 22)
        if _ip:
            try:
                import socket as _sock
                _s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                _s.settimeout(3)
                _r = _s.connect_ex((_ip, int(_port)))
                _s.close()
                if _r != 0:
                    log.info(f"ensure_lldp: {name} offline (port {_port} unreachable), skipping")
                    d["_lldp_status"] = "offline"
                    updated.append(d)
                    continue
            except Exception as _e:
                log.debug(f"ensure_lldp: {name} online check failed: {_e}, skipping")
                d["_lldp_status"] = "offline"
                updated.append(d)
                continue

        if d.get("lldp_neighbors") and not force:'''

content = content.replace(old_loop, new_loop, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done - online check added to ensure_lldp_on_all_devices")
