import re

path = r'Z:\netops-ai\web\templates\index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: chat-messages -> messages in sendChat thinking placeholder
content = content.replace(
    "document.getElementById('chat-messages').insertAdjacentHTML('beforeend', thinkingHtml);",
    "document.getElementById('messages').insertAdjacentHTML('beforeend', thinkingHtml);",
    1
)

# Fix 2: Also fix the thinking-placeholder class to be consistent
# (chat-msg ai -> msg msg-ai) for both thinking placeholders
content = content.replace(
    "'<div class=\"chat-msg ai\" id=\"thinking-placeholder\"><span style=\"color:#67e8f9\">⏳ 思考中...</span></div>'",
    "'<div class=\"msg msg-ai\" id=\"thinking-placeholder\"><span style=\"color:#67e8f9\">⏳ 思考中...</span></div>'"
)
content = content.replace(
    "'<div class=\"chat-msg ai\" id=\"thinking-placeholder\"><span style=\"color:#67e8f9\">⏳ 正在全面诊断...</span></div>'",
    "'<div class=\"msg msg-ai\" id=\"thinking-placeholder\"><span style=\"color:#67e8f9\">⏳ 正在全面诊断...</span></div>'"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done - 3 fixes applied")
