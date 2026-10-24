"""Platform submission acknowledgements, scoped to the application's window."""

import ctypes
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QObject, pyqtProperty
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QApplication
from PyQt5 import sip

_cursor_owners = set()
_cursor_interval = None


def _steady_cursor(owner, active):
    """Avoid periodic panel updates while retaining the application's preference."""
    global _cursor_interval
    if active:
        if not _cursor_owners:
            _cursor_interval = QApplication.cursorFlashTime()
            QApplication.setCursorFlashTime(0)
        _cursor_owners.add(owner)
    else:
        _cursor_owners.discard(owner)
        if not _cursor_owners and _cursor_interval is not None:
            if QApplication.cursorFlashTime() == 0:
                QApplication.setCursorFlashTime(_cursor_interval)
            _cursor_interval = None


class _Kobo:
    def __init__(self):
        paths = (
            Path(p) / "platforms/libkobo.so" for p in QCoreApplication.libraryPaths()
        )
        path = next(p for p in paths if p.is_file())
        self.library = ctypes.CDLL(str(path))
        signatures = {
            "kobo_set_typing_mode": ([ctypes.c_bool], None),
            "kobo_set_keyboard_regions": (
                [ctypes.POINTER(ctypes.c_int), ctypes.c_int],
                None,
            ),
            "kobo_keyboard_frame": ([], ctypes.c_uint64),
            "kobo_keyboard_region_ready": (
                [ctypes.c_int] * 4 + [ctypes.c_uint64],
                ctypes.c_bool,
            ),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.library, name)
            function.argtypes, function.restype = arguments, result

    def regions(self, rectangles):
        flat = [value for rect in rectangles for value in rect.getRect()]
        values = (ctypes.c_int * len(flat))(*flat)
        self.library.kobo_set_keyboard_regions(values, len(rectangles))
        self.library.kobo_set_typing_mode(bool(rectangles))

    def frame(self):
        return self.library.kobo_keyboard_frame()

    def ready(self, rectangle, frame):
        return self.library.kobo_keyboard_region_ready(*rectangle.getRect(), frame)


class Display(QObject):
    def __init__(self, parent, *, device, family):
        super().__init__(parent)
        self._kindle = device and family == "kindle"
        self._monochrome_keys = family == "kindle"
        self._kobo = (
            _Kobo() if device and QGuiApplication.platformName() == "kobo" else None
        )
        self.minimum_feedback_ms = 0 if self._kobo else 120
        self._sessions = set()
        self._windows = {}
        self._closed = False
        QCoreApplication.instance().aboutToQuit.connect(self.close)

    @pyqtProperty(bool, constant=True)
    def monochromeKeys(self):
        return self._monochrome_keys

    def attach(self, window):
        """Return the Kindle damage refresher, or None on other platforms."""
        if self._kindle and window not in self._windows:
            from .x11 import WindowGrayscaleRefresh

            self._windows[window] = WindowGrayscaleRefresh(window, self)
        return self._windows.get(window)

    def update(self, session, active):
        if self._closed:
            return
        if active:
            self._sessions.add(session)
        else:
            self._sessions.discard(session)
        self._sessions = {s for s in self._sessions if not sip.isdeleted(s)}
        _steady_cursor(self, bool(self._sessions))
        if self._kobo:
            self._kobo.regions(
                [rect for s in self._sessions for rect in s.rectangles()]
            )
        for window, refresh in self._windows.items():
            sessions = [s for s in self._sessions if s.window() == window]
            fields = [s.field_rectangle() for s in sessions]
            refresh.set_typing_regions(
                [rect for s in sessions for rect in s.rectangles()],
                [rect for rect in fields if rect is not None],
            )

    def frame(self, item):
        if self._kobo:
            return self._kobo.frame()
        refresh = self._windows.get(item.window())
        return refresh.frame() if refresh else 0

    def feedback_changed(self, item):
        if self._closed or item.keyboard not in self._sessions:
            return
        refresh = self._windows.get(item.window())
        if refresh:
            refresh.expect_key(item.scene_rectangle())

    def ready(self, item, frame):
        if self._kobo:
            return self._kobo.ready(item.scene_rectangle(), frame)
        refresh = self._windows.get(item.window())
        return not refresh or refresh.key_ready(item.scene_rectangle(), frame)

    def close(self):
        if self._closed:
            return
        self._closed = True
        _steady_cursor(self, False)
        if self._kobo:
            self._kobo.regions([])
        self._sessions.clear()
        for refresh in self._windows.values():
            refresh.close()
        self._windows.clear()
