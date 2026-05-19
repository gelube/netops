import re

path = r'Z:\netops-ai\web\templates\index.html'
with open(path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# 1. Add _discovering flag near _topoTimer
old = "    // 拓扑实时刷新\n    let _topoTimer = null;"
new = "    // 拓扑实时刷新\n    let _topoTimer = null;\n    let _discovering = false;"
content = content.replace(old, new, 1)

# 2. Add guard + lock in discoverTopology
old_func = """    async function discoverTopology() {
      addMsg('system', '⏳ 正在发现拓扑，可能需要1-2分钟...');
      try {"""
new_func = """    async function discoverTopology() {
      if (_discovering) { addMsg('system', '⏳ 上次发现还在进行中，请稍候'); return; }
      _discovering = true;
      addMsg('system', '⏳ 正在发现拓扑，可能需要1-2分钟...');
      try {"""
content = content.replace(old_func, new_func, 1)

# 3. Add finally block - replace the catch+close in discoverTopology
old_end = """      } catch(e) {
        addMsg('system', '❌ 拓扑发现超时或失败: ' + e.message);
      }
    }"""
new_end = """      } catch(e) {
        addMsg('system', '❌ 拓扑发现超时或失败: ' + e.message);
      } finally {
        _discovering = false;
      }
    }"""
# Only replace the first occurrence (discoverTopology's catch)
idx = content.find(old_end)
if idx > 0:
    content = content[:idx] + new_end + content[idx+len(old_end):]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done - 3 replacements made")
