// Keyboard layout and styling adapted from ktrmnl2.
import QtQuick 2.15
import EBoard 1.0

Item {
    id: root
    objectName: "onScreenKeyboard"
    KeyboardSession {
        id: session
        anchors.fill: parent
        display: eboardDisplay
        target: root.target
    }
    property color paper: "white"
    property color ink: "black"
    property string fontFamily: "sans-serif"
    property real uiScale: 1
    property real bodySize: 22
    property real controlSize: 18
    property real headingSize: 28
    property int fontWeight: Font.Normal
    property real iconSize: 24
    property color trayColor: paper
    property color trayBorderColor: ink
    property real trayBorderWidth: 1
    property real trayRadius: 0
    property int trayPadding: Math.max(7, Math.round(9 * uiScale))
    property int keyGap: Math.max(4, Math.round(6 * uiScale))
    property color keyColor: paper
    property color keyTextColor: ink
    property color actionKeyColor: keyColor
    property color actionKeyTextColor: keyTextColor
    property color submitKeyColor: actionKeyColor
    property color submitKeyTextColor: actionKeyTextColor
    property color keyBorderColor: ink
    property real keyBorderWidth: 1
    property real keyRadius: 0
    readonly property bool monochromeKeys: session.display && session.display.monochromeKeys
    property var target: null
    property bool touchAssistance: true
    property string touchLanguage: "en"
    signal edited()
    implicitHeight: 258

    function insert(value) {
        if (!target || !target.enabled || target.readOnly) return
        var position = target.cursorPosition
        if (target.selectionStart !== target.selectionEnd) {
            position = target.selectionStart
            target.remove(target.selectionStart, target.selectionEnd)
        }
        target.insert(position, value)
        edited()
    }
    function erase() {
        if (!target || !target.enabled || target.readOnly) return
        if (target.selectionStart !== target.selectionEnd) {
            target.remove(target.selectionStart, target.selectionEnd)
        } else if (target.cursorPosition > 0) {
            // QTextBoundaryFinder handles surrogate pairs and combining marks.
            var position = session.previousGrapheme(target.text, target.cursorPosition)
            target.remove(position, target.cursorPosition)
        }
        edited()
    }
    onTextEntered: insert(text)
    onBackspaceRequested: erase()
    property int currentRow: 0
    property int currentColumn: 0
    property bool selectionActive: false
    property bool shifted: false
    property bool symbols: false
    property bool alternateSymbols: false
    property bool numericMode: false
    property string submitLabel: "Enter"
    signal textEntered(string text)
    signal backspaceRequested()
    signal submitRequested()

    Rectangle {
        anchors.fill: parent
        color: root.trayColor; border.color: root.trayBorderColor
        border.width: root.trayBorderWidth; radius: root.trayRadius
        antialiasing: !root.monochromeKeys
    }

    readonly property var letterRows: [
        [
            {"label": "q", "value": "q"}, {"label": "w", "value": "w"},
            {"label": "e", "value": "e"}, {"label": "r", "value": "r"},
            {"label": "t", "value": "t"}, {"label": "y", "value": "y"},
            {"label": "u", "value": "u"}, {"label": "i", "value": "i"},
            {"label": "o", "value": "o"}, {"label": "p", "value": "p"}
        ],
        [
            {"label": "a", "value": "a"}, {"label": "s", "value": "s"},
            {"label": "d", "value": "d"}, {"label": "f", "value": "f"},
            {"label": "g", "value": "g"}, {"label": "h", "value": "h"},
            {"label": "j", "value": "j"}, {"label": "k", "value": "k"},
            {"label": "l", "value": "l"}
        ],
        [
            {"label": "⇧", "action": "shift", "weight": 1.25},
            {"label": "z", "value": "z"}, {"label": "x", "value": "x"},
            {"label": "c", "value": "c"}, {"label": "v", "value": "v"},
            {"label": "b", "value": "b"}, {"label": "n", "value": "n"},
            {"label": "m", "value": "m"},
            {"label": "⌫", "action": "delete", "weight": 1.25}
        ],
        [
            {"label": "123", "action": "symbols", "weight": 1.35},
            {"label": ",", "value": ","},
            {"label": "space", "action": "space", "weight": 4.4},
            {"label": ".", "value": ".", "weight": 1.2},
            {"label": "↵", "action": "submit", "weight": 1.35}
        ]
    ]
    readonly property var symbolRows: [
        [
            {"label": "1", "value": "1"}, {"label": "2", "value": "2"},
            {"label": "3", "value": "3"}, {"label": "4", "value": "4"},
            {"label": "5", "value": "5"}, {"label": "6", "value": "6"},
            {"label": "7", "value": "7"}, {"label": "8", "value": "8"},
            {"label": "9", "value": "9"}, {"label": "0", "value": "0"}
        ],
        [
            {"label": "-", "value": "-"}, {"label": "/", "value": "/"},
            {"label": ":", "value": ":"}, {"label": ";", "value": ";"},
            {"label": "(", "value": "("}, {"label": ")", "value": ")"},
            {"label": "$", "value": "$"}, {"label": "&", "value": "&"},
            {"label": "@", "value": "@"}
        ],
        [
            {"label": "#+=", "action": "more-symbols", "weight": 1.25},
            {"label": "_", "value": "_"}, {"label": "+", "value": "+"},
            {"label": "=", "value": "="}, {"label": "?", "value": "?"},
            {"label": "!", "value": "!"}, {"label": "'", "value": "'"},
            {"label": "\"", "value": "\""},
            {"label": "⌫", "action": "delete", "weight": 1.25}
        ],
        [
            {"label": "ABC", "action": "letters", "weight": 1.35},
            {"label": ",", "value": ","},
            {"label": "space", "action": "space", "weight": 4.4},
            {"label": ".", "value": ".", "weight": 1.2},
            {"label": "↵", "action": "submit", "weight": 1.35}
        ]
    ]
    readonly property var alternateSymbolRows: [
        symbolRows[0],
        [
            {"label": "[", "value": "["}, {"label": "]", "value": "]"},
            {"label": "{", "value": "{"}, {"label": "}", "value": "}"},
            {"label": "#", "value": "#"}, {"label": "%", "value": "%"},
            {"label": "^", "value": "^"}, {"label": "*", "value": "*"},
            {"label": "+", "value": "+"}, {"label": "=", "value": "="}
        ],
        [
            {"label": "123", "action": "more-symbols", "weight": 1.25},
            {"label": "\\", "value": "\\"}, {"label": "|", "value": "|"},
            {"label": "~", "value": "~"}, {"label": "`", "value": "`"},
            {"label": "<", "value": "<"}, {"label": ">", "value": ">"},
            {"label": ",", "value": ","},
            {"label": "⌫", "action": "delete", "weight": 1.25}
        ],
        symbolRows[3]
    ]
    readonly property var numberRows: [
        [
            {"label": "1", "value": "1"},
            {"label": "2", "value": "2"},
            {"label": "3", "value": "3"}
        ],
        [
            {"label": "4", "value": "4"},
            {"label": "5", "value": "5"},
            {"label": "6", "value": "6"}
        ],
        [
            {"label": "7", "value": "7"},
            {"label": "8", "value": "8"},
            {"label": "9", "value": "9"}
        ],
        [
            {"label": "⌫", "action": "delete"},
            {"label": "0", "value": "0"},
            {"label": "↵", "action": "submit"}
        ]
    ]
    readonly property var displayedRows: numericMode
                                         ? numberRows
                                         : (symbols ? (alternateSymbols ? alternateSymbolRows : symbolRows) : letterRows)
    readonly property int rowCount: displayedRows.length
    readonly property real keyHeight: Math.max(
                                          1,
                                          (height - trayPadding * 2
                                           - keyGap * (rowCount - 1)) / rowCount)

    function reset(useNumbers) {
        cancelTouch()
        session.resetTouchCalibration()
        currentRow = 0
        currentColumn = 0
        selectionActive = false
        shifted = false
        numericMode = Boolean(useNumbers)
        symbols = false
        alternateSymbols = false
    }

    onDisplayedRowsChanged: {
        cancelTouch()
        session.resetTouchCalibration()
    }
    onTargetChanged: cancelTouch()
    onVisibleChanged: if (!visible) cancelTouch()
    onEnabledChanged: if (!enabled) cancelTouch()
    onWidthChanged: session.resetTouchCalibration()
    onHeightChanged: session.resetTouchCalibration()

    function cancelTouch() {
        var key = touch.pressedKey
        touch.pressedKey = null
        if (key) key.endTouch(false)
    }

    function keyCount(row) { return displayedRows[row].length }
    function keyWeight(key) { return Number(key.weight || 1) }
    function rowWeight(row) {
        var total = 0
        for (var index = 0; index < displayedRows[row].length; index++)
            total += keyWeight(displayedRows[row][index])
        return total
    }

    function keyLabel(key) {
        var value = String(key.label || "")
        if (shifted && !symbols && !numericMode
                && key.value && value >= "a" && value <= "z")
            return value.toUpperCase()
        if (key.action === "submit") return submitLabel
        if (key.action === "space") {
            return "space"
        }
        return value
    }

    function moveHorizontal(delta) {
        var count = keyCount(currentRow)
        currentColumn = (currentColumn + delta + count) % count
    }

    function moveVertical(delta) {
        var nextRow = (currentRow + delta + rowCount) % rowCount
        if (nextRow === currentRow) return
        var oldCount = keyCount(currentRow)
        var nextCount = keyCount(nextRow)
        var position = oldCount <= 1 ? 0 : currentColumn / (oldCount - 1)
        currentRow = nextRow
        currentColumn = Math.max(0, Math.min(nextCount - 1, Math.round(position * (nextCount - 1))))
    }

    function activateCurrent() {
        selectionActive = true
        var row = rowRepeater.itemAt(currentRow)
        if (row) {
            var item = row.keys.itemAt(currentColumn)
            if (item) item.pulse()
        }
        activate(displayedRows[currentRow][currentColumn])
    }

    function activate(key) {
        var action = String(key.action || "")
        if (!action) {
            var value = String(key.value || "")
            if (shifted && !symbols && !numericMode
                    && value >= "a" && value <= "z") value = value.toUpperCase()
            textEntered(value)
        } else if (action === "shift") {
            shifted = !shifted
        } else if (action === "symbols") {
            symbols = true
            alternateSymbols = false
            currentRow = 0
            currentColumn = 0
        } else if (action === "more-symbols") {
            alternateSymbols = !alternateSymbols
            currentRow = 0
            currentColumn = 0
        } else if (action === "letters") {
            symbols = false
            currentRow = 0
            currentColumn = 0
        } else if (action === "space") {
            textEntered(" ")
        } else if (action === "delete") {
            backspaceRequested()
        } else if (action === "submit") {
            submitRequested()
        }
    }

    function handleAction(action) {
        selectionActive = true
        if (action === "left") moveHorizontal(-1)
        else if (action === "right") moveHorizontal(1)
        else if (action === "up") moveVertical(-1)
        else if (action === "down") moveVertical(1)
        else if (action === "select") activateCurrent()
        else return false
        return true
    }

    Column {
        id: keyboardRows
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: root.trayPadding
        anchors.bottomMargin: root.trayPadding
        width: root.numericMode
               ? Math.min(parent.width - root.trayPadding * 2,
                          Math.round(430 * root.uiScale))
               : parent.width - root.trayPadding * 2
        spacing: root.keyGap

        Repeater {
            id: rowRepeater
            model: root.rowCount

            delegate: Row {
                id: keyRow
                property int rowIndex: index
                property alias keys: keyRepeater
                width: keyboardRows.width
                height: root.keyHeight
                spacing: root.keyGap

                Repeater {
                    id: keyRepeater
                    model: root.displayedRows[keyRow.rowIndex]
                    delegate: Key {
                        keyboard: session
                        definition: modelData
                        label: root.keyLabel(modelData)
                        paper: action === "submit" ? root.submitKeyColor
                               : action && action !== "space" ? root.actionKeyColor : root.keyColor
                        ink: action === "submit" ? root.submitKeyTextColor
                             : action && action !== "space" ? root.actionKeyTextColor : root.keyTextColor
                        borderColor: root.keyBorderColor; borderWidth: root.keyBorderWidth
                        radius: root.keyRadius; iconSize: root.iconSize
                        fontFamily: root.fontFamily; fontWeight: root.fontWeight
                        selected: root.selectionActive && root.currentRow === keyRow.rowIndex
                                  && root.currentColumn === index
                        engaged: action === "shift" && root.shifted
                        width: (keyRow.width - keyRow.spacing * (root.keyCount(keyRow.rowIndex) - 1))
                               * root.keyWeight(modelData) / root.rowWeight(keyRow.rowIndex)
                        height: keyRow.height
                        textSize: action === "space" || action === "submit" ? root.controlSize
                                  : root.numericMode ? root.headingSize : root.bodySize
                        onActivated: {
                            root.selectionActive = false
                            root.currentRow = keyRow.rowIndex
                            root.currentColumn = index
                            root.activate(modelData)
                        }
                    }
                }
            }
        }
    }

    MouseArea {
        id: touch
        anchors.fill: parent
        preventStealing: true
        property var pressedKey: null
        onPressed: {
            var items = []
            var geometry = []
            for (var rowIndex = 0; rowIndex < root.rowCount; rowIndex++) {
                var row = rowRepeater.itemAt(rowIndex)
                if (!row) continue
                for (var column = 0; column < row.keys.count; column++) {
                    var key = row.keys.itemAt(column)
                    if (!key || !key.visible || key.width <= 0 || key.height <= 0) continue
                    var point = key.mapToItem(root, 0, 0)
                    items.push(key)
                    geometry.push({"x": point.x, "y": point.y,
                                   "width": key.width, "height": key.height,
                                   "value": String(key.definition.value || ""),
                                   "action": key.action})
                }
            }
            var selected = session.resolveTouch(mouse.x, mouse.y, geometry,
                                                root.touchAssistance, root.touchLanguage)
            pressedKey = selected >= 0 ? items[selected] : null
            if (pressedKey) pressedKey.beginTouch()
        }
        onReleased: {
            var key = pressedKey
            pressedKey = null
            if (key) {
                var point = key.mapFromItem(root, mouse.x, mouse.y)
                key.endTouch(point.x >= 0 && point.x < key.width
                             && point.y >= 0 && point.y < key.height)
            }
        }
        onCanceled: root.cancelTouch()
    }
}
