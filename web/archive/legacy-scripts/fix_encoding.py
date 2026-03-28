# 检查并修复 index.html 编码问题
import os

html_path = 'Z:/netops-ai/web/templates/index.html'

# 读取原始字节
with open(html_path, 'rb') as f:
    raw = f.read()

# 尝试不同编码解码
encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'latin-1']
content = None

for enc in encodings:
    try:
        content = raw.decode(enc)
        # 检查是否有正常的中文
        if '网络' in content or '模型' in content or '保存' in content:
            print(f'成功用 {enc} 解码')
            break
    except:
        continue

if content is None:
    print('无法解码文件')
    exit(1)

# 替换常见的乱码模式
replacements = {
    '閸欐牗绉?': '取消',
    '娣囨繂鐡ㄩ': '保存配置',
    '娣囨繂鐡?': '保存',
    '闁板秶鐤?': '配置',
    '缃戠粶宸ョ▼甯堟櫤鑳藉姪': '网络工程师智能助手',
    '妯″瀷': '模型',
    '璁剧疆': '设置',
    '鎺ュ叆鏂瑰紡': '接入方式',
}

for bad, good in replacements.items():
    content = content.replace(bad, good)

# 移除 BOM
if content.startswith('\ufeff'):
    content = content[1:]

# 重新保存为 UTF-8
with open(html_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print('文件已修复')

# 验证
with open(html_path, 'rb') as f:
    verify = f.read(50)
print('验证前50字节:', verify)