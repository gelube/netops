# Core module
from app.core.device import (
    Vendor as Vendor,
    DeviceType as DeviceType,
    PortType as PortType,
    PortStatus as PortStatus,
    Device as Device,
    Interface as Interface,
    Link as Link,
    Topology as Topology,
)
from app.core.vendor import VendorIdentifier as VendorIdentifier


# Lazy imports to avoid circular dependency
def __getattr__(name):
    if name in ("TopologyDiscovery", "DiscoveryResult"):
        from app.core.discovery import TopologyDiscovery, DiscoveryResult

        return {"TopologyDiscovery": TopologyDiscovery, "DiscoveryResult": DiscoveryResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
