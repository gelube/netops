with open('Z:/netops-ai/web/app.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('    else:\n            pass\n', '    else:\n        pass\n')
with open('Z:/netops-ai/web/app.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Done')
