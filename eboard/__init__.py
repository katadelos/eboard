"""Shared Qt Quick keyboard and display integration."""

from pathlib import Path

from PyQt5.QtQml import qmlRegisterType

from .feedback import KeyboardSession, KeyFeedback
from .display import Display

_registered = False


def install(engine, *, device=False, family=None):
    """Register EBoard before loading QML; attach the returned display to the window."""
    global _registered
    if not _registered:
        qmlRegisterType(KeyboardSession, "EBoard", 1, 0, "KeyboardSession")
        qmlRegisterType(KeyFeedback, "EBoard", 1, 0, "KeyFeedback")
        _registered = True
    display = Display(engine, device=device, family=family)
    engine.rootContext().setContextProperty("eboardDisplay", display)
    engine.addImportPath(str(Path(__file__).parent / "qml"))
    return display
