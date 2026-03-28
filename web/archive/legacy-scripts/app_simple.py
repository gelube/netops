#!/usr/bin/env python3
"""NetOps AI Web - Simple Local LLM Config Page"""
from flask import Flask, request, jsonify, send_file
import json, os, sys

CONFIG_FILE = r'Z:\netops-ai\web\data\llm_config.json'

app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_file(r'Z:\netops-ai\web\templates\index_simple.html')

@app.route('/api/llm/config', methods=['POST', 'GET'])
def handle_llm_config():
    if request.method == 'GET':
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        return jsonify({})
    
    # POST - save config
    try:
        data = request.json or {}
        
        def clean(s):
            return str(s or '').replace('<', '').replace('>', '').strip()
        
        provider = clean(data.get('provider', 'openai'))
        endpoint = clean(data.get('endpoint', ''))
        api_key = clean(data.get('api_key', 'ollama'))
        model = clean(data.get('model', ''))
        
        if endpoint and not endpoint.startswith(('http://', 'https://')):
            endpoint = 'http://' + endpoint
        
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'provider': provider,
                'endpoint': endpoint,
                'api_key': api_key,
                'model': model
            }, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'provider': provider,
            'endpoint': endpoint,
            'model': model
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/llm/test', methods=['POST'])
def test_llm():
    try:
        data = request.json or {}
        endpoint = str(data.get('endpoint', '')).strip()
        api_key = str(data.get('api_key', 'ollama')).strip()
        
        if not endpoint:
            return jsonify({'success': False, 'message': 'Endpoint required'})
        
        import requests
        headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
        base = endpoint.rstrip('/')
        if '/v1' not in base:
            base = base + '/v1'
        
        resp = requests.get(f'{base}/models', headers=headers, timeout=5)
        
        if resp.status_code == 200:
            models_data = resp.json()
            models = [m.get('id', str(m)) for m in models_data.get('data', [])]
            return jsonify({
                'success': True,
                'message': f'连接成功，{len(models)} 个模型',
                'models': models[:10]
            })
        else:
            return jsonify({'success': True, 'message': f'端点可达 (HTTP {resp.status_code})'})
    
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': '无法连接，请检查 URL 和端口'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
