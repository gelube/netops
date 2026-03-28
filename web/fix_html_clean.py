"""Clean up duplicated JS code in index.html"""

HTML_PATH = 'Z:/netops-ai/web/templates/index.html'

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove BOM if present
if content.startswith('\ufeff'):
    content = content[1:]

# Remove duplicated "const clean" lines
old_dupe = """const clean = (s) => String(s || '').replace(/[<>]/g, '').trim();
              provider = clean(provider);
              endpoint = clean(endpoint);
              apiKey = clean(apiKey);
              model = clean(model);
              const clean=(s)=>String(s||"").replace(/[<>]/g,"").trim();provider=clean(provider);endpoint=clean(endpoint);apiKey=clean(apiKey);model=clean(model);if(!model)model={"openai":"gpt-3.5-turbo","bailian-plan":"qwen3.5-plus"}[provider]||"";[provider] || '';"""

new_clean = """// Clean special characters (prevent < > breaking JSON)
              const clean = (s) => String(s || '').replace(/[<>]/g, '').trim();
              provider = clean(provider);
              endpoint = clean(endpoint);
              apiKey = clean(apiKey);
              model = clean(model);
              // Model is optional for local LLM"""

if old_dupe in content:
    content = content.replace(old_dupe, new_clean)
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Cleaned duplicated code")
else:
    # Try simpler approach
    import re
    pattern = r'const clean=\(s\)=>String\(s\|\|""\)\.replace\(/\[<>\]/g,""\)\.trim\(\);provider=clean\(provider\);.*?\|\|\'\';'
    if re.search(pattern, content):
        content = re.sub(pattern, new_clean, content)
        with open(HTML_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Cleaned with regex")
    else:
        print("Pattern not found, manual check needed")
        idx = content.find('const clean=(s)=>')
        if idx > 0:
            print(f"Found at {idx}")
            print(content[idx:idx+200])
