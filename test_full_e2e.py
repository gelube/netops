#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full E2E test: confirmed commands on telnet devices"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json
import urllib.request

BASE = "http://127.0.0.1:5000"

def api(path, method="GET", data=None, timeout=30):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"Content-Type": "application/json"} if body else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw)
    except Exception as e:
        return 0, {"error": str(e)}

passed = 0
failed = 0

def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")
    if detail:
        print(f"        {detail[:200]}")

print("=" * 60)
print("NetOps AI — E2E Command Execution Test")
print("=" * 60)

# 1. Confirmed commands on SW1 (telnet)
print("\n--- 1. Confirmed Commands (SW1 telnet) ---")
cmds = [
    {"device": "SW1", "commands": ["display version"]},
]
s, d = api("/api/chat", "POST", {"confirmed_commands": cmds}, timeout=30)
check("SW1 display version", s == 200 and d.get("success") and d.get("executed"))
if d.get("results"):
    for r in d["results"]:
        check("  SW1 output", "Comware" in str(r.get("results", "")) or "H3C" in str(r.get("results", "")))

# 2. Multiple commands on SW1
print("\n--- 2. Multiple Commands (SW1) ---")
cmds = [
    {"device": "SW1", "commands": ["display version", "display device"]},
]
s, d = api("/api/chat", "POST", {"confirmed_commands": cmds}, timeout=30)
check("SW1 multiple commands", s == 200 and d.get("success"))
if d.get("results"):
    for r in d["results"]:
        num_outputs = len(r.get("results", []))
        check(f"  {num_outputs} outputs", num_outputs == 2)

# 3. Confirmed commands on SW2
print("\n--- 3. Confirmed Commands (SW2 telnet) ---")
cmds = [
    {"device": "SW2", "commands": ["display version"]},
]
s, d = api("/api/chat", "POST", {"confirmed_commands": cmds}, timeout=30)
check("SW2 display version", s == 200 and d.get("success"))

# 4. Non-existent device
print("\n--- 4. Error Handling ---")
cmds = [
    {"device": "nonexistent", "commands": ["display version"]},
]
s, d = api("/api/chat", "POST", {"confirmed_commands": cmds}, timeout=10)
check("Non-existent device fails gracefully", s == 200 and not d.get("success"))

# 5. Collect device (uses CommandService internally)
print("\n--- 5. Device Collection ---")
s, d = api("/api/device/collect", "POST", {"device": "SW1", "type": "version"}, timeout=30)
check("Collect SW1 version", s == 200 and d.get("success"))

# 6. Topology discover
print("\n--- 6. Topology ---")
s, d = api("/api/topology/discover", "POST", {}, timeout=60)
check("Topology discover", s == 200 and d.get("success"))
if d.get("state"):
    links = d["state"].get("links", [])
    check(f"  Links found: {len(links)}", len(links) >= 1)

# 7. Quick config (template match)
print("\n--- 7. Quick Config ---")
s, d = api("/api/quick-config", "POST", {
    "device": "SW1",
    "type": "vlan",
    "parameters": {"vlan_id": "10", "name": "test"}
}, timeout=30)
check("Quick config template", s == 200 and (d.get("success") or d.get("commands")))

# 8. Chat with response field
print("\n--- 8. Chat API Compatibility ---")
s, d = api("/api/chat", "POST", {"message": "hello", "context": {}}, timeout=30)
check("Chat returns response", s == 200 and "response" in d and "message" in d)
check("response == message", d.get("response") == d.get("message"))

# Summary
print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print("FAILURES DETECTED")
print("=" * 60)
