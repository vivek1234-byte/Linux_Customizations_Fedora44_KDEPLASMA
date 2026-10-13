import QtQuick
import QtQuick.Particles
import org.kde.plasma.plasmoid
import org.kde.taskmanager as TaskManager

// A still picture with sakura petals drifting across it on the breeze, plus a
// music visualizer (Visualizer.qml) while something is playing. Petals dance
// harder with the music. Everything pauses while the focused window is
// maximised/fullscreen (saves battery).
WallpaperItem {
    id: root
    readonly property real density: (root.configuration.Density ?? 100) / 100
    // loudness from the visualizer (0 when silent), makes the petals dance
    readonly property real music: viz.item && viz.item.visible ? viz.item.energy : 0

    Rectangle { anchors.fill: parent; color: "#1b1530" }
    Image {
        id: picture
        anchors.fill: parent
        source: root.configuration.Image
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: root.width * Screen.devicePixelRatio
        sourceSize.height: root.height * Screen.devicePixelRatio
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 600 } }
    }

    // ── music visualizer (in its own file so a problem there can't break the wallpaper) ──
    Loader {
        id: viz
        anchors.fill: parent
        asynchronous: true
        source: "Visualizer.qml"
        onLoaded: {
            item.picture = picture
            item.paused = Qt.binding(() => root.covered)
        }
    }
    Connections {
        target: viz.item
        ignoreUnknownSignals: true
        function onBeat(s) { if (s > 0.75) gust.burst(Math.round(1 + s * 2)) }
    }

    // ── is the desktop covered? ──
    property bool covered: false
    TaskManager.VirtualDesktopInfo { id: vdi }
    TaskManager.ActivityInfo { id: ai }
    TaskManager.TasksModel {
        id: tasks
        groupMode: TaskManager.TasksModel.GroupDisabled
        virtualDesktop: vdi.currentDesktop
        activity: ai.currentActivity
        filterByVirtualDesktop: true
        filterByActivity: true
    }
    function checkCovered() {
        let c = false
        for (let i = 0; i < tasks.count; i++) {
            const idx = tasks.index(i, 0)
            // only the focused window counts: with "Show Desktop" nothing is active
            if (!tasks.data(idx, TaskManager.AbstractTasksModel.IsActive)) continue
            if (tasks.data(idx, TaskManager.AbstractTasksModel.IsMinimized)) continue
            if (tasks.data(idx, TaskManager.AbstractTasksModel.IsMaximized)
                || tasks.data(idx, TaskManager.AbstractTasksModel.IsFullScreen)) { c = true; break }
        }
        covered = c
    }
    Timer { interval: 1500; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.checkCovered() }

    // ── petals ──
    ParticleSystem { id: sys; paused: root.covered }

    // far layer: small, faint, slow
    ImageParticle {
        system: sys; groups: ["far"]
        source: "../images/petal2.png"
        alpha: 0.55; alphaVariation: 0.2
        rotationVariation: 180; rotationVelocity: 20; rotationVelocityVariation: 50
        entryEffect: ImageParticle.Fade
    }
    // near layer: bigger, brighter, two tints
    ImageParticle {
        system: sys; groups: ["near"]
        source: "../images/petal1.png"
        alpha: 0.95; alphaVariation: 0.1
        rotationVariation: 180; rotationVelocity: 40; rotationVelocityVariation: 90
        entryEffect: ImageParticle.Fade
    }
    ImageParticle {
        system: sys; groups: ["near2"]
        source: "../images/petal3.png"
        alpha: 0.9; alphaVariation: 0.1
        rotationVariation: 180; rotationVelocity: -40; rotationVelocityVariation: 90
        entryEffect: ImageParticle.Fade
    }

    // all petals start just above the top edge and float down slowly
    // (steady speeds, no gravity build-up, nothing from the sides)
    Emitter {
        system: sys; group: "far"
        x: 0; y: -30; width: root.width; height: 10
        emitRate: 3.0 * root.density * (1 + root.music * 0.8); lifeSpan: 40000
        size: 13; sizeVariation: 5
        velocity: AngleDirection { angle: 88; angleVariation: 10; magnitude: 30; magnitudeVariation: 6 }
    }
    Emitter {
        system: sys; group: "near"
        x: 0; y: -40; width: root.width; height: 10
        emitRate: 1.4 * root.density * (1 + root.music * 0.8); lifeSpan: 30000
        size: 26; sizeVariation: 9
        velocity: AngleDirection { angle: 86; angleVariation: 10; magnitude: 44; magnitudeVariation: 8 }
    }
    Emitter {
        system: sys; group: "near2"
        x: 0; y: -40; width: root.width; height: 10
        emitRate: 0.9 * root.density * (1 + root.music * 0.8); lifeSpan: 30000
        size: 22; sizeVariation: 8
        velocity: AngleDirection { angle: 90; angleVariation: 10; magnitude: 40; magnitudeVariation: 8 }
    }

    // on big beats a few extra petals start falling from the top (same gentle speed)
    Emitter {
        id: gust
        system: sys; group: "near"; enabled: false
        x: 0; y: -40; width: root.width; height: 10
        lifeSpan: 30000; size: 24; sizeVariation: 8
        velocity: AngleDirection { angle: 88; angleVariation: 10; magnitude: 44; magnitudeVariation: 8 }
    }

    // breeze: gentle side-to-side sway, a little livelier with music
    Wander { system: sys; anchors.fill: parent; xVariance: 30 + root.music * 12; yVariance: 6; pace: 45 + root.music * 25; affectedParameter: Wander.Velocity }
}
