"""Fix: add Content-Type header to topology/discover fetch calls in index.html"""
import sys

filepath = r'Z:\netops-ai\web\templates\index.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: btn-refresh-now onclick (line ~342)
old1 = "const r = await fetch('/api/topology/discover', { method: 'POST', signal: controller.signal });"
new1 = "const r = await fetch('/api/topology/discover', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({}), signal: controller.signal });"

count1 = content.count(old1)
content = content.replace(old1, new1)

# Fix 2: discoverTopology function (line ~1076)
old2 = "const r = await fetch('/api/topology/discover', { method: 'POST', signal: controller.signal });"
new2 = "const r = await fetch('/api/topology/discover', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({}), signal: controller.signal });"

# This is same string as old1, already replaced. Check if there are remaining occurrences
count2 = content.count(old2)
content = content.replace(old2, new2)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Fixed {count1} + {count2} occurrences of discover fetch without Content-Type")
