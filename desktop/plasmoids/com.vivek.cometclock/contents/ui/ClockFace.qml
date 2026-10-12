import QtQuick
import QtQuick.Effects
import QtQuick.Particles
import Qt5Compat.GraphicalEffects as GE

// Kimi no Na wa themed clock: pale sky-to-sakura gradient that slowly drifts,
// rolling digits, a comet that crosses the line once a minute, soft sparkles.
Item {
    id: face
    property string userName: "@USER_NAME@"
    property var now: new Date()
    property real progress: 0          // 0..1 through the current minute

    readonly property color sky: "#86BEFF"
    readonly property color sakura: "#FFA3D2"
    readonly property color glow: "#3B2391"

    // fonts ship inside the widget, so they work without a re-login
    FontLoader { id: script; source: "../fonts/GreatVibes-Regular.ttf" }
    FontLoader { source: "../fonts/Poppins-Thin.ttf" }
    FontLoader { id: poppins; source: "../fonts/Poppins-ExtraLight.ttf" }
    FontLoader { source: "../fonts/Poppins-Light.ttf" }
    FontLoader { source: "../fonts/Poppins-Regular.ttf" }
    readonly property string sans: poppins.status === FontLoader.Ready ? poppins.font.family : "Poppins"

    implicitWidth: 620
    implicitHeight: col.implicitHeight + 40

    function pad(n) { return n < 10 ? "0" + n : "" + n }
    readonly property int h12: (now.getHours() % 12) || 12
    readonly property string greeting: {
        const h = now.getHours()
        return h < 5 ? "Sweet dreams" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon"
             : h < 21 ? "Good evening" : "Good night"
    }

    function tick() {
        now = new Date()
        const s = now.getSeconds() + now.getMilliseconds() / 1000
        sweep.stop()
        sweep.from = s / 60
        sweep.to = Math.min(1, (Math.floor(s) + 1) / 60)
        sweep.duration = Math.max(1, 1000 - now.getMilliseconds())
        sweep.start()
        timer.interval = 1000 - now.getMilliseconds()
    }
    Timer { id: timer; running: true; repeat: true; interval: 1000; triggeredOnStart: true; onTriggered: face.tick() }
    NumberAnimation { id: sweep; target: face; property: "progress" }

    // entrance
    opacity: 0
    Component.onCompleted: intro.start()
    ParallelAnimation {
        id: intro
        NumberAnimation { target: face; property: "opacity"; to: 1; duration: 1400; easing.type: Easing.OutCubic }
        NumberAnimation { target: col; property: "anchors.topMargin"; from: 46; to: 20; duration: 1600; easing.type: Easing.OutExpo }
    }

    HoverHandler { id: hover }

    // ── floating sparkles + the comet's tail ──
    ParticleSystem { id: sys }
    ImageParticle {
        system: sys; groups: ["dust"]
        source: "qrc:///particleresources/star.png"
        color: "#FFFFFF"; colorVariation: 0.25; alpha: 0.0; alphaVariation: 0.5
        entryEffect: ImageParticle.Fade
        rotationVariation: 180; rotationVelocityVariation: 40
    }
    ImageParticle {
        system: sys; groups: ["tail"]
        source: "qrc:///particleresources/glowdot.png"
        color: face.sakura; colorVariation: 0.3
        entryEffect: ImageParticle.Fade
    }
    Emitter {
        system: sys; group: "dust"
        anchors.fill: parent
        emitRate: hover.hovered ? 6 : 2.2; lifeSpan: 4200; lifeSpanVariation: 1500
        size: 9; sizeVariation: 6; endSize: 0
        velocity: AngleDirection { angle: -90; angleVariation: 40; magnitude: 7; magnitudeVariation: 5 }
    }
    Emitter {
        system: sys; group: "tail"
        x: col.x + comet.x + comet.head - 3; y: col.y + comet.y + comet.height / 2 - 3
        width: 6; height: 6
        emitRate: 45; lifeSpan: 1100; lifeSpanVariation: 300
        size: 10; sizeVariation: 4; endSize: 1
        velocity: AngleDirection { angle: 180; angleVariation: 22; magnitude: 22; magnitudeVariation: 12 }
    }

    Column {
        id: col
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top; anchors.topMargin: 20
        spacing: 2

        // greeting
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: face.greeting + ", " + face.userName
            font.family: script.status === FontLoader.Ready ? script.font.family : "Great Vibes"; font.pixelSize: 40
            color: "#FFF0F7"
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#7A1F5C"; shadowBlur: 0.8; blurMax: 20; shadowHorizontalOffset: 0; shadowVerticalOffset: 1 }
        }

        // time
        Row {
            id: timeBlock
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 10

            Item {
                id: timeHolder
                width: digits.width; height: digits.height

                Row {
                    id: digits
                    visible: false
                    layer.enabled: true
                    readonly property font f: Qt.font({ family: face.sans, weight: Font.ExtraLight, pixelSize: 120, features: { "tnum": 1 } })
                    Digit { value: face.h12 >= 10 ? "1" : ""; font: digits.f }
                    Digit { value: "" + (face.h12 % 10); font: digits.f }
                    Text {
                        text: ":"; font: digits.f; color: "white"
                        height: parent.height; verticalAlignment: Text.AlignVCenter
                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.25; duration: 1000; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1.0; duration: 1000; easing.type: Easing.InOutSine }
                        }
                    }
                    Digit { value: "" + Math.floor(face.now.getMinutes() / 10); font: digits.f }
                    Digit { value: "" + (face.now.getMinutes() % 10); font: digits.f }
                }

                // drifting gradient, masked by the digits
                Item {
                    id: shimmer
                    visible: false
                    width: digits.width; height: digits.height
                    clip: true
                    Rectangle {
                        width: parent.width * 2; height: parent.height
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.00; color: face.sky }
                            GradientStop { position: 0.17; color: "#FFFFFF" }
                            GradientStop { position: 0.30; color: face.sakura }
                            GradientStop { position: 0.50; color: face.sky }
                            GradientStop { position: 0.67; color: "#FFFFFF" }
                            GradientStop { position: 0.80; color: face.sakura }
                            GradientStop { position: 1.00; color: face.sky }
                        }
                        NumberAnimation on x { from: 0; to: -shimmer.width; duration: 9000; loops: Animation.Infinite }
                    }
                }

                GE.OpacityMask {
                    anchors.fill: parent
                    source: shimmer; maskSource: digits
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: face.glow
                        shadowBlur: hover.hovered ? 1.0 : 0.8
                        shadowOpacity: hover.hovered ? 1.0 : 0.9
                        shadowScale: 1.03
                        blurMax: 40
                        shadowHorizontalOffset: 0; shadowVerticalOffset: 0
                        Behavior on shadowBlur { NumberAnimation { duration: 500 } }
                        Behavior on shadowOpacity { NumberAnimation { duration: 500 } }
                    }
                }
            }

            // AM/PM over seconds
            Column {
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: 6
                spacing: -4
                layer.enabled: true
                layer.effect: MultiEffect { shadowEnabled: true; shadowColor: face.glow; shadowBlur: 0.7; blurMax: 16; shadowHorizontalOffset: 0; shadowVerticalOffset: 0 }
                Text {
                    text: face.now.getHours() < 12 ? "AM" : "PM"
                    font.family: face.sans; font.weight: Font.Normal; font.pixelSize: 20; font.letterSpacing: 4
                    color: face.sakura
                }
                Row {
                    readonly property font f: Qt.font({ family: face.sans, weight: Font.Light, pixelSize: 24, features: { "tnum": 1 } })
                    Digit { value: "" + Math.floor(face.now.getSeconds() / 10); font: parent.f; color: "#E8F2FF" }
                    Digit { value: "" + (face.now.getSeconds() % 10); font: parent.f; color: "#E8F2FF" }
                }
            }
        }

        // comet line: fills once per minute
        Item {
            id: comet
            anchors.horizontalCenter: parent.horizontalCenter
            width: timeBlock.width - 8; height: 14
            readonly property real head: width * face.progress

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#00FFFFFF" }
                    GradientStop { position: 0.5; color: "#55FFFFFF" }
                    GradientStop { position: 1; color: "#88FFFFFF" }
                }
            }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: comet.head; height: 2; radius: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#00FFFFFF" }
                    GradientStop { position: 0.55; color: face.sky }
                    GradientStop { position: 1.0; color: face.sakura }
                }
            }
            Rectangle {
                x: comet.head - width / 2
                anchors.verticalCenter: parent.verticalCenter
                width: 8; height: 8; radius: 4
                color: "white"
                layer.enabled: true
                layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#FF8FCB"; shadowBlur: 1.0; shadowScale: 1.6; blurMax: 24; shadowHorizontalOffset: 0; shadowVerticalOffset: 0 }
            }
        }

        // date
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            topPadding: 4
            text: Qt.formatDate(face.now, "dddd  ·  d MMMM yyyy").toUpperCase()
            font.family: face.sans; font.weight: Font.Normal; font.pixelSize: 15; font.letterSpacing: 5
            color: "#F4F7FF"
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#2A1866"; shadowBlur: 0.7; blurMax: 16; shadowHorizontalOffset: 0; shadowVerticalOffset: 1 }
        }
    }
}
