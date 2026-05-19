"""Shared utility functions for NetOps-AI blueprints."""

import json
import os
import threading

# Global devices file lock (shared across all blueprints)
_devices_lock = threading.Lock()


def get_devices_lock():
    """Return the shared devices file lock."""
    return _devices_lock


def load_devices(devices_file: str) -> list:
    """Load devices from JSON file with thread-safe locking."""
    with _devices_lock:
        if os.path.exists(devices_file):
            with open(devices_file, "r", encoding="utf-8") as f:
                return json.load(f)
    return []


def save_devices(devices_file: str, devices: list) -> None:
    """Save devices to JSON file atomically with thread-safe locking."""
    with _devices_lock:
        tmp = devices_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
        # Atomic replace
        if os.path.exists(devices_file):
            os.replace(tmp, devices_file)
        else:
            os.replace(tmp, devices_file)


def atomic_write_json(filepath: str, data, indent=2) -> None:
    """Write JSON atomically: write to .tmp then os.replace."""
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, filepath)
