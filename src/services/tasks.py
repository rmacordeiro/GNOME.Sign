"""Tiny helper to run blocking work in a thread and deliver the result on the GLib main loop."""
import threading

from gi.repository import GLib


class CancelToken:
    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    def is_cancelled(self):
        return self._event.is_set()


def run_in_thread(work, on_done, token=None):
    """Runs work(token) in a daemon thread; calls on_done(result, error) on the main loop unless cancelled."""
    token = token or CancelToken()

    def runner():
        try:
            result, error = work(token), None
        except Exception as e:  # delivered to the caller, never raised in the thread
            result, error = None, e
        if not token.is_cancelled():
            GLib.idle_add(lambda: on_done(result, error) or GLib.SOURCE_REMOVE)

    threading.Thread(target=runner, daemon=True).start()
    return token
