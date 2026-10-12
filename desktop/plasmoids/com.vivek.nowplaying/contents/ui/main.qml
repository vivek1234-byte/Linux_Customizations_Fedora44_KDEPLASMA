import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Qt5Compat.GraphicalEffects as GE
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris

// Glass "now playing" card. Hidden while nothing is playing or paused.
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    fullRepresentation: Item {
        id: face
        Layout.preferredWidth: 410
        Layout.preferredHeight: 136
        Layout.minimumWidth: 410
        Layout.minimumHeight: 136

        readonly property color sky: "#86BEFF"
        readonly property color sakura: "#FFA3D2"

        Mpris.Mpris2Model { id: mpris }
        readonly property var player: mpris.currentPlayer
        readonly property bool playing: !!player && player.playbackStatus === Mpris.PlaybackStatus.Playing
        readonly property bool shown: !!player && (playing || player.playbackStatus === Mpris.PlaybackStatus.Paused)
        readonly property string art: player ? player.artUrl.toString() : ""
        readonly property real progress: player && player.length > 0 ? Math.min(1, player.position / player.length) : 0

        function fmt(us) {
            const s = Math.max(0, Math.floor(us / 1e6))
            return Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60)
        }
        Timer { interval: 1000; repeat: true; running: face.playing; onTriggered: face.player.updatePosition() }

        Item {
            id: card
            anchors.fill: parent
            anchors.margins: 4
            opacity: face.shown ? 1 : 0
            scale: face.shown ? 1 : 0.92
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: 700; easing.type: Easing.OutBack } }

            // drop shadow
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#90000000"; shadowBlur: 0.9; blurMax: 32; shadowVerticalOffset: 6; shadowHorizontalOffset: 0 }

            // glass body: blurred cover art + tint, clipped to a rounded rect
            Item {
                id: body
                anchors.fill: parent
                visible: false
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: "#3A2D6B" }
                        GradientStop { position: 1; color: "#6B2D5C" }
                    }
                }
                Image {
                    id: bgArt
                    anchors.fill: parent
                    source: face.art
                    fillMode: Image.PreserveAspectCrop
                    visible: false
                }
                MultiEffect {
                    anchors.fill: parent
                    source: bgArt
                    visible: bgArt.status === Image.Ready
                    blurEnabled: true; blur: 1.0; blurMax: 64
                    saturation: 0.25
                }
                Rectangle { anchors.fill: parent; color: "#1E1433"; opacity: 0.55 }
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#22FFFFFF" }
                        GradientStop { position: 0.5; color: "#00FFFFFF" }
                    }
                }
            }
            Rectangle { id: roundMask; anchors.fill: parent; radius: 24; visible: false }
            GE.OpacityMask { anchors.fill: parent; source: body; maskSource: roundMask }
            Rectangle {
                anchors.fill: parent; radius: 24; color: "transparent"
                border.width: 1; border.color: "#38FFFFFF"
            }

            // spinning vinyl
            Item {
                id: vinyl
                width: 104; height: 104
                anchors.left: parent.left; anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter

                Rectangle { anchors.fill: parent; radius: width / 2; color: "#141018" }
                Repeater {   // grooves
                    model: 4
                    Rectangle {
                        anchors.centerIn: parent
                        width: vinyl.width - 8 - index * 9; height: width; radius: width / 2
                        color: "transparent"; border.width: 1; border.color: "#18FFFFFF"
                    }
                }
                Item {
                    id: disc
                    anchors.centerIn: parent
                    width: 64; height: 64
                    Image {
                        id: artImg
                        anchors.fill: parent
                        source: face.art
                        fillMode: Image.PreserveAspectCrop
                        visible: false
                    }
                    Rectangle {
                        id: artFallback
                        anchors.fill: parent; visible: false
                        gradient: Gradient { GradientStop { position: 0; color: face.sky } GradientStop { position: 1; color: face.sakura } }
                    }
                    Rectangle { id: circle; anchors.fill: parent; radius: width / 2; visible: false }
                    GE.OpacityMask {
                        anchors.fill: parent
                        source: artImg.status === Image.Ready ? artImg : artFallback
                        maskSource: circle
                    }
                    Rectangle { anchors.centerIn: parent; width: 9; height: 9; radius: 4.5; color: "#141018"; border.color: "#55FFFFFF"; border.width: 1 }
                    RotationAnimation on rotation {
                        from: 0; to: 360; duration: 9000; loops: Animation.Infinite
                        running: face.playing
                        paused: !face.playing && running
                    }
                }
                // sheen
                Rectangle {
                    anchors.fill: parent; radius: width / 2
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#20FFFFFF" }
                        GradientStop { position: 0.45; color: "#00FFFFFF" }
                    }
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: face.player && face.player.Raise() }
            }

            ColumnLayout {
                anchors.left: vinyl.right; anchors.leftMargin: 16
                anchors.right: parent.right; anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    // marquee title
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: title.implicitHeight
                        clip: true
                        Text {
                            id: title
                            text: face.player ? (face.player.track || face.player.identity) : ""
                            font.family: "Poppins"; font.pixelSize: 17; font.weight: Font.Medium
                            color: "white"
                            readonly property real overflow: Math.max(0, implicitWidth - parent.width)
                            SequentialAnimation on x {
                                running: title.overflow > 0
                                loops: Animation.Infinite
                                PauseAnimation { duration: 2500 }
                                NumberAnimation { to: -title.overflow; duration: title.overflow * 30; easing.type: Easing.InOutSine }
                                PauseAnimation { duration: 1500 }
                                NumberAnimation { to: 0; duration: title.overflow * 30; easing.type: Easing.InOutSine }
                            }
                        }
                    }
                    // equalizer
                    Row {
                        spacing: 3
                        Layout.preferredHeight: 18
                        Repeater {
                            model: 4
                            Rectangle {
                                width: 3; radius: 1.5
                                anchors.bottom: parent.bottom
                                height: 4
                                gradient: Gradient { GradientStop { position: 0; color: face.sakura } GradientStop { position: 1; color: face.sky } }
                                SequentialAnimation on height {
                                    running: face.playing
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 6 + Math.random() * 12; duration: 260 + index * 70; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 3 + Math.random() * 5; duration: 220 + index * 60; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 8 + Math.random() * 10; duration: 300 + index * 40; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 4; duration: 240; easing.type: Easing.InOutSine }
                                }
                            }
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: face.player ? (face.player.artist || face.player.identity) : ""
                    elide: Text.ElideRight
                    font.family: "Poppins"; font.pixelSize: 13; font.weight: Font.Light
                    color: "#D9E2FF"
                }

                // progress
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 14
                    Layout.topMargin: 4
                    Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 3; radius: 1.5; color: "#30FFFFFF" }
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width * face.progress; height: 3; radius: 1.5
                        gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: face.sky } GradientStop { position: 1; color: face.sakura } }
                        Behavior on width { NumberAnimation { duration: 950 } }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: face.player ? face.fmt(face.player.position) : ""; font.family: "Poppins"; font.pixelSize: 11; color: "#B8C4E8" }
                    Item { Layout.fillWidth: true }
                    Repeater {
                        model: [
                            { icon: "media-skip-backward", act: "prev", size: 18 },
                            { icon: face.playing ? "media-playback-pause" : "media-playback-start", act: "toggle", size: 24 },
                            { icon: "media-skip-forward", act: "next", size: 18 }
                        ]
                        Item {
                            width: 34; height: 30
                            Rectangle {
                                anchors.centerIn: parent
                                width: modelData.act === "toggle" ? 32 : 26; height: width; radius: width / 2
                                color: btn.containsMouse ? "#40FFFFFF" : (modelData.act === "toggle" ? "#22FFFFFF" : "transparent")
                                Behavior on color { ColorAnimation { duration: 200 } }
                            }
                            Kirigami.Icon {
                                anchors.centerIn: parent
                                width: modelData.size; height: width
                                source: modelData.icon
                                isMask: true; color: "white"
                                scale: btn.pressed ? 0.85 : 1
                                Behavior on scale { NumberAnimation { duration: 120 } }
                            }
                            MouseArea {
                                id: btn
                                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!face.player) return
                                    if (modelData.act === "prev") face.player.Previous()
                                    else if (modelData.act === "next") face.player.Next()
                                    else face.player.PlayPause()
                                }
                            }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: face.player && face.player.length > 0 ? face.fmt(face.player.length) : ""; font.family: "Poppins"; font.pixelSize: 11; color: "#B8C4E8" }
                }
            }
        }
    }
}
