import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Effects
import QtQuick.Controls as QQC2
import Qt5Compat.GraphicalEffects as GE
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support

// Pomodoro ring + a tiny to-do list on a glass card.
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    readonly property color sky: "#86BEFF"
    readonly property color lilac: "#C3A6FF"
    readonly property color sakura: "#FFA3D2"

    // ── timer state ──
    property bool onBreak: false
    property bool running: false
    readonly property int doneToday: Plasmoid.configuration.DoneDay === new Date().toDateString() ? (Plasmoid.configuration.DoneToday || 0) : 0
    readonly property int total: (onBreak ? (Plasmoid.configuration.BreakMinutes || 5) : (Plasmoid.configuration.FocusMinutes || 25)) * 60000
    property real remaining: total
    property real endAt: 0
    onTotalChanged: if (!running) remaining = total

    function start() { endAt = Date.now() + remaining; running = true }
    function pause() { remaining = Math.max(0, endAt - Date.now()); running = false }
    function reset() { running = false; remaining = total }
    function finish() {
        running = false
        if (!onBreak) {
            const today = new Date().toDateString()
            if (Plasmoid.configuration.DoneDay !== today) { Plasmoid.configuration.DoneDay = today; Plasmoid.configuration.DoneToday = 0 }
            Plasmoid.configuration.DoneToday = (Plasmoid.configuration.DoneToday || 0) + 1
        }
        notify(onBreak ? "Break over" : "Focus session done 🌸",
               onBreak ? "Back to it — you've got this." : "Take a " + Plasmoid.configuration.BreakMinutes + " minute break.")
        onBreak = !onBreak
        remaining = total
        pulse.restart()
    }
    Timer {
        interval: 250; repeat: true; running: root.running
        onTriggered: { root.remaining = Math.max(0, root.endAt - Date.now()); if (root.remaining <= 0) root.finish() }
    }

    P5Support.DataSource {
        id: exec
        engine: "executable"
        onNewData: (source) => disconnectSource(source)
    }
    function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
    function notify(title, body) {
        exec.connectSource("notify-send -a 'Focus Garden' -i chronometer " + shq(title) + " " + shq(body)
                           + "; paplay /usr/share/sounds/freedesktop/stereo/complete.oga")
    }

    // ── tasks (stored as JSON in the widget config) ──
    property var tasks: []
    Component.onCompleted: { try { tasks = JSON.parse(Plasmoid.configuration.Tasks) } catch (e) { tasks = [] } }
    function save(t) { tasks = t; Plasmoid.configuration.Tasks = JSON.stringify(t) }
    function addTask(text) { if (text.trim()) save(tasks.concat([{ t: text.trim(), d: false }])) }
    function toggleTask(i) { const t = tasks.slice(); t[i] = { t: t[i].t, d: !t[i].d }; save(t) }
    function removeTask(i) { const t = tasks.slice(); t.splice(i, 1); save(t) }

    fullRepresentation: Item {
        Layout.preferredWidth: 340
        Layout.preferredHeight: 470
        Layout.minimumWidth: 300
        Layout.minimumHeight: 420

        Item {
            id: card
            anchors.fill: parent
            anchors.margins: 6
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#80000000"; shadowBlur: 0.9; blurMax: 32; shadowVerticalOffset: 6; shadowHorizontalOffset: 0 }

            Rectangle {
                anchors.fill: parent; radius: 26
                gradient: Gradient {
                    GradientStop { position: 0; color: "#B02A2150" }
                    GradientStop { position: 1; color: "#B0451F45" }
                }
                border.width: 1; border.color: "#33FFFFFF"
            }
            Rectangle {
                anchors.fill: parent; radius: 26
                gradient: Gradient { GradientStop { position: 0; color: "#1EFFFFFF" } GradientStop { position: 0.35; color: "#00FFFFFF" } }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10

                // header
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.onBreak ? "BREAK" : "FOCUS"
                        font.family: "Poppins"; font.pixelSize: 13; font.letterSpacing: 5; font.weight: Font.Normal
                        color: root.onBreak ? root.sky : root.sakura
                    }
                    Item { Layout.fillWidth: true }
                    Row {   // finished sessions today
                        spacing: 5
                        Repeater {
                            model: Math.max(4, root.doneToday)
                            Rectangle {
                                readonly property bool lit: index < root.doneToday
                                width: 8; height: 8; radius: 4
                                color: lit ? root.sakura : "transparent"
                                border.width: 1; border.color: lit ? root.sakura : "#66FFFFFF"
                            }
                        }
                    }
                }

                // ring
                Item {
                    id: ringBox
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 190; Layout.preferredHeight: 190
                    readonly property real frac: root.total > 0 ? root.remaining / root.total : 0

                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            strokeColor: "#22FFFFFF"; strokeWidth: 8; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                            PathAngleArc { centerX: 95; centerY: 95; radiusX: 85; radiusY: 85; startAngle: 0; sweepAngle: 360 }
                        }
                    }
                    Shape {
                        id: arc
                        anchors.fill: parent
                        visible: false
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            strokeColor: "white"; strokeWidth: 8; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                            PathAngleArc { centerX: 95; centerY: 95; radiusX: 85; radiusY: 85; startAngle: -90; sweepAngle: 360 * ringBox.frac }
                        }
                    }
                    GE.ConicalGradient {
                        id: cone
                        anchors.fill: parent; visible: false
                        angle: 0
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: root.sky }
                            GradientStop { position: 0.5; color: root.lilac }
                            GradientStop { position: 1.0; color: root.sakura }
                        }
                    }
                    GE.OpacityMask {
                        anchors.fill: parent; source: cone; maskSource: arc
                        layer.enabled: true
                        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: root.lilac; shadowBlur: root.running ? 0.8 : 0.4; blurMax: 24; shadowHorizontalOffset: 0; shadowVerticalOffset: 0 }
                    }
                    // pulse when a session ends
                    Rectangle {
                        id: pulseRing
                        anchors.centerIn: parent
                        width: 178; height: 178; radius: width / 2
                        color: "transparent"; border.width: 3; border.color: root.sakura; opacity: 0
                        ParallelAnimation {
                            id: pulse
                            loops: 3
                            NumberAnimation { target: pulseRing; property: "scale"; from: 1; to: 1.25; duration: 900; easing.type: Easing.OutCubic }
                            NumberAnimation { target: pulseRing; property: "opacity"; from: 0.9; to: 0; duration: 900 }
                        }
                    }

                    Column {
                        anchors.centerIn: parent
                        spacing: -6
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            readonly property int s: Math.ceil(root.remaining / 1000)
                            text: Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60)
                            font.family: "Poppins"; font.weight: Font.ExtraLight; font.pixelSize: 46
                            font.features: { "tnum": 1 }
                            color: "white"
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: root.running ? (root.onBreak ? "breathe" : "deep work") : (root.remaining < root.total ? "paused" : "ready")
                            font.family: "Great Vibes"; font.pixelSize: 24
                            color: "#FFE3F1"
                        }
                    }
                }

                // controls
                Row {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 14
                    Repeater {
                        model: [
                            { label: "↺", act: "reset", big: false },
                            { label: root.running ? "❚❚" : "▶", act: "toggle", big: true },
                            { label: "»", act: "skip", big: false }
                        ]
                        Rectangle {
                            width: modelData.big ? 52 : 38; height: width; radius: width / 2
                            anchors.verticalCenter: parent.verticalCenter
                            gradient: Gradient {
                                GradientStop { position: 0; color: modelData.big ? root.sky : (ma.containsMouse ? "#40FFFFFF" : "#1FFFFFFF") }
                                GradientStop { position: 1; color: modelData.big ? root.sakura : (ma.containsMouse ? "#40FFFFFF" : "#1FFFFFFF") }
                            }
                            scale: ma.pressed ? 0.9 : (ma.containsMouse ? 1.06 : 1)
                            Behavior on scale { NumberAnimation { duration: 150 } }
                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                font.pixelSize: modelData.big ? 18 : 18
                                color: modelData.big ? "#2A1B45" : "white"
                            }
                            MouseArea {
                                id: ma
                                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (modelData.act === "toggle") root.running ? root.pause() : root.start()
                                    else if (modelData.act === "reset") root.reset()
                                    else { root.running = false; root.onBreak = !root.onBreak; root.remaining = root.total }
                                }
                            }
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#26FFFFFF"; Layout.topMargin: 4 }

                // tasks
                ListView {
                    id: list
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    model: root.tasks
                    add: Transition { NumberAnimation { properties: "opacity"; from: 0; to: 1; duration: 300 } }
                    delegate: Item {
                        width: list.width; height: 30
                        HoverHandler { id: rowHover }
                        Rectangle {
                            id: check
                            width: 16; height: 16; radius: 8
                            anchors.verticalCenter: parent.verticalCenter
                            color: modelData.d ? root.sakura : "transparent"
                            border.width: 1.5; border.color: modelData.d ? root.sakura : "#99FFFFFF"
                            Behavior on color { ColorAnimation { duration: 250 } }
                            Text { anchors.centerIn: parent; text: "✓"; visible: modelData.d; color: "#2A1B45"; font.pixelSize: 11; font.bold: true }
                            MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor; onClicked: root.toggleTask(index) }
                        }
                        Text {
                            anchors.left: check.right; anchors.leftMargin: 10
                            anchors.right: del.left; anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.t
                            elide: Text.ElideRight
                            font.family: "Poppins"; font.pixelSize: 13; font.weight: Font.Light
                            font.strikeout: modelData.d
                            color: modelData.d ? "#88FFFFFF" : "white"
                        }
                        Text {
                            id: del
                            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            text: "✕"; font.pixelSize: 12; color: "#AAFFFFFF"
                            opacity: rowHover.hovered ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                            MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor; onClicked: root.removeTask(index) }
                        }
                    }
                }

                QQC2.TextField {
                    id: input
                    Layout.fillWidth: true
                    placeholderText: "+  add a task…"
                    placeholderTextColor: "#99FFFFFF"
                    color: "white"
                    font.family: "Poppins"; font.pixelSize: 13
                    background: Rectangle {
                        radius: 14
                        color: input.activeFocus ? "#30FFFFFF" : "#18FFFFFF"
                        border.width: 1; border.color: input.activeFocus ? root.sakura : "#22FFFFFF"
                        Behavior on color { ColorAnimation { duration: 200 } }
                    }
                    leftPadding: 14
                    onAccepted: { root.addTask(text); text = "" }
                }
            }
        }
    }
}
