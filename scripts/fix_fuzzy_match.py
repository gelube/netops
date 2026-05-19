"""Add fuzzy device name matching to chat.py - match when device name contains or is contained in LLM output"""
import sys

filepath = r'Z:\netops-ai\web\blueprints\chat.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Helper function to add after imports
helper_func = '''

def _match_device(devices, dev_name):
    """Match device by exact name, then by substring containment"""
    if not dev_name:
        return None
    # Exact match first
    for d in devices:
        if d.get("name") == dev_name or d.get("remark") == dev_name or d.get("ip") == dev_name:
            return d
    # Substring match: LLM name contains device name or vice versa
    for d in devices:
        dn = d.get("name", "")
        dr = d.get("remark", "")
        if (dn and (dn in dev_name or dev_name in dn)) or (dr and (dr in dev_name or dev_name in dr)):
            return d
    return None

'''

# Insert helper after the module-level constants (after _CHAT_KEYWORDS)
anchor = "_CHAT_KEYWORDS = "
idx = content.find(anchor)
if idx < 0:
    print("ERROR: cannot find _CHAT_KEYWORDS")
    sys.exit(1)
# Find end of that line
end = content.find('\n', idx)
content = content[:end+1] + helper_func + content[end+1:]

# Now replace 3 occurrences of the device matching pattern
# Pattern 1: main run_commands branch (exact match block)
old1 = """                        dev = None
                        for d in devices:
                            if (
                                d.get("name") == dev_name
                                or d.get("remark") == dev_name
                                or d.get("ip") == dev_name
                            ):
                                dev = d
                                break
                        if dev:"""

new1 = """                        dev = _match_device(devices, dev_name)
                        if dev:"""

count1 = content.count(old1)
content = content.replace(old1, new1)

# Pattern 2: _QUERY_MAP branch
old2 = """                        dev = None
                        for d in devices:
                            if d.get("name") == dev_name or d.get("remark") == dev_name or d.get("ip") == dev_name:
                                dev = d
                                break
                        if dev:"""

new2 = """                        dev = _match_device(devices, dev_name)
                        if dev:"""

count2 = content.count(old2)
content = content.replace(old2, new2)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Replaced {count1} exact-match blocks (pattern1) and {count2} (pattern2)")
print(f"Added _match_device helper function")
