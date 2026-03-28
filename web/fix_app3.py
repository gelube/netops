APP_PATH = 'Z:/netops-ai/web/app.py'
with open(APP_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the incorrectly indented pass statements
content = content.replace('    else:\n            pass\n', '    else:\n        pass\n')

with open(APP_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed indentation")
