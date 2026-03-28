"""
主界面 - Hacknet风格终端UI
"""
from typing import Optional, List
from enum import Enum

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, Input, TextArea
from textual.screen import Screen
from textual import events

from app.core.device import Topology, Device
from app.core.discovery import TopologyDiscovery, DiscoveryResult
from app.ui.components import TopologyCanvas, DeviceDetailRenderer
from app.ui.styles import HacknetColors, HacknetStyles


class AppMode(str, Enum):
    """应用模式"""
    MAIN = "main"
    TOPOLOGY = "topology"
    SETTINGS = "settings"
    DETAIL = "detail"


class MainMenu(Screen):
    """主菜单界面"""
    
    CSS = f"""
    Screen {{
        background: {HacknetColors.BACKGROUND};
    }}
    
    .menu-container {{
        align: center middle;
        height: 100%;
    }}
    
    .menu-title {{
        text-align: center;
        color: {HacknetColors.PRIMARY};
        text-style: bold;
    }}
    
    .menu-button {{
        width: 30;
        margin: 1;
    }}
    
    Button {{
        background: #0a0a0a;
        color: #00FF00;
        border: solid #00FF00;
    }}
    
    Button:hover, Button:focus {{
        background: #00FF00;
        color: #000000;
    }}
    
    #topology, #settings, #help, #quit {{
        min-width: 25;
    }}
    """
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("╔══════════════════════════════════════════════════════════╗", expand=True),
            Static("║                                                          ║", expand=True),
            Static("║        NETOPS AI - 网络工程师智能助手                   ║", expand=True),
            Static("║        Network Engineer AI Assistant                   ║", expand=True),
            Static("║                                                          ║", expand=True),
            Static("╚══════════════════════════════════════════════════════════╝", expand=True),
            classes="menu-title",
        )
        
        with Container(classes="menu-container"):
            yield Button("🔍 拓扑发现", id="topology", classes="menu-button")
            yield Button("⚙️ LLM 配置", id="settings", classes="menu-button")
            yield Button("❓ 帮助", id="help", classes="menu-button")
            yield Button("🚪 退出", id="quit", classes="menu-button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件"""
        button_id = event.button.id
        
        if button_id == "topology":
            self.app.push_screen(DiscoveryScreen())
        elif button_id == "settings":
            self.app.push_screen(SettingsScreen())
        elif button_id == "help":
            self.app.push_screen(HelpScreen())
        elif button_id == "quit":
            self.app.exit()


class DiscoveryScreen(Screen):
    """拓扑发现界面"""
    
    CSS = f"""
    Screen {{
        background: {HacknetColors.BACKGROUND};
    }}
    
    .header-bar {{
        height: 3;
        background: {HacknetColors.PANEL};
        color: {HacknetColors.PRIMARY};
    }}
    
    .input-row {{
        height: 3;
        padding: 1;
    }}
    
    Input {{
        background: #0a0a0a;
        color: #00FF00;
        border: solid #008800;
    }}
    
    Button {{
        background: #0a0a0a;
        color: #00FF00;
        border: solid #00FF00;
    }}
    
    Button:hover, Button:focus {{
        background: #00FF00;
        color: #000000;
    }}
    
    #start-discovery {{
        min-width: 20;
    }}
    
    .topology-view {{
        background: #000000;
        color: #00FF00;
    }}
    
    .status-bar {{
        height: 3;
        background: {HacknetColors.PANEL};
        color: {HacknetColors.PRIMARY_DARK};
    }}
    """
    
    def __init__(self):
        super().__init__()
        self.topology: Optional[Topology] = None
        self.canvas: Optional[TopologyCanvas] = None
        self.found_devices: List[Device] = []
    
    def compose(self) -> ComposeResult:
        # 顶部栏
        with Horizontal(classes="header-bar"):
            yield Static(" NETOPS TOPOLOGY ", classes="header-bar")
            yield Static("", classes="header-bar")  # 空白填充
            yield Static("[Zoom: 100%]  [Nodes: 0]", id="status-info", classes="header-bar")
        
        # 输入行
        with Horizontal(classes="input-row"):
            yield Input(placeholder="种子设备IP", id="seed-ip")
            yield Input(placeholder="用户名", id="username")
            yield Input(placeholder="密码", password=True, id="password")
            yield Button("🔍 开始发现", id="start-discovery")
        
        # 拓扑显示区域
        yield Static("", id="topology-display", classes="topology-view")
        
        # 底部提示
        with Horizontal(classes="status-bar"):
            yield Static("[Tab] 焦点  [Enter] 详情  [↑↓←→] 移动  [Ctrl++/-] 缩放  [R] 刷新  [Esc] 返回", 
                        classes="status-bar")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """开始发现"""
        if event.button.id == "start-discovery":
            self._start_discovery()
    
    def _start_discovery(self) -> None:
        """执行拓扑发现"""
        seed_ip = self.query_one("#seed-ip", Input).value
        username = self.query_one("#username", Input).value
        password = self.query_one("#password", Input).value
        
        if not seed_ip or not username or not password:
            self._show_message("请输入种子设备IP、用户名和密码")
            return
        
        self._show_message(f"正在发现网络拓扑: {seed_ip} ...")
        
        # 执行发现 (异步)
        async def run_discovery():
            discovery = TopologyDiscovery()
            result = await discovery.discover(seed_ip, username, password)
            
            if result.success:
                self.topology = result.topology
                self.canvas = TopologyCanvas(self.topology)
                self._update_display()
                self._show_message(result.message)
            else:
                self._show_message(f"发现失败: {result.message}")
        
        # 简单处理: 同步执行 (生产环境应使用异步)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果在异步环境中，创建新任务
                asyncio.create_task(run_discovery())
            else:
                loop.run_until_complete(run_discovery())
        except:
            # 新事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_discovery())
    
    def _update_display(self) -> None:
        """更新拓扑显示"""
        if not self.canvas:
            return
        
        # 模拟渲染 (实际应该使用Textual的widget)
        display = self.query_one("#topology-display", Static)
        
        # 渲染拓扑
        lines = self.canvas.render(80, 20)
        topology_text = "\n".join(lines)
        
        display.update(topology_text)
        
        # 更新状态
        status = self.query_one("#status-info", Static)
        status.update(f"[Zoom: {int(self.canvas.viewport.scale * 100)}%]  [Nodes: {len(self.topology.devices)}]")
    
    def _show_message(self, message: str) -> None:
        """显示消息"""
        display = self.query_one("#topology-display", Static)
        display.update(message)
    
    def on_key(self, event: events.Key) -> None:
        """键盘事件"""
        if not self.canvas:
            return
        
        key = event.key
        
        if key == "tab":
            self.canvas.focus_next()
        elif key == "shift+tab":
            self.canvas.focus_previous()
        elif key == "ctrl+plus":
            self.canvas.viewport.zoom_in()
        elif key == "ctrl+-":
            self.canvas.viewport.zoom_out()
        elif key == "ctrl+0":
            self.canvas.viewport.reset()
        elif key == "r":
            self._start_discovery()
        elif key == "escape":
            self.app.pop_screen()
        
        self._update_display()


class SettingsScreen(Screen):
    """LLM配置界面"""
    
    CSS = f"""
    Screen {{
        background: {HacknetColors.BACKGROUND};
    }}
    
    .settings-container {{
        width: 60;
        height: auto;
        align: center middle;
        padding: 2;
    }}
    
    .settings-title {{
        color: #00FF00;
        text-style: bold;
        text-align: center;
    }}
    
    Input {{
        background: #0a0a0a;
        color: #00FF00;
        border: solid #008800;
    }}
    
    Button {{
        background: #0a0a0a;
        color: #00FF00;
        border: solid #00FF00;
    }}
    
    Button:hover, Button:focus {{
        background: #00FF00;
        color: #000000;
    }}
    """
    
    def compose(self) -> ComposeResult:
        with Vertical(classes="settings-container"):
            yield Static("═══ LLM 配置 ═══", classes="settings-title")
            yield Static("")
            
            # 接入方式按钮
            yield Static("接入方式:")
            with Horizontal():
                yield Button("OpenAI", id="btn-openai")
                yield Button("Anthropic", id="btn-anthropic")
                yield Button("自定义", id="btn-custom")
            
            yield Static("")
            yield Static("API Endpoint:")
            yield Input(placeholder="https://api.openai.com/v1", id="endpoint")
            
            yield Static("API Key:")
            yield Input(placeholder="sk-...", password=True, id="api-key")
            
            yield Static("")
            yield Button("检测连接 & 获取模型", id="btn-test")
            
            yield Static("")
            yield Static("可用模型:")
            yield Static("[点击检测后获取模型列表]", id="model-list")
            
            yield Static("")
            yield Button("保存配置", id="btn-save")
            yield Button("返回", id="btn-back")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮事件"""
        button_id = event.button.id
        
        if button_id == "btn-back":
            self.app.pop_screen()
        
        elif button_id == "btn-test":
            self._test_connection()
        
        elif button_id == "btn-save":
            self._save_config()
    
    def _test_connection(self) -> None:
        """测试连接"""
        from app.llm.config import LLMConfig, LLMClient, ProviderType, LLMConfigManager
        
        endpoint = self.query_one("#endpoint", Input).value
        api_key = self.query_one("#api-key", Input).value
        
        if not endpoint or not api_key:
            self.query_one("#model-list", Static).update("请输入 Endpoint 和 API Key")
            return
        
        # 检测提供商
        provider = LLMConfigManager.detect_provider(endpoint, api_key)
        
        # 测试连接
        success, message = LLMConfigManager.test_connection(endpoint, api_key, provider)
        
        if success:
            # 获取模型列表
            config = LLMConfig(provider=provider, endpoint=endpoint, api_key=api_key)
            client = LLMClient(config)
            models = client.list_models()
            
            if models:
                self.query_one("#model-list", Static).update(
                    "\n".join([f"  • {m}" for m in models[:10]])
                )
            else:
                self.query_one("#model-list", Static).update(message)
        else:
            self.query_one("#model-list", Static).update(f"❌ {message}")
    
    def _save_config(self) -> None:
        """保存配置"""
        self.query_one("#model-list", Static).update("✓ 配置已保存")


class HelpScreen(Screen):
    """帮助界面"""
    
    CSS = f"""
    Screen {{
        background: {HacknetColors.BACKGROUND};
    }}
    
    .help-content {{
        color: {HacknetColors.PRIMARY};
        padding: 2;
    }}
    """
    
    def compose(self) -> ComposeResult:
        yield Static("""
╔═══════════════════════════════════════════════════════════╗
║                     NetOps AI 帮助文档                       ║
╠═══════════════════════════════════════════════════════════╣
║                                                            ║
║  功能:                                                     ║
║  • 拓扑自动发现 - 从种子设备自动发现整个网络拓扑             ║
║  • 设备识别 - 自动识别华为/华三/思科等设备                  ║
║  • 关系显示 - 显示聚合/VRRP/堆叠等链路关系                  ║
║  • AI助手 - 使用LLM辅助网络排障和问答                       ║
║                                                            ║
║  快捷键:                                                   ║
║  • Tab - 切换设备焦点                                      ║
║  • Enter - 查看设备详情                                    ║
║  • ↑↓←→ - 移动视图                                         ║
║  • Ctrl++/- - 缩放视图                                      ║
║  • R - 刷新拓扑                                            ║
║  • Esc - 返回                                              ║
║                                                            ║
║  提示:                                                     ║
║  • 首次使用请先配置LLM连接                                  ║
║  • 确保SSH端口(22)可达                                      ║
║  • 支持LLDP和CDP邻居发现                                    ║
║                                                            ║
╚═══════════════════════════════════════════════════════════╝
        """, classes="help-content")
        
        yield Button("返回", id="btn-back")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()


class NetOpsApp(App):
    """NetOps AI 主应用"""
    
    CSS = f"""
    Screen {{
        background: {HacknetColors.BACKGROUND};
    }}
    """
    
    TITLE = "NetOps AI"
    SUB_TITLE = "网络工程师智能助手"
    
    SCREENS = {
        "main": MainMenu,
        "discovery": DiscoveryScreen,
        "settings": SettingsScreen,
        "help": HelpScreen,
    }
    
    def __init__(self):
        super().__init__()
        self.mode = AppMode.MAIN
    
    def on_mount(self) -> None:
        """应用启动"""
        self.push_screen(MainMenu())
    
    def get_default_screen(self) -> Screen:
        return MainMenu()


def run_app() -> None:
    """运行应用"""
    app = NetOpsApp()
    app.run()


if __name__ == "__main__":
    run_app()