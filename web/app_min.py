#!/usr/bin/env python3
"""NetOps AI Web - Minimal LLM Config Save"""
from flask import Flask, request, jsonify, render_template
import json, os, sys
sys.path.insert(0, r'Z:\netops-ai')
from app.llm.config import LLMConfig, LLMClient

app = Flask(__name__, template_folder=r'Z:\netops-ai\web\templates', static_folder=r'Z:\netops-ai\web\static')
CONFIG_FILE = r'Z:\netops-ai\web\data\llm_config.json'

def save_llm_config(d):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(d, f, ensure_ascii=False, indent=2)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/llm/config', methods=['POST'])
def save_llm():
    try:
        data = request.json or {}
        provider = str(data.get('provider', 'openai')).strip()
        endpoint = str(data.get('endpoint', '')).strip()
        api_key = str(data.get('api_key', '')).strip()
        model = str(data.get('model', '')).strip()
        if not model:
            model = {'openai': 'gpt-3.5-turbo', 'bailian-plan': 'qwen3.5-plus', 'aliyun': 'qwen-plus'}.get(provider, '')
        # Clean special chars
        for s in [provider, endpoint, api_key, model]:
            if any(c in s for c in '<>'): raise ValueError('Invalid characters in input')
        llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
        llm_config.save()
        save_llm_config({'provider': provider, 'endpoint': endpoint, 'api_key': api_key, 'model': model})
        return jsonify({'success': True, 'provider': provider, 'model': model})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
