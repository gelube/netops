"""
Add intent verification after LLM tool_calls — if LLM generated commands
don't match the user's config intent, override with _match_config_command
"""
import re

path = r'Z:\netops-ai\web\blueprints\chat.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the point right after "if commands:" inside the run_commands handler
# We need to add intent verification BEFORE the readonly check
old_block = """                    _READ_ONLY_PREFIXES = ("display ", "show ", "ping ", "traceroute")
                    all_readonly = all(
                        any(cmd.lower().strip().startswith(p) for p in _READ_ONLY_PREFIXES)
                        for cmd in commands
                    )
                    if all_readonly and not preview_only:"""

new_block = """                    # 意图校验：如果用户意图是配置操作但LLM生成了查看命令，用意图映射覆盖
                    _config_intent = _match_config_command(message)
                    if _config_intent and _config_intent != commands:
                        # LLM没理解配置意图，用映射命令覆盖
                        log.info(f"Intent override: LLM={commands}, mapped={_config_intent}")
                        commands = _config_intent.split("\\n")
                    
                    _READ_ONLY_PREFIXES = ("display ", "show ", "ping ", "traceroute")
                    all_readonly = all(
                        any(cmd.lower().strip().startswith(p) for p in _READ_ONLY_PREFIXES)
                        for cmd in commands
                    )
                    if all_readonly and not preview_only:"""

if old_block not in content:
    print("ERROR: Can't find first _READ_ONLY_PREFIXES block")
    # Debug
    idx = content.find("_READ_ONLY_PREFIXES")
    while idx >= 0:
        print(f"Found at {idx}: ...{repr(content[idx:idx+80])}")
        idx = content.find("_READ_ONLY_PREFIXES", idx+1)
    exit(1)

content = content.replace(old_block, new_block, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK - Intent verification added after LLM tool_calls")
