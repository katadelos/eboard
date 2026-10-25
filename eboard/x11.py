"""Window-scoped Kindle refresh through Awesome's lab126_flash API."""

import ctypes
import os
import struct

from PyQt5 import sip
from PyQt5.QtCore import QObject, QRect, QSocketNotifier, QTimer
from PyQt5.QtGui import QRegion


class _XRectangle(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_short),
        ("y", ctypes.c_short),
        ("width", ctypes.c_ushort),
        ("height", ctypes.c_ushort),
    ]


class _DamageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("drawable", ctypes.c_ulong),
        ("damage", ctypes.c_ulong),
        ("level", ctypes.c_int),
        ("more", ctypes.c_int),
        ("timestamp", ctypes.c_ulong),
        ("area", _XRectangle),
        ("geometry", _XRectangle),
    ]


class _MessageData(ctypes.Union):
    _fields_ = [("bytes", ctypes.c_ubyte * 20), ("longs", ctypes.c_long * 5)]


class _ClientMessage(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", _MessageData),
    ]


class _XEvent(ctypes.Union):
    # Xlib's public event union is 24 native longs on both ARM ABIs.
    _fields_ = [
        ("type", ctypes.c_int),
        ("damage", _DamageEvent),
        ("message", _ClientMessage),
        ("padding", ctypes.c_long * 24),
    ]


