"""Fix index.html - support custom provider, no forced model selection"""

HTML_PATH = 'Z:/netops-ai/web/templates/index.html'

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace model validation with flexible version
import re
pattern = r"if\s*\(\s*!\s*model\s*\)\s*\{[^}]*alert\([^)]*\)[^}]*return[^}]*\}"

new_code = """// Clean special characters (prevent < > breaking JSON)
              const clean = (s) => String(s || '').replace(/[<>]/g, '').trim();
              provider = clean(provider);
              endpoint = clean(endpoint);
              apiKey = clean(apiKey);
              model = clean(model);
              
              // Model is optional - user can leave empty for custom providers
              // No validation, just save what user entered"""

match = re.search(pattern, content)
if match:
    content = content[:match.start()] + new_code + content[match.end():]
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed model validation - now optional")
else:
    print("Pattern not found, checking manually...")
    if 'if (!model)' in content:
        idx = content.find('if (!model)')
        b1 = content.find('{', idx)
        b2 = content.find('}', b1) + 1
        old = content[idx:b2]
        print(f"Found at {idx}: {repr(old[:80])}")
        content = content[:idx] + new_code + content[b2:]
        with open(HTML_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed!")
