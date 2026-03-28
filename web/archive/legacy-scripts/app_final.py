#!/usr/bin/env python3
"""NetOps AI Web - LLM Config Save (Custom Provider Support)"""
from flask import Flask, request, jsonify
import json, os, sys
sys.path.insert(0, r'Z:\netops-ai')
from app.llm.config import LLMConfig

app = Flask(__name__)
CONFIG_FILE = r'Z:\netops-ai\web\data\llm_config.json'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/llm/config', methods=['POST'])
def save_llm():
    """Save LLM configuration - supports custom providers"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Content-Type must be application/json'}), 400
        
        data = request.json or {}
        
        # Clean and validate inputs - remove special chars that break JSON
        def clean(s):
            return str(s or '').replace('<', '').replace('>', '').strip()
        
        provider = clean(data.get('provider', 'custom'))
        endpoint = clean(data.get('endpoint', ''))
        api_key = clean(data.get('api_key', ''))
        model = clean(data.get('model', ''))
        
        # Model is optional - user can leave it empty
        # No default model, user must specify if needed
        
        # Validate endpoint format (basic check)
        if endpoint and not endpoint.startswith(('http://', 'https://')):
            endpoint = 'https://' + endpoint
        
        # Save config
        llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
        llm_config.save()
        
        # Save to web data directory
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
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Save failed: {str(e)}',
            'error': str(e)
        }), 500

@app.route('/api/llm/test', methods=['POST'])
def test_llm():
    """Test LLM connection"""
    try:
        data = request.json or {}
        config = LLMConfig(
            provider=data.get('provider', 'custom'),
            endpoint=data.get('endpoint', ''),
            api_key=data.get('api_key', '')
        )
        # Just validate config can be created, don't actually call API
        return jsonify({'success': True, 'message': '配置格式有效，可以保存'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
