"""Test plugin for hot-reload testing."""

from crypto_portfolio_analyzer.core.plugin_manager import BasePlugin

class TestPlugin(BasePlugin):
    """A simple test plugin."""
    
    __version__ = "1.0.0"
    __author__ = "Test Developer"
    
    def __init__(self, name="test_plugin"):
        super().__init__(name)
        self.test_data = "initial_value"
    
    async def initialize(self):
        print(f"TestPlugin initialized with data: {self.test_data}")
        self.test_data = "initialized"
    
    async def teardown(self):
        print(f"TestPlugin shutting down")
        self.test_data = "shutdown"
    
    async def on_command_start(self, command_name, context):
        print(f"TestPlugin: Command started - {command_name}")
