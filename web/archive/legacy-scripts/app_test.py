#!/usr/bin/env python3
from flask import Flask, request, jsonify
import json, os, sys
sys.path.insert(0, r'Z:\netops-ai')
from app.llm.config import LLMConfig

app = Flask(__name__)
CONFIG_FILE = r'Z:\netops-ai\web\data\llm_config.json'

@app.route('/test')
def test():
    return jsonify({'status': 'ok'})

@app.route('/api/llm/config', methods=['POST'])
def save_llm():
    print(f"Received request: {request.method} {request.path}")
    print(f"Content-Type: {request.content_type}")
    print(f"Data: {request.data}")
    try:
        if not request.is_json:
            print("Not JSON")
            return jsonify({'success': False, 'message': 'Not JSON'}), 400
        data = request.json
        print(f"Parsed JSON: {data}")
        if not data:
            return jsonify({'success': False, 'message': 'Empty'}), 400
        provider = str(data.get('provider', 'openai')).strip()
        model = str(data.get('model', '')).strip()
        if not model:
            model = {'openai': 'gpt-3.5-turbo', 'bailian-plan': 'qwen3.5-plus'}.get(provider, '')
        llm_config = LLMConfig(provider=provider, endpoint=str(data.get('endpoint','')).strip(), api_key=str(data.get('api_key','')).strip(), model=model)
        llm_config.save()
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'provider':provider,'endpoint':data.get('endpoint',''),'api_key':data.get('api_key',''),'model':model}, f, indent=2)
        print("Saved successfully")
        return jsonify({'success': True, 'provider': provider, 'model': model})
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
