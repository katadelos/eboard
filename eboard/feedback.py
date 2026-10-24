"""Keep each key visible through rendering and native submission before releasing it."""

from PyQt5 import sip
from PyQt5.QtCore import (
    QElapsedTimer,
    QObject,
    QRectF,
    Qt,
    QTextBoundaryFinder,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtQuick import QQuickItem

from .touch import TouchResolver


class KeyboardSession(QQuickItem):
    displayChanged = pyqtSignal()
    targetChanged = pyqtSignal()

    @pyqtSlot(str, int, result=int)
    def previousGrapheme(self, text, position):
        finder = QTextBoundaryFinder(QTextBoundaryFinder.Grapheme, text)
        finder.setPosition(position)
        return max(0, finder.toPreviousBoundary())

    def __init__(self, parent=None):
        super().__init__(parent)
        self._touch = TouchResolver()
        self._display = None
        self._target = None
        self._keys = set()
        self._window = None
        self._poll = QTimer(self)
        self._poll.setInterval(16)
        self._poll.timeout.connect(self._check_frames)
        self._layout = QTimer(self)
        self._layout.setSingleShot(True)
        self._layout.timeout.connect(self._sync)
        self.destroyed.connect(lambda: self._destroyed())
        self.windowChanged.connect(self._window_changed)
        for signal in (
            self.visibleChanged,
            self.enabledChanged,
            self.xChanged,
            self.yChanged,
            self.widthChanged,
            self.heightChanged,
        ):
            signal.connect(self.schedule_layout)

    @pyqtProperty(QObject, notify=displayChanged)
    def display(self):
        return self._display

    @display.setter
    def display(self, value):
        if self._display:
            self._display.update(self, False)
        self._display = value
        self.displayChanged.emit()
        self.schedule_layout()

    def schedule_layout(self, *_):
        if not sip.isdeleted(self._layout):
            self._layout.start(0)

    @pyqtProperty(QObject, notify=targetChanged)
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._touch.reset()
        self._target = value
        self.targetChanged.emit()
        self.schedule_layout()

    @pyqtSlot()
    def resetTouchCalibration(self):
        self._touch.reset()

    @pyqtSlot(float, float, "QVariantList", bool, str, result=int)
    def resolveTouch(self, x, y, keys, assisted, language):
        target = self._target
        text, cursor = "", 0
        adapt, predictive = True, False
        if target is not None and not sip.isdeleted(target):
            hints = int(target.property("inputMethodHints") or 0)
            literal_hints = int(Qt.ImhHiddenText | Qt.ImhSensitiveData
                                | Qt.ImhDigitsOnly | Qt.ImhFormattedNumbersOnly
                                | Qt.ImhDialableCharactersOnly | Qt.ImhUrlCharactersOnly
                                | Qt.ImhEmailCharactersOnly)
            adapt = not (hints & literal_hints or target.property("echoMode"))
            predictive = (adapt and language.lower() == "en"
                          and not hints & int(Qt.ImhNoPredictiveText)
                          and target.property("selectionStart") == target.property("selectionEnd"))
            if predictive:
                text = str(target.property("text") or "")
                cursor = int(target.property("cursorPosition") or 0)
        return self._touch.resolve(keys, x, y, assisted=assisted, adapt=adapt,
                                   text=text, cursor=cursor, predictive=predictive)

    def _window_changed(self, window):
        if self._window and not sip.isdeleted(self._window):
            for signal, slot in (
                (self._window.frameSwapped, self._frame),
                (self._window.visibleChanged, self.schedule_layout),
                (self._window.activeChanged, self.schedule_layout),
            ):
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass  # Qt has already disconnected a window being destroyed.
        self._window = window
        if window:
            window.frameSwapped.connect(self._frame, Qt.QueuedConnection)
            window.visibleChanged.connect(self.schedule_layout)
            window.activeChanged.connect(self.schedule_layout)
        self.schedule_layout()

    def _sync(self):
        self._layout.stop()
        active = bool(
            self._window
            and not sip.isdeleted(self._window)
            and self._window.isVisible()
            and self.isVisible()
            and self.isEnabled()
            and self._window.isActive()
        )
        if self._display:
            self._display.update(self, active)
        if not active:
            self._poll.stop()
            for key in tuple(self._keys):
                if not sip.isdeleted(key):
                    key.reset()

    def _destroyed(self):
        if self._display and not sip.isdeleted(self._display):
            self._display.update(self, False)

    def rectangles(self):
        return [
            key.scene_rectangle()
            for key in self._keys
            if not sip.isdeleted(key) and key.isVisible() and key.width() > 0
        ]

    def field_rectangle(self):
        target = self._target
        if isinstance(target, QQuickItem) and not sip.isdeleted(target):
            rectangle = target.mapRectToScene(
                QRectF(0, 0, target.width(), target.height())
            )
            parent = target.parentItem()
            while parent:
                if parent.clip():
                    rectangle = rectangle.intersected(
                        parent.mapRectToScene(
                            QRectF(0, 0, parent.width(), parent.height())
                        )
                    )
                parent = parent.parentItem()
            return rectangle.toAlignedRect()
        return None

    @pyqtSlot()
    def updateGeometry(self):
        self.schedule_layout()

    def _frame(self):
        self._sync()
        for key in tuple(self._keys):
            if not sip.isdeleted(key) and key._awaiting:
                key._rendered = True
        # QFbScreen consumes the backing-store flush on the GUI event loop.
        # Native readiness below also requires a newer composed frame and a
        # matching submitted shadow; frameSwapped alone is not an e-paper fence.
        self._check_frames()

    def _check_frames(self):
        pending = False
        for key in tuple(self._keys):
            if sip.isdeleted(key) or not key._awaiting:
                continue
            if key._rendered and self._display and self._display.ready(key, key._frame):
                key.presented()
            else:
                pending = True
        if pending:
            self._poll.start()
        else:
            self._poll.stop()


class KeyFeedback(QQuickItem):
    keyboardChanged = pyqtSignal()
    highlightedChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._keyboard = None
        self._highlighted = False
        self._down = False
        self._awaiting = False
        self._rendered = False
        self._frame = 0
        self._hold_age = QElapsedTimer()
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self.reset)
        for signal in (
            self.xChanged,
            self.yChanged,
            self.widthChanged,
            self.heightChanged,
            self.visibleChanged,
        ):
            signal.connect(self._geometry_changed)

    @pyqtProperty(QObject, notify=keyboardChanged)
    def keyboard(self):
        return self._keyboard

    @keyboard.setter
    def keyboard(self, value):
        if self._keyboard:
            self._keyboard._keys.discard(self)
        self._keyboard = value
        if value:
            value._keys.add(self)
            # Capture the session, not the deleted key's methods.
            self.destroyed.connect(lambda: self._remove_from(value))
            value.schedule_layout()
        self.keyboardChanged.emit()

    def _remove_from(self, session):
        session._keys.discard(self)
        if not sip.isdeleted(session):
            session.schedule_layout()

    @pyqtProperty(bool, notify=highlightedChanged)
    def highlighted(self):
        return self._highlighted

    def scene_rectangle(self):
        return self.mapRectToScene(
            QRectF(0, 0, self.width(), self.height())
        ).toAlignedRect()

    def _geometry_changed(self):
        if self._keyboard:
            self._keyboard.schedule_layout()

    @pyqtSlot()
    def press(self):
        # Layout/focus signals already schedule geometry updates. Do not map
        # every key through the scene again before accepting each character.
        if self._keyboard._layout.isActive():
            self._keyboard._sync()
        self._down = True
        self._hold.stop()
        self._hold_age.start()
        if not self._highlighted:
            self._frame = self._keyboard.display.frame(self)
            self._awaiting = True
            self._rendered = False
            self._highlighted = True
            self._keyboard.display.feedback_changed(self)
            self.highlightedChanged.emit()

    @pyqtSlot()
    def release(self):
        self._down = False
        if self._highlighted and not self._awaiting:
            self._schedule_release()

    @pyqtSlot()
    def pulse(self):
        self.press()
        self.release()

    def presented(self):
        self._awaiting = False
        self._hold_age.start()
        if not self._down:
            self._schedule_release()

    def _schedule_release(self):
        # Count the hold from submission (or a repeated tap), not finger-up.
        # A long press can return to white as soon as the finger is released.
        minimum = self._keyboard.display.minimum_feedback_ms
        self._hold.start(max(0, minimum - self._hold_age.elapsed()))

    @pyqtSlot()
    def reset(self):
        self._hold.stop()
        self._down = False
        self._awaiting = False
        if self._highlighted:
            self._highlighted = False
            if self._keyboard and self._keyboard.display:
                self._keyboard.display.feedback_changed(self)
            self.highlightedChanged.emit()
