# Network module
# Lazy imports to avoid circular dependency
__all__ = ["DeviceConnection", "ConnectionInfo", "test_connection", "LLDPNeighborParser", "LinkTypeDetector", "CommandBuilder"]

def __getattr__(name):
    if name in ["DeviceConnection", "ConnectionInfo", "test_connection"]:
        from app.network.ssh import DeviceConnection, ConnectionInfo, test_connection
        return locals()[name]
    elif name in ["LLDPNeighborParser", "LinkTypeDetector"]:
        from app.network.lldp import LLDPNeighborParser, LinkTypeDetector
        return locals()[name]
    elif name == "CommandBuilder":
        from app.network.commands import CommandBuilder
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")