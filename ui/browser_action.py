"""Open a user-requested URL without blocking Tk or touching widgets in a worker."""
import queue
import threading
import time
from core.browser_launcher import open_browser, BrowserNotFoundError


class BrowserAction:
    def __init__(self, owner, completed, *, browser=None, unavailable=None):
        self.owner, self.completed = owner, completed
        self.browser = browser or (lambda: "default")
        self.unavailable = unavailable
        self.pending = queue.Queue()
        self.busy = False
        self.closed = False
        self.job = None

    def open(self, url, *, browser=None):
        if self.busy or self.closed:
            return False
        selected = self.browser() if browser is None else browser
        self.busy = True
        self.started = time.monotonic()
        self.requested_browser = selected
        pending = self.pending = queue.Queue()
        def worker():
            try:
                pending.put(bool(open_browser(url, selected)))
            except BrowserNotFoundError:
                pending.put("missing")
            except Exception:
                pending.put(False)  # URLs include private message text: never log them.
        threading.Thread(target=worker, daemon=True).start()
        self.job = self.owner.after(50, self.poll)
        return True

    def poll(self):
        self.job = None
        if self.closed:
            return
        try:
            success = self.pending.get_nowait()
        except queue.Empty:
            if time.monotonic() - self.started < 10:
                self.job = self.owner.after(50, self.poll)
                return
            success = False
        self.busy = False
        if success == "missing" and self.unavailable is not None:
            self.unavailable()
        else:
            self.completed(False if success == "missing" else success)

    def close(self):
        self.closed = True
        if self.job is not None:
            self.owner.after_cancel(self.job)
            self.job = None
