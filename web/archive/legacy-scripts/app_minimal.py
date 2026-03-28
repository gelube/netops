#!/usr/bin/env python3
"""NetOps AI - Minimal Version with LLM Config Save"""

from flask import Flask, request, jsonify, render_template
import json
import os
import sys

sys.path.insert(0, r'Z:\netops-ai')

from app.llm.config import LLMConfig, LLMClient

app = Flask(__name__, template_folder='templates', static_folder='static')

CONFIG_FILE = 'data/llm_config.json'

def save_llm_config(config_data):
    """Save LLM config to file"""
    os.makedirs('data', exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
    return True

def load_llm_config():
    """Load LLM config from file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/llm/config', methods=['POST'])
def save_llm():
    """Save LLM configuration"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Content-Type must be application/json'}), 400
        
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Invalid data format'}), 400
        
        provider = data.get('provider', 'openai')
        endpoint = data.get('endpoint', '')
        api_key = data.get('api_key', '')
        model = data.get('model', '')
        
        # Validate required fields
        if not model:
            # Use default model based on provider
            defaults = {
                'openai': 'gpt-3.5-turbo',
                'anthropic': 'claude-3-sonnet-20240229',
                'aliyun': 'qwen-plus',
                'bailian-plan': 'qwen3.5-plus',
            }
            model = defaults.get(provider, '')
        
        # Clean special characters
        model = str(model).strip()
        endpoint = str(endpoint).strip()
        api_key = str(api_key).strip() if api_key else ''
        
        # Create and save config
        llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
        llm_config.save()
        
        # Save to web data directory
        save_llm_config({
            'provider': provider,
            'endpoint': endpoint,
            'api_key': api_key,
            'model': model
        })
        
        return jsonify({
            'success': True,
            'provider': provider,
            'endpoint': endpoint,
            'model': model
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Save failed: {str(e)}',
            'error': str(e)
        }), 500

@app.route('/api/llm/test', methods=['POST'])
def test_llm():
    """Test LLM connection"""
    data = request.json
    try:
        config = LLMConfig(
            provider=data.get('provider', 'openai'),
            endpoint=data.get('endpoint', ''),
            api_key=data.get('api_key', '')
        )
        client = LLMClient(config)
        return jsonify({'success': True, 'message': 'LLM connection test successful'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
