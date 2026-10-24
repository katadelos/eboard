import QtQuick 2.15
import QtQuick.Shapes 1.15
import EBoard 1.0

Item {
    id: key
    property var keyboard
    readonly property bool highlighted: feedback.highlighted
    readonly property bool monochrome: keyboard && keyboard.display && keyboard.display.monochromeKeys
    readonly property bool inverted: highlighted
    function pulse() { feedback.pulse() }
    function beginTouch() {
        feedback.press()
        if (!releaseAction) activated()
        if (action === "delete") repeatDelay.start()
    }
    function endTouch(activateOnRelease) {
        repeatDelay.stop(); repeatDelete.stop()
        feedback.release()
        if (activateOnRelease && releaseAction) activated()
    }
    KeyFeedback { id: feedback; anchors.fill: parent; keyboard: key.keyboard }
    property var definition
    property string label
    property color paper: "white"
    property color ink: "black"
    property string fontFamily: "sans-serif"
    property real textSize: 22
    property int fontWeight: Font.Normal
    property real iconSize: 24
    property color borderColor: ink
    property real borderWidth: 1
    property real radius: 0
    property bool engaged: false
    property bool selected: false
    readonly property string action: String(definition.action || "")
    readonly property bool iconKey: action === "shift" || action === "delete"
    readonly property bool releaseAction: action !== "" && action !== "space" && action !== "delete"
    signal activated()
    objectName: "keyboardKey_" + (definition.value || action)
    Accessible.role: Accessible.Button
    Accessible.name: action === "delete" ? "Backspace" : label
    Accessible.onPressAction: { key.pulse(); key.activated() }

    // Synchronous scene-graph primitives avoid Canvas.requestPaint arriving
    // a frame later than the label and losing short inversions.
    Rectangle {
        anchors.fill: parent
        color: key.inverted ? key.ink : key.paper
        border.color: key.selected ? key.ink : key.borderColor
        border.width: key.selected ? Math.max(2, key.borderWidth) : key.borderWidth
        radius: key.radius
        antialiasing: !key.monochrome
    }
    Text {
        visible: key.monochrome || !key.iconKey
        anchors.centerIn: parent
        width: parent.width - 6
        text: key.monochrome && key.iconKey ? (key.action === "shift" ? "⇧" : "⌫") : key.label
        color: key.inverted ? key.paper : key.ink
        font.family: key.monochrome && key.iconKey ? "DejaVu Sans" : key.fontFamily
        font.pixelSize: key.monochrome && key.iconKey ? key.iconSize : key.textSize
        font.weight: key.fontWeight
        renderType: key.monochrome ? Text.NativeRendering : Text.QtRendering
        antialiasing: !key.monochrome
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }
    Shape {
        visible: !key.monochrome && key.iconKey
        anchors.centerIn: parent
        width: 24; height: 24; scale: key.iconSize / 24
        ShapePath {
            strokeColor: key.inverted ? key.paper : key.ink
            strokeWidth: 1.65; fillColor: "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            PathSvg {
                path: key.action === "shift"
                      ? "M12,3 L3,12 L8,12 L8,21 L16,21 L16,12 L21,12 Z"
                      : "M8,5 L22,5 L22,19 L8,19 L1,12 Z M12,9 L18,15 M18,9 L12,15"
            }
        }
    }
    Rectangle {
        visible: key.engaged
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 5
        width: 12; height: 2
        color: key.inverted ? key.paper : key.ink
    }
    Timer { id: repeatDelay; interval: 450; onTriggered: repeatDelete.start() }
    Timer { id: repeatDelete; interval: 90; repeat: true; onTriggered: key.activated() }
}
