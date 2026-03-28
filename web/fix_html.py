#!/usr/bin/env python3
"""Fix index.html - remove model validation and add sanitization"""

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the model validation with sanitization
old_code = """if (!model) {
                  alert('请先选择模型');
                  return;
              }"""

new_code = """// Clean special characters (prevent < > etc in JSON)
              const clean = (str) => String(str || '').replace(/[<>]/g, '').trim();
              provider = clean(provider);
              endpoint = clean(endpoint);
              apiKey = clean(apiKey);
              model = clean(model);
              
              // Use default model if empty
              if (!model) {
                  const defaults = {
                      'openai': 'gpt-3.5-turbo',
                      'anthropic': 'claude-3-sonnet-20240229',
                      'aliyun': 'qwen-plus',
                      'bailian-plan': 'qwen3.5-plus',
                      'custom': ''
                  };
                  model = defaults[provider] || '';
              }"""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed model validation in index.html")
else:
    print("Could not find the exact code to replace")
    print("Looking for similar patterns...")
    if "if (!model)" in content:
        print("Found 'if (!model)' - context:")
        idx = content.find("if (!model)")
        print(content[idx:idx+200])
