import re

config_file = r"Z:\netops-ai\app\llm\config.py"

with open(config_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复被破坏的 save 方法
pattern = r"def save\(self.*?\n(.*?)\n    @classmethod"
replacement = '''def save(self, config_dir: str = "~/.netops-ai") -> None:
        """保存配置到文件"""
        config_path = os.path.join(os.path.expanduser(config_dir), "llm_config.json")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # 简单实现：只保存非敏感配置
        config_data = {
            "provider": self.provider.value,
            "endpoint": self.endpoint,
            "model": self.model,
        }
        
        import json
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"LLM config saved to: {config_path}")
        except Exception as e:
            print(f"Failed to save config: {e}")
            raise
    
    @classmethod'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open(config_file, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Fixed!")
