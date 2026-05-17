#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NetOps AI Web - 精简入口，逻辑已拆分到blueprints/"""
from flask import Flask, render_template
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

app = Flask(__name__)
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEB_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DEVICES_FILE = os.path.join(DATA_DIR, 'devices.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'llm_config.json')

# 注册蓝图（init_* 是模块级函数，不是 Blueprint 实例方法）
from blueprints import topology_bp, device_bp, chat_bp, sys_bp  # noqa: E402
from blueprints.topology import init_topology_blueprint  # noqa: E402
from blueprints.device import init_device_blueprint  # noqa: E402
from blueprints.chat import init_chat_blueprint  # noqa: E402
from blueprints.system import init_system_blueprint  # noqa: E402

from app.logger import get_logger  # noqa: E402

log = get_logger(__name__)

init_topology_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE)
init_device_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE, project_root=PROJECT_ROOT)
init_chat_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE, project_root=PROJECT_ROOT)
init_system_blueprint(data_dir=DATA_DIR, devices_file=DEVICES_FILE, project_root=PROJECT_ROOT)

app.register_blueprint(topology_bp)
app.register_blueprint(device_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(sys_bp)

# WebSocket
try:
    from ws_push import init_socketio  # noqa: E402
    socketio = init_socketio(app)
except ImportError:
    socketio = None

# CORS 安全：仅允许本机访问（生产环境应配置具体域名）
try:
    from flask_cors import CORS  # noqa: E402
    CORS(app, origins="*")
except ImportError:
    pass


# ===== 首页 =====
@app.route('/')
def index():
    return render_template('index.html')


# 启动
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    if socketio:
        socketio.run(app, host=args.host, port=args.port, debug=args.debug, allow_unsafe_werkzeug=True)
    else:
        app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