class WindowGrayscaleRefresh(QObject):
    """Use Awesome's native typing policy and settle damage outside that area.

    Awesome owns the display policy. Its lab126_flash message accepts a
    client-relative rectangle and refuses obscured areas. Its public fidelity
    map includes GC=6, FAST_FULL=1 and SLOW_FULL=9 (lab126_ligl.lua's s_fid_map).
    Explicit scene transitions request flashing cleanup after fresh damage.
    DM:KB sets the native fast
    keyboard policy over keys only; extra A2/DU requests would duplicate its
    automatic updates. XDamage orders feedback after the client's drawing,
    but does not acknowledge physical panel completion.

    Keep this object alive with the QQuickWindow and close it before deleting
    that window. The private connection owns its own DAMAGE object, separate
    from Awesome's subscription. Closing it releases all server resources.
    """

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self._closed = False
        self._display = None
        self._notifier = None
        self._pending = QRegion()
        self._cleanup_fidelity = 0
        self._cleanup_ready = False
        self._typing = False
        self._typing_rectangle = QRect()
        self._typing_region = QRegion()
        self._typing_setup = QRegion()
        self._saved_mode = None
        self._mode_title = None
        self._geometry = QRect()
        self._keys = []
        self._fields = []
        self._feedback = set()
        self._submitted = {}
        self._generation = 0
        self._drain_timer = QTimer(self)
        self._drain_timer.setSingleShot(True)
        self._drain_timer.timeout.connect(self._drain)
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(120)
        self._idle.timeout.connect(self._refresh)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.setInterval(500)
        self._deadline.timeout.connect(self._refresh)
        self._x11 = ctypes.CDLL("libX11.so.6")
        self._extension = ctypes.CDLL("libXdamage.so.1")
        self._configure_abi()
        try:
            self._display = self._x11.XOpenDisplay(
                os.environ.get("DISPLAY", ":0").encode()
            )
            if not self._display:
                raise RuntimeError(
                    "Cannot connect to the Kindle X display for grayscale refresh"
                )
            event_base, error_base = ctypes.c_int(), ctypes.c_int()
            if not self._extension.XDamageQueryExtension(
                self._display, ctypes.byref(event_base), ctypes.byref(error_base)
            ):
                raise RuntimeError("The Kindle X display does not support DAMAGE")
            self._event_type = event_base.value  # XDamageNotify = 0
            self._window_id = int(window.winId())
            self._root = self._x11.XDefaultRootWindow(self._display)
            self._atom = self._x11.XInternAtom(self._display, b"lab126_flash", False)
            # RawRectangles reports only each drawing operation's actual area,
            # not the bounding box of all damage accumulated on the server.
            self._damage = self._extension.XDamageCreate(
                self._display, self._window_id, 0
            )
            self._notifier = QSocketNotifier(
                self._x11.XConnectionNumber(self._display), QSocketNotifier.Read, self
            )
            self._notifier.activated.connect(self._schedule_drain)
            self._x11.XFlush(self._display)
            window.activeChanged.connect(self._visibility_changed)
            window.visibleChanged.connect(self._visibility_changed)
            window.destroyed.connect(self.close)
            self._schedule_drain()
        except Exception:
            self.close()
            raise

    def set_typing_regions(self, keys, fields=()):
        keys = list(keys)
        fields = list(fields)
        geometry = self._window_rectangle()
        if (
            keys == self._keys
            and fields == self._fields
            and geometry == self._geometry
            and self.window.title() == self._mode_title
        ):
            return
        self._keys, self._fields, self._geometry = keys, fields, geometry
        typing = bool(keys)
        rectangle = QRect()
        if typing:
            for area in keys:
                rectangle = rectangle.united(area)
            rectangle = rectangle.intersected(geometry)
        # KB is a window-manager waveform policy for key feedback. Including
        # the editor makes every key press affect its whole fast-mode area.
        self._typing_rectangle = rectangle
        region = QRegion(rectangle)
        if typing:
            for field in fields:
                region += field.intersected(geometry)
        region_changed = region != self._typing_region
        if region_changed:
            added = region.subtracted(self._typing_region)
            self._pending += self._typing_region.subtracted(region)
            self._pending += added
            self._typing_setup = (self._typing_setup + added).intersected(region)
            self._typing_region = region
        self._set_typing_mode(rectangle)
        typing_changed = typing != self._typing
        self._typing = typing
        self._idle.setInterval(
            700
            if typing and self._typing_setup.isEmpty() and not self._cleanup_fidelity
            else 120
        )
        if typing_changed or region_changed:
            if not self._cleanup_ready:
                self._deadline.stop()
            if not self._pending.isEmpty():
                self._idle.start()
        if not typing:
            self._feedback.clear()
            self._submitted.clear()

    def _window_rectangle(self):
        return QRect(
            0, 0, min(65535, self.window.width()), min(65535, self.window.height())
        )

    def _set_typing_mode(self, rectangle):
        # Window-scoped policy follows focus and is reapplied by Awesome after
        # suspend. Preserve the app's other title flags and its previous mode.
        if sip.isdeleted(self.window):
            return
        title = self.window.title()
        names = {"DM", "DMINSETLEFT", "DMINSETTOP", "DMINSETRIGHT", "DMINSETBOTTOM"}
        parts = title.split("_")
        mode = [part for part in parts if part.split(":", 1)[0] in names]
        parts = [part for part in parts if part.split(":", 1)[0] not in names]
        if rectangle.isEmpty():
            if self._saved_mode is None:
                self._mode_title = title
                return
            parts.extend(self._saved_mode)
            self._saved_mode = None
        else:
            if self._saved_mode is None:
                self._saved_mode = mode
            parts.extend(
                (
                    "DM:KB",
                    f"DMINSETLEFT:{rectangle.x()}",
                    f"DMINSETTOP:{rectangle.y()}",
                    f"DMINSETRIGHT:{self.window.width() - rectangle.x() - rectangle.width()}",
                    f"DMINSETBOTTOM:{self.window.height() - rectangle.y() - rectangle.height()}",
                )
            )
        updated = "_".join(parts)
        self._mode_title = updated
        if updated != title:
            self.window.setTitle(updated)

    def expect_key(self, rectangle):
        self._feedback.add(rectangle.getRect())

    def frame(self):
        return self._generation

    def key_ready(self, rectangle, frame):
        return self._submitted.get(rectangle.getRect(), 0) > frame

    def _configure_abi(self):
        pointer, xid = ctypes.c_void_p, ctypes.c_ulong
        declarations = {
            "XOpenDisplay": ([ctypes.c_char_p], pointer),
            "XCloseDisplay": ([pointer], ctypes.c_int),
            "XDefaultRootWindow": ([pointer], xid),
            "XConnectionNumber": ([pointer], ctypes.c_int),
            "XInternAtom": ([pointer, ctypes.c_char_p, ctypes.c_int], xid),
            "XPending": ([pointer], ctypes.c_int),
            "XNextEvent": ([pointer, ctypes.POINTER(_XEvent)], ctypes.c_int),
            "XFlush": ([pointer], ctypes.c_int),
            "XSync": ([pointer, ctypes.c_int], ctypes.c_int),
            "XSendEvent": (
                [pointer, xid, ctypes.c_int, ctypes.c_long, ctypes.POINTER(_XEvent)],
                ctypes.c_int,
            ),
        }
        for name, (arguments, result) in declarations.items():
            function = getattr(self._x11, name)
            function.argtypes, function.restype = arguments, result
        self._extension.XDamageQueryExtension.argtypes = [
            pointer,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        self._extension.XDamageQueryExtension.restype = ctypes.c_int
        self._extension.XDamageCreate.argtypes = [pointer, xid, ctypes.c_int]
        self._extension.XDamageCreate.restype = xid
        self._extension.XDamageSubtract.argtypes = [pointer, xid, xid, xid]
        self._extension.XDamageSubtract.restype = None

    def _eligible(self):
        return (
            not self._closed
            and self.window.isVisible()
            and self.window.isActive()
            and self.window.isExposed()
        )

    def _visibility_changed(self):
        if not self._eligible():
            self._clear_pending()

    def _clear_pending(self):
        self._pending = QRegion()
        self._cleanup_fidelity = 0
        self._cleanup_ready = False
        self._feedback.clear()
        self._idle.stop()
        self._deadline.stop()

    def _schedule_drain(self, *_):
        if not self._closed:
            self._notifier.setEnabled(False)
            if not self._drain_timer.isActive():
                self._drain_timer.start(0)

    def _drain(self, *_, limit=64):
        if self._closed:
            return
        self._drain_timer.stop()
        self._notifier.setEnabled(False)
        event = _XEvent()
        damaged = False
        current = QRegion()
        # Bound a batch so sustained rendering cannot monopolize Qt's event loop.
        for _ in range(limit):
            if not self._x11.XPending(self._display):
                break
            self._x11.XNextEvent(self._display, ctypes.byref(event))
            if event.type != self._event_type or event.damage.damage != self._damage:
                continue
            damaged = True
            if not self._eligible():
                continue
            area, geometry = event.damage.area, event.damage.geometry
            left, top = max(0, area.x), max(0, area.y)
            right = min(geometry.width, area.x + area.width, 65535)
            bottom = min(geometry.height, area.y + area.height, 65535)
            if right <= left or bottom <= top:
                continue
            rectangle = QRect(left, top, right - left, bottom - top)
            current += rectangle
        if not current.isEmpty():
            self._pending += current
            if self._cleanup_fidelity:
                self._cleanup_ready = True
                self._idle.setInterval(120)
            if (
                self._cleanup_ready or not self._typing or not self._typing_setup.isEmpty()
            ) and not self._deadline.isActive():
                self._deadline.start()
            self._idle.start()
        if self._typing and not current.isEmpty():
            self._generation += 1
            for coordinates in tuple(self._feedback):
                rectangle = QRect(*coordinates)
                if current.intersects(rectangle):
                    self._submitted[coordinates] = self._generation
                    self._feedback.discard(coordinates)
        if damaged:
            self._extension.XDamageSubtract(self._display, self._damage, 0, 0)
            self._x11.XFlush(self._display)
        if self._x11.XPending(self._display):
            self._schedule_drain()
        else:
            self._notifier.setEnabled(True)

    def flush_pending(self):
        """Settle the presented splash before startup work occupies the GUI thread."""
        if not self._typing:
            self._refresh()

    def request_cleanup(self, full: bool = True):
        """Clean the whole client after the next drawing settles.

        Call before the transition renders. SLOW_FULL (9) takes precedence over
        FAST_FULL (1) when transitions overlap. Existing damage cannot fulfill
        the request; an inactive window drops it instead of flashing on return.
        """
        if not self._eligible():
            self._clear_pending()
            return
        # Finish delivery of previous drawing before arming. QML transitions
        # have changed the scene, but Qt has not rendered their next frame yet.
        self._x11.XSync(self._display, False)
        self._drain(limit=self._x11.XPending(self._display))
        # FULL (7) selects GC16_FAST on older Kindles. Thin gray outlines need
        # the full-length GC16 waveform, selected explicitly by SLOW_FULL (9).
        self._cleanup_fidelity = max(self._cleanup_fidelity, 9 if full else 1)
        self._cleanup_ready = False
        self._idle.stop()
        self._deadline.stop()

    def _refresh(self):
        if self._closed:
            return
        # Include any already-arrived damage before choosing the settle area.
        self._drain()
        if not self._eligible():
            self._clear_pending()
            return
        if self._cleanup_fidelity and not self._cleanup_ready:
            self._idle.stop()
            self._deadline.stop()
            return
        # A layout change can leave dozens of narrow damage strips. Sending
        # each separately queues slow panel updates behind the new keyboard.
        # Coalesce first, then exclude typing areas so key feedback stays local.
        region = QRegion(self._pending.boundingRect())
        self._pending = QRegion()
        self._idle.stop()
        self._deadline.stop()
        fidelity = self._cleanup_fidelity or 6
        if self._cleanup_fidelity:
            region = QRegion(self._window_rectangle())
            self._cleanup_fidelity = 0
            self._cleanup_ready = False
        # Newly exposed keys and fields need one settle pass to replace the
        # previous page. Afterwards keep them out of grayscale refreshes so
        # typing retains its fast, local feedback.
        if self._typing and fidelity == 6:
            region -= self._typing_region.subtracted(self._typing_setup)
        self._typing_setup = QRegion()
        self._idle.setInterval(700 if self._typing else 120)
        for rectangle in region.rects():
            self._send(rectangle, fidelity)
        self._x11.XFlush(self._display)

    def _send(self, rectangle, fidelity):
        if not self._eligible():
            return False
        rectangle = rectangle.intersected(self._window_rectangle())
        if rectangle.isEmpty():
            return False
        left, top, width, height = rectangle.getRect()
        event = _XEvent()
        event.message.type = 33  # ClientMessage
        event.message.display = self._display
        event.message.window = self._window_id
        event.message.message_type = self._atom
        event.message.format = 8
        payload = struct.pack("<HHHHB", left, top, width, height, fidelity)
        event.message.data.bytes[: len(payload)] = payload
        # Route to the window manager, retaining this application's client ID.
        # This refreshes EPDC output only; it does not draw into X and therefore
        # cannot generate another DAMAGE event and form a refresh loop.
        sent = self._x11.XSendEvent(
            self._display, self._root, False, (1 << 19) | (1 << 20), ctypes.byref(event)
        )
        return bool(sent)

    def close(self, *_):
        if self._closed:
            return
        self._set_typing_mode(QRect())
        self._closed = True
        self._drain_timer.stop()
        self._clear_pending()
        if self._notifier is not None:
            self._notifier.setEnabled(False)
        if self._display:
            # The connection also owns the DAMAGE object. Closing it releases
            # that resource even if the window has already been destroyed.
            self._x11.XCloseDisplay(self._display)
            self._display = None
