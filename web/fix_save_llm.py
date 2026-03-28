#!/usr/bin/env python3
"""修复 LLM 保存 - 添加错误处理"""

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''@app.route('/api/llm/config', methods=['POST'])
def save_llm():
    global llm_config, llm_client
    
    data = request.json
    provider = ProviderType(data.get('provider', 'openai'))
    endpoint = data.get('endpoint', '')
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    
    llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
    llm_client = LLMClient(llm_config)
    llm_config.save()
    
    # 保存到文件（包含 api_key）
    save_llm_config({
        'provider': provider.value,
        'endpoint': endpoint,
        'api_key': api_key,
        'model': model
    })
    
    return jsonify({
        'success': True,
        'provider': provider.value,
        'endpoint': endpoint,
        'model': model
    })'''

new_code = '''@app.route('/api/llm/config', methods=['POST'])
def save_llm():
    global llm_config, llm_client
    
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': '无效的数据格式'}), 400
        
        provider = ProviderType(data.get('provider', 'openai'))
        endpoint = data.get('endpoint', '')
        api_key = data.get('api_key', '')
        model = data.get('model', '')
        
        llm_config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key, model=model)
        llm_client = LLMClient(llm_config)
        llm_config.save()
        
        # 保存到文件（包含 api_key）
        save_llm_config({
            'provider': provider.value,
            'endpoint': endpoint,
            'api_key': api_key,
            'model': model
        })
        
        return jsonify({
            'success': True,
            'provider': provider.value,
            'endpoint': endpoint,
            'model': model
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'保存失败：{str(e)}',
            'error': str(e)
        }), 500'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("[OK] Added error handling to save_llm")
else:
    print("[ERROR] Could not find save_llm code")
