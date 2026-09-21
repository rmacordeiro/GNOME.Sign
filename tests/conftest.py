import sys
import types


def _install_gi_stub():
    if "gi" in sys.modules:
        return

    gi = types.ModuleType("gi")
    gi.require_version = lambda *args, **kwargs: None

    repository = types.ModuleType("gi.repository")
    repository.GLib = types.SimpleNamespace(get_user_config_dir=lambda: "/tmp")

    gi.repository = repository
    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = repository


_install_gi_stub()
