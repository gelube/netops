# Network module
# Lazy imports to avoid circular dependency
__all__ = ["DeviceConnection", "ConnectionInfo", "test_connection", "LLDPNeighborParser", "LinkTypeDetector", "CommandBuilder"]

def __getattr__(name):
    if name == "DeviceConnection":
        from app.network.ssh import DeviceConnection
        return DeviceConnection
    elif name == "ConnectionInfo":
        from app.network.ssh import ConnectionInfo
        return ConnectionInfo
    elif name == "test_connection":
        from app.network.ssh import test_connection
        return test_connection
    elif name == "LLDPNeighborParser":
        from app.network.lldp import LLDPNeighborParser
        return LLDPNeighborParser
    elif name == "LinkTypeDetector":
        from app.network.lldp import LinkTypeDetector
        return LinkTypeDetector
    elif name == "CommandBuilder":
        from app.network.commands import CommandBuilder
        return CommandBuilder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
