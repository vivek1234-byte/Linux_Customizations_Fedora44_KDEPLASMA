import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Qt5Compat.GraphicalEffects as GE
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris

// Dynamic Island desktop widget (sits behind windows, top centre).
//   idle      – hidden (fades away when nothing is playing)
//   compact   – spinning cover art + equalizer
//   expanded  – (hover / new track / click) title, artist, progress, controls
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    fullRepresentation: Item {
        id: face
        readonly property color sky: "#86BEFF"
        readonly property color sakura: "#FFA3D2"

        Mpris.Mpris2Model { id: mpris }
        readonly property var player: mpris.currentPlayer
        readonly property bool playing: !!player && player.playbackStatus === Mpris.PlaybackStatus.Playing
        // visible while playing; after a pause it lingers 8 s, then fades away
        property bool lingering: false
        onPlayingChanged: { lingering = !playing; if (!playing) lingerTimer.restart() }
        Timer { id: lingerTimer; interval: 8000; onTriggered: face.lingering = false }
        readonly property bool hasMedia: !!player && (playing || (lingering && player.playbackStatus === Mpris.PlaybackStatus.Paused))
        readonly property string art: player ? player.artUrl.toString() : ""
        readonly property string track: player ? (player.track || player.identity) : ""
        readonly property real progress: player && player.length > 0 ? Math.min(1, player.position / player.length) : 0

        property bool pinned: false
        property bool peek: false            // short expand when the track changes
        readonly property bool expanded: hasMedia && (hover.hovered || pinned || peek)
        readonly property string mode: !hasMedia ? "idle" : expanded ? "expanded" : "compact"

        onTrackChanged: if (hasMedia && track !== "") { peek = true; peekTimer.restart() }
        Timer { id: peekTimer; interval: 4000; onTriggered: face.peek = false }
        Timer { interval: 1000; repeat: true; running: face.playing; onTriggered: face.player.updatePosition() }


        readonly property real pillW: mode === "expanded" ? 470 : 210
        readonly property real pillH: mode === "expanded" ? 44 : 34

        Layout.preferredWidth: 500
        Layout.minimumWidth: 500
        Layout.preferredHeight: 64
        Layout.minimumHeight: 64

        function fmt(us) {
            const s = Math.max(0, Math.floor(us / 1e6))
            return Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60)
        }

        Item {
            id: pill
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top; anchors.topMargin: 5
            width: face.pillW; height: face.pillH
            opacity: face.hasMedia ? 1 : 0
            scale: face.hasMedia ? 1 : 0.6
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: 550; easing.type: Easing.OutBack } }
            Behavior on width { NumberAnimation { duration: 520; easing.type: Easing.OutBack; easing.overshoot: 1.1 } }
            Behavior on height { NumberAnimation { duration: 420; easing.type: Easing.OutBack; easing.overshoot: 1.3 } }

            HoverHandler { id: hover }

            Rectangle {
                id: body
                anchors.fill: parent
                radius: height / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#EE231C46" }
                    GradientStop { position: 0.5; color: "#EE2E1F52" }
                    GradientStop { position: 1.0; color: "#EE3F1E4A" }
                }
                border.width: 1; border.color: "#66C3A6FF"
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: face.playing ? "#B48CFF" : "#3B2391"
                    shadowOpacity: face.playing ? 0.75 : 0.5
                    shadowBlur: 0.7; blurMax: 24
                    shadowHorizontalOffset: 0; shadowVerticalOffset: 2
                    Behavior on shadowOpacity { NumberAnimation { duration: 600 } }
                }
            }

            Rectangle {
                anchors.fill: parent; radius: height / 2
                gradient: Gradient { GradientStop { position: 0; color: "#24FFFFFF" } GradientStop { position: 0.5; color: "#00FFFFFF" } }
            }

            // click the pill (not a button) to keep it open
            MouseArea { anchors.fill: parent; onClicked: face.pinned = !face.pinned }

            // progress hairline along the bottom (expanded)
            Item {
                anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width - parent.height; height: 2
                opacity: face.mode === "expanded" ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 300 } }
                Rectangle { anchors.fill: parent; radius: 1; color: "#22FFFFFF" }
                Rectangle {
                    width: parent.width * face.progress; height: 2; radius: 1
                    gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: face.sky } GradientStop { position: 1; color: face.sakura } }
                    Behavior on width { NumberAnimation { duration: 950 } }
                }
            }

            // ── cover art (compact + expanded) ──
            Item {
                id: disc
                property real d: face.mode === "expanded" ? 32 : 24
                width: d; height: d
                anchors.left: parent.left; anchors.leftMargin: (pill.height - d) / 2 + 2
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: face.mode === "expanded" ? -1 : 0
                opacity: face.mode === "idle" ? 0 : 1
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: 250 } }
                Behavior on d { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

                Image { id: artImg; anchors.fill: parent; source: face.art; fillMode: Image.PreserveAspectCrop; visible: false; sourceSize.width: 96 }
                Rectangle {
                    id: artFallback; anchors.fill: parent; visible: false
                    gradient: Gradient { GradientStop { position: 0; color: face.sky } GradientStop { position: 1; color: face.sakura } }
                }
                Rectangle { id: circle; anchors.fill: parent; radius: width / 2; visible: false }
                GE.OpacityMask { anchors.fill: parent; source: artImg.status === Image.Ready ? artImg : artFallback; maskSource: circle }
                Rectangle { anchors.centerIn: parent; width: 5; height: 5; radius: 2.5; color: "#231C46" }
                RotationAnimation on rotation {
                    from: 0; to: 360; duration: 8000; loops: Animation.Infinite
                    running: face.playing; paused: !face.playing && running
                }
            }

            // ── expanded: title + artist ──
            Column {
                anchors.left: disc.right; anchors.leftMargin: 10
                anchors.right: controls.left; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -2
                spacing: -2
                opacity: face.mode === "expanded" ? 1 : 0
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: 300 } }

                Item {
                    width: parent.width; height: title.implicitHeight
                    clip: true
                    Text {
                        id: title
                        text: face.track
                        font.family: "Poppins"; font.pixelSize: 13; font.weight: Font.Medium
                        color: "white"
                        readonly property real overflow: Math.max(0, implicitWidth - parent.width)
                        SequentialAnimation on x {
                            running: title.overflow > 0 && face.mode === "expanded"
                            loops: Animation.Infinite
                            PauseAnimation { duration: 1800 }
                            NumberAnimation { to: -title.overflow; duration: title.overflow * 28; easing.type: Easing.InOutSine }
                            PauseAnimation { duration: 1200 }
                            NumberAnimation { to: 0; duration: title.overflow * 28; easing.type: Easing.InOutSine }
                        }
                    }
                }
                Text {
                    width: parent.width
                    text: (face.player ? (face.player.artist || face.player.identity) : "")
                          + (face.player && face.player.length > 0 ? "  ·  " + face.fmt(face.player.position) + " / " + face.fmt(face.player.length) : "")
                    elide: Text.ElideRight
                    font.family: "Poppins"; font.pixelSize: 10; font.weight: Font.Light
                    color: "#D6C8FF"
                }
            }

            // ── expanded: controls ──
            Row {
                id: controls
                anchors.right: eq.left; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -1
                spacing: 2
                opacity: face.mode === "expanded" ? 1 : 0
                visible: opacity > 0
                width: face.mode === "expanded" ? implicitWidth : 0
                Behavior on opacity { NumberAnimation { duration: 300 } }
                Repeater {
                    model: [
                        { icon: "media-skip-backward", act: "prev" },
                        { icon: face.playing ? "media-playback-pause" : "media-playback-start", act: "toggle" },
                        { icon: "media-skip-forward", act: "next" }
                    ]
                    Item {
                        width: 28; height: 28
                        Rectangle {
                            anchors.centerIn: parent; width: 26; height: 26; radius: 13
                            color: btn.containsMouse ? "#33FFFFFF" : "transparent"
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                        Kirigami.Icon {
                            anchors.centerIn: parent
                            width: modelData.act === "toggle" ? 18 : 15; height: width
                            source: modelData.icon; isMask: true; color: "white"
                            scale: btn.pressed ? 0.8 : 1
                            Behavior on scale { NumberAnimation { duration: 100 } }
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
            }

            // ── equalizer (compact + expanded) ──
            Row {
                id: eq
                anchors.right: parent.right; anchors.rightMargin: pill.height / 2 - 1
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: face.mode === "expanded" ? -1 : 0
                height: 14; spacing: 2.5
                opacity: face.mode === "idle" ? 0 : 1
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: 250 } }
                Repeater {
                    model: 4
                    Rectangle {
                        width: 2.5; radius: 1.25
                        anchors.bottom: parent.bottom
                        height: 3
                        gradient: Gradient { GradientStop { position: 0; color: face.sakura } GradientStop { position: 1; color: face.sky } }
                        SequentialAnimation on height {
                            running: face.playing
                            loops: Animation.Infinite
                            NumberAnimation { to: 5 + Math.random() * 9; duration: 240 + index * 70; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 3 + Math.random() * 4; duration: 210 + index * 50; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 7 + Math.random() * 7; duration: 280 + index * 40; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 3; duration: 220; easing.type: Easing.InOutSine }
                        }
                    }
                }
            }
        }
    }
}
