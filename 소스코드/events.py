"""워커 큐를 Tk 이벤트로 전달한다. 대기 중 폴링하지 않는다."""
import queue
import threading
import tkinter as tk


class MainThreadEvents:
    def __init__(self, root, handler):
        self.root, self.handler = root, handler
        self.queue = queue.Queue()
        self.wake = threading.Event()
        self.closed = False
        self.thread = threading.Thread(target=self._bridge, name="CaptureEvents", daemon=True)
        self.root.bind("<<CaptureEvent>>", self._drain)
        self.root.after_idle(self.thread.start)

    def put(self, event):
        if not self.closed:
            self.queue.put(event)
            self.wake.set()

    def _bridge(self):
        while True:
            self.wake.wait()
            self.wake.clear()
            if self.closed:
                return
            try:
                # _tkinter가 메인 스레드로 전달한다. Win32 콜백에서 Tcl을
                # 직접 재진입하지 않아 Python 3.14의 GIL 충돌을 피한다.
                self.root.event_generate("<<CaptureEvent>>", when="tail")
            except (tk.TclError, RuntimeError):
                return

    def _drain(self, event=None):
        while not self.closed:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                return
            try:
                self.handler(item)
            except Exception:
                import sys
                self.root.report_callback_exception(*sys.exc_info())

    def close(self):
        self.closed = True
        self.wake.set()
