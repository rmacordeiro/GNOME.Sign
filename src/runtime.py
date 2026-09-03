import os


def get_runtime_environment():
    """Returns the packaging/runtime environment used to launch the app."""
    if os.getenv("FLATPAK_ID"):
        return "flatpak"
    if os.getenv("SNAP") or os.getenv("SNAP_NAME"):
        return "snap"
    return "native"


def is_sandboxed_runtime():
    """Returns True when the app is running in a sandboxed package format."""
    return get_runtime_environment() in {"flatpak", "snap"}
