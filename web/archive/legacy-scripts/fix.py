import re

HTML_PATH = 'Z:/netops-ai/web/templates/index.html'

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

i = content.find('if (!model)')
if i < 0:
    print("Not found")
    exit(1)

b1 = content.find('{', i)
b2 = content.find('}', b1) + 1
old = content[i:b2]

new = 'const clean=(s)=>String(s||"").replace(/[<>]/g,"").trim();provider=clean(provider);endpoint=clean(endpoint);apiKey=clean(apiKey);model=clean(model);if(!model)model={"openai":"gpt-3.5-turbo","bailian-plan":"qwen3.5-plus"}[provider]||"";'

content = content[:i] + new + content[b2:]

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed!")
