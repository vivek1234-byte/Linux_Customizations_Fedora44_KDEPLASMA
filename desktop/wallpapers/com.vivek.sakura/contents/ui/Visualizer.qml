import QtQuick
import QtQuick.Effects
import QtQuick.Particles
import QtCore
import org.kde.plasma.private.mpris as Mpris

// Music visualizer layer of the Sakura Breeze wallpaper.
//
// Audio comes from sakura-viz-bridge (cava), which keeps the newest frame in
// $XDG_RUNTIME_DIR/sakura-viz/frame as "v1;v2;...;" (0..1000, stereo: low
// notes in the middle). We read that file once per rendered frame.
//
// Layers, back to front: light-star pulse + ripples, ground haze,
// glowing bars with heart caps and reflections, floating hearts/notes/sparkles.
Item {
    id: viz

    // ── set by main.qml ──
    property bool paused: false
    property Item picture: null      // wallpaper Image, to locate the light-star
    property real starU: 0.5         // light-star position inside the picture (0..1)
    property real starV: 0.712

    // ── read by main.qml ──
    property real energy: 0          // smoothed loudness 0..1
    property real pulse: 0           // beat flash 0..1, decays quickly
    signal beat(real strength)

    readonly property int count: 56
    readonly property string frameUrl:
        StandardPaths.writableLocation(StandardPaths.RuntimeLocation).toString() + "/sakura-viz/frame"

    readonly property color cTop: "#8FC3FF"
    readonly property color cMid: "#B394FF"
    readonly property color cBot: "#FF6FB5"

    // ── stage geometry: bars sit just above the dock ──
    readonly property real stageW: Math.min(width * 0.55, 1060)
    readonly property real baseY: height - 116
    readonly property real maxH: Math.min(250, height * 0.24)

    // where the light-star of the picture is on screen
    readonly property point star: {
        const p = picture
        if (!p || p.implicitWidth <= 0 || p.implicitHeight <= 0)
            return Qt.point(width * starU, height * starV)
        const s = Math.max(width / p.implicitWidth, height / p.implicitHeight)
        const w = p.implicitWidth * s, h = p.implicitHeight * s
        return Qt.point((width - w) / 2 + starU * w, (height - h) / 2 + starV * h)
    }

    // ── show while music plays ──
    Mpris.Mpris2Model { id: mpris }
    readonly property bool playing: !!mpris.currentPlayer
                                    && mpris.currentPlayer.playbackStatus === Mpris.PlaybackStatus.Playing
    property bool lingering: false
    onPlayingChanged: { lingering = !playing; if (!playing) lingerTimer.restart() }
    Timer { id: lingerTimer; interval: 4000; onTriggered: viz.lingering = false }

    readonly property bool live: playing || lingering
    property bool hasData: false
    readonly property bool shown: live && hasData
    opacity: shown ? 1 : 0
    visible: opacity > 0.001
    Behavior on opacity { NumberAnimation { duration: 1100; easing.type: Easing.InOutSine } }

    // ── reading frames ──
    property bool busy: false
    property double lastFrameAt: 0
    property double lastPollAt: 0
    function poll() {
        const now = Date.now()
        if (busy || now - lastPollAt < 14) return
        busy = true; lastPollAt = now
        const x = new XMLHttpRequest()
        x.onreadystatechange = function() {
            if (x.readyState !== XMLHttpRequest.DONE) return
            viz.busy = false
            const t = x.responseText
            if (!t || t.length < 8) return
            const parts = t.split(";")
            const n = Math.min(viz.count, parts.length)
            for (let i = 0; i < n; i++) {
                const b = bars.itemAt(i)
                if (b) b.target = Math.min(1, (parseInt(parts[i]) || 0) / 1000)
            }
            viz.lastFrameAt = Date.now()
        }
        x.open("GET", frameUrl)
        x.send()
    }

    // ── per-frame animation ──
    property real avgBass: 0
    property double lastBeat: 0
    property int beatNo: 0
    function step(dt) {
        dt = Math.min(dt, 0.05)
        hasData = Date.now() - lastFrameAt < 1200
        let sum = 0, bass = 0, nb = 0
        const mid = (count - 1) / 2
        for (let i = 0; i < count; i++) {
            const b = bars.itemAt(i)
            if (!b) continue
            const t = hasData ? b.target : 0
            const k = t > b.level ? Math.min(1, dt * 24) : Math.min(1, dt * 7)   // fast up, soft down
            b.level += (t - b.level) * k
            b.peak = Math.max(b.level, b.peak - dt * 0.42)
            sum += b.level
            if (Math.abs(i - mid) < 9) { bass += b.level; nb++ }
            // little sparkles from the tops of loud bars
            if (b.level > 0.55 && Math.random() < dt * b.level * 2.2)
                sparkEm.burst(1, stage.x + b.x + b.width / 2, baseY - b.level * maxH)
        }
        energy += (Math.min(1, sum / count * 2.4) - energy) * Math.min(1, dt * 5)
        bass = nb ? bass / nb : 0
        avgBass += (bass - avgBass) * Math.min(1, dt * 1.5)
        const now = Date.now()
        if (bass > avgBass * 1.22 + 0.035 && bass > 0.2 && now - lastBeat > 180) {
            lastBeat = now
            handleBeat(Math.min(1, (bass - avgBass) * 3.2 + 0.35))
        }
        pulse = Math.max(0, pulse - dt * 2.4)
    }

    function handleBeat(s) {
        pulse = Math.max(pulse, s)
        beatNo++
        // ripple ring from the light-star
        const r = ripples.itemAt(beatNo % ripples.count)
        if (r && s > 0.45) r.fire(s)
        // hearts (and sometimes a note) float up from the middle bars
        const cx = stage.x + stage.width / 2
        const hearts = 1 + Math.round(s * 2.5)
        for (let i = 0; i < hearts; i++) {
            const x = cx + (Math.random() - 0.5) * stage.width * 0.55
            heartEm.burst(1, x, baseY - maxH * (0.35 + Math.random() * 0.4))
        }
        if (beatNo % 3 === 0) {
            const em = beatNo % 2 ? noteEm : note2Em
            em.burst(1, cx + (Math.random() - 0.5) * stage.width * 0.8, baseY - maxH * 0.6)
        }
        if (s > 0.6) starSparks.burst(Math.round(4 + s * 6), star.x, star.y)
        beat(s)
    }

    property real acc: 0
    FrameAnimation {
        running: viz.live && !viz.paused
        onTriggered: {
            viz.acc += frameTime
            if (viz.acc < 1 / 61) return       // bars update at ~60 fps, even on 144 Hz screens
            viz.poll(); viz.step(viz.acc); viz.acc = 0
        }
    }
    onLiveChanged: if (!live) { for (let i = 0; i < count; i++) { const b = bars.itemAt(i); if (b) b.target = 0 } }

    // ═══ light-star: the picture's light pillar and star breathe with the bass ═══
    Item {
        id: lightStar
        anchors.fill: parent
        opacity: 0.25 + viz.energy * 0.45 + viz.pulse * 0.6

        Image {   // pillar
            source: "../images/glow.png"
            width: 34 + viz.pulse * 26; height: viz.height * 1.25
            x: viz.star.x - width / 2; y: viz.star.y - height * 0.6
            opacity: 0.55
        }
        Image {   // horizontal flare
            source: "../images/glow-pink.png"
            width: viz.width * (0.42 + viz.pulse * 0.18); height: 22 + viz.pulse * 14
            x: viz.star.x - width / 2; y: viz.star.y - height / 2
            opacity: 0.8
        }
        Image {   // star bloom
            source: "../images/glow-pink.png"
            width: 260 * (0.75 + viz.pulse * 0.75 + viz.energy * 0.3); height: width
            x: viz.star.x - width / 2; y: viz.star.y - height / 2
        }
        Repeater {   // ripple rings on strong beats
            id: ripples
            model: 3
            Image {
                id: ring
                source: "../images/ring.png"
                width: 380; height: 380
                x: viz.star.x - width / 2; y: viz.star.y - height / 2
                scale: 0.1; opacity: 0
                function fire(s) { anim.stop(); peak = 0.55 + s * 0.4; anim.start() }
                property real peak: 0.8
                ParallelAnimation {
                    id: anim
                    NumberAnimation { target: ring; property: "scale"; from: 0.12; to: 1.7; duration: 1400; easing.type: Easing.OutCubic }
                    NumberAnimation { target: ring; property: "opacity"; from: ring.peak; to: 0; duration: 1400; easing.type: Easing.InQuad }
                }
            }
        }
    }

    // ═══ soft pink haze on the ground under the bars ═══
    Image {
        source: "../images/glow-pink.png"
        width: viz.stageW * 1.35; height: 190
        x: (viz.width - width) / 2; y: viz.baseY - height * 0.55
        opacity: 0.12 + viz.energy * 0.5 + viz.pulse * 0.2
    }

    // ═══ bars, heart caps, reflections ═══
    Item {
        id: stage
        width: viz.stageW
        height: viz.maxH + 44 + viz.maxH * 0.3
        x: (viz.width - width) / 2
        y: viz.baseY - viz.maxH - 44
        readonly property real base: viz.maxH + 44       // baseline inside the stage
        readonly property real slot: width / viz.count

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#9B6BFF"
            shadowBlur: 0.6
            blurMax: 24
            shadowOpacity: 0.7 + viz.pulse * 0.3
            shadowHorizontalOffset: 0; shadowVerticalOffset: 0
            brightness: viz.pulse * 0.1
        }

        Repeater {
            id: bars
            model: viz.count
            Item {
                property real target: 0
                property real level: 0
                property real peak: 0
                x: index * stage.slot
                width: stage.slot; height: stage.height

                Rectangle {   // the bar
                    id: bar
                    width: stage.slot * 0.56
                    x: (parent.width - width) / 2
                    height: Math.max(width, level * viz.maxH)
                    y: stage.base - height
                    radius: width / 2
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#FFFFFF" }
                        GradientStop { position: 0.12; color: viz.cTop }
                        GradientStop { position: 0.55; color: viz.cMid }
                        GradientStop { position: 1.0; color: viz.cBot }
                    }
                    Rectangle {   // candy shine
                        x: parent.width * 0.2; y: parent.width * 0.35
                        width: Math.max(1.5, parent.width * 0.24)
                        height: Math.max(0, parent.height - parent.width * 0.9)
                        radius: width / 2
                        color: "#8CFFFFFF"
                    }
                }
                Rectangle {   // reflection on the road
                    width: bar.width; x: bar.x
                    y: stage.base + 4
                    height: bar.height * 0.3
                    radius: width / 2
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#59FF9ACB" }
                        GradientStop { position: 1.0; color: "#00FF9ACB" }
                    }
                }
                Image {       // heart riding on the peak
                    source: "../images/heart.png"
                    width: stage.slot * 0.95; height: width
                    x: (parent.width - width) / 2
                    y: stage.base - peak * viz.maxH - height - 4
                    opacity: peak > 0.22 ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 300 } }
                    mipmap: true
                }
            }
        }
    }

    // ═══ floating hearts, notes and sparkles ═══
    ParticleSystem { id: ps; anchors.fill: parent; paused: viz.paused || !viz.visible }

    ImageParticle {
        system: ps; groups: ["heart"]
        source: "../images/heart.png"
        alpha: 0.95
        rotation: 0; rotationVariation: 22
        entryEffect: ImageParticle.Scale
    }
    ImageParticle {
        system: ps; groups: ["note"]
        source: "../images/note1.png"
        alpha: 0.95; rotationVariation: 18
        entryEffect: ImageParticle.Scale
    }
    ImageParticle {
        system: ps; groups: ["note2"]
        source: "../images/note2.png"
        alpha: 0.95; rotationVariation: 18
        entryEffect: ImageParticle.Scale
    }
    ImageParticle {
        system: ps; groups: ["spark"]
        source: "../images/sparkle.png"
        color: "#FFF4FA"; colorVariation: 0.12
        rotationVariation: 45
        entryEffect: ImageParticle.Scale
    }

    Emitter {
        id: heartEm
        system: ps; group: "heart"; enabled: false
        lifeSpan: 2800; lifeSpanVariation: 700
        size: 24; sizeVariation: 10; endSize: 12
        velocity: AngleDirection { angle: -90; angleVariation: 28; magnitude: 95; magnitudeVariation: 40 }
        acceleration: PointDirection { y: 18 }
    }
    Emitter {
        id: noteEm
        system: ps; group: "note"; enabled: false
        lifeSpan: 3200; lifeSpanVariation: 600
        size: 30; sizeVariation: 8; endSize: 18
        velocity: AngleDirection { angle: -90; angleVariation: 22; magnitude: 70; magnitudeVariation: 25 }
    }
    Emitter {
        id: note2Em
        system: ps; group: "note2"; enabled: false
        lifeSpan: 3200; lifeSpanVariation: 600
        size: 30; sizeVariation: 8; endSize: 18
        velocity: AngleDirection { angle: -90; angleVariation: 22; magnitude: 70; magnitudeVariation: 25 }
    }
    Emitter {   // a few notes drift up all the time while music plays
        system: ps; group: "note"
        enabled: viz.shown && !viz.paused
        x: stage.x; y: viz.baseY - 20; width: stage.width; height: 10
        emitRate: 0.25 + viz.energy * 0.9
        lifeSpan: 3600; size: 24; sizeVariation: 8; endSize: 10
        velocity: AngleDirection { angle: -90; angleVariation: 18; magnitude: 55; magnitudeVariation: 20 }
    }
    Emitter {
        id: sparkEm
        system: ps; group: "spark"; enabled: false
        lifeSpan: 800; lifeSpanVariation: 300
        size: 18; sizeVariation: 8; endSize: 2
        velocity: AngleDirection { angle: -90; angleVariation: 60; magnitude: 40; magnitudeVariation: 25 }
    }
    Emitter {
        id: starSparks
        system: ps; group: "spark"; enabled: false
        lifeSpan: 1100; lifeSpanVariation: 300
        size: 22; sizeVariation: 10; endSize: 2
        velocity: AngleDirection { angle: 0; angleVariation: 180; magnitude: 120; magnitudeVariation: 60 }
    }
    Wander {   // hearts and notes sway as they float
        system: ps; groups: ["heart", "note", "note2"]
        anchors.fill: parent
        xVariance: 45; pace: 70
        affectedParameter: Wander.Velocity
    }
}
