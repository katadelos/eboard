# eboard

eboard is an on-screen Qt Quick keyboard for Kindle and Kobo applications.
It provides text editing, touch assistance, configurable styling, and e-paper
key feedback. Desktop previews are also supported.

Requires Python 3.9+ and PyQt5 5.15.6 or later in the 5.x series.
The package includes the `EBoard 1.0` QML module.

## Install

From a checkout, run on your development computer:

```sh
python3 -m pip install .
```

On a reader using the eink SDK, run `opkg install eboard` in the SDK shell.

## Use in an application

After creating a `QApplication`, register eboard before loading your QML:

```python
import eboard
from PyQt5.QtQml import QQmlApplicationEngine

engine = QQmlApplicationEngine()
display = eboard.install(engine)
engine.load("Main.qml")
display.attach(engine.rootObjects()[0])
```

The default is a desktop preview. On a reader, pass `device=True` and
`family="kindle"` or `family="kobo"` to `install()`.
Call `display.close()` before destroying or replacing the engine;
application shutdown also closes it.

In a QML item containing a `TextInput` or `TextEdit` named `searchField`:

```qml
import QtQuick 2.15
import EBoard 1.0

Keyboard {
    width: parent.width
    height: 288
    target: searchField
    submitLabel: "Done"
    onSubmitRequested: visible = false
}
```

Set `paper`, `ink`, `fontFamily`, and the key styling properties to match your app.
The available properties and signals are in [Keyboard.qml](eboard/qml/EBoard/Keyboard.qml).
Use black and white key colours when `monochromeKeys` is true.

For a custom editor, leave `target` unset and handle `textEntered(text)` and
`backspaceRequested()`. `reset(numeric)` resets the layout; `handleAction(action)`
accepts `left`, `right`, `up`, `down`, and `select` for physical navigation.
Set `touchAssistance: false` to use literal key hitboxes.

## License

[MIT](LICENSE).
