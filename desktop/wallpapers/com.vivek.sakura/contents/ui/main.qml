import QtQuick
import QtQuick.Particles
import org.kde.plasma.plasmoid
import org.kde.taskmanager as TaskManager

// A still picture with sakura petals drifting across it on the breeze.
// Petals pause while the focused window is maximised/fullscreen (saves battery).
WallpaperItem {
    id: root
    readonly property real density: (root.configuration.Density ?? 100) / 100

    Rectangle { anchors.fill: parent; color: "#1b1530" }
    Image {
        anchors.fill: parent
        source: root.configuration.Image
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: root.width * Screen.devicePixelRatio
        sourceSize.height: root.height * Screen.devicePixelRatio
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 600 } }
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

    // from the top edge, drifting down and to the right
    Emitter {
        system: sys; group: "far"
        x: -root.width * 0.3; y: -30; width: root.width * 1.1; height: 10
        emitRate: 3.5 * root.density; lifeSpan: 22000
        size: 13; sizeVariation: 5
        velocity: AngleDirection { angle: 68; angleVariation: 12; magnitude: 38; magnitudeVariation: 12 }
    }
    Emitter {
        system: sys; group: "near"
        x: -root.width * 0.3; y: -40; width: root.width * 1.1; height: 10
        emitRate: 1.6 * root.density; lifeSpan: 15000
        size: 26; sizeVariation: 9
        velocity: AngleDirection { angle: 62; angleVariation: 14; magnitude: 70; magnitudeVariation: 25 }
    }
    Emitter {
        system: sys; group: "near2"
        x: -root.width * 0.3; y: -40; width: root.width * 1.1; height: 10
        emitRate: 1.0 * root.density; lifeSpan: 15000
        size: 22; sizeVariation: 8
        velocity: AngleDirection { angle: 64; angleVariation: 14; magnitude: 64; magnitudeVariation: 22 }
    }
    // a few blown in from the left side
    Emitter {
        system: sys; group: "near"
        x: -40; y: 0; width: 10; height: root.height * 0.55
        emitRate: 0.5 * root.density; lifeSpan: 14000
        size: 24; sizeVariation: 8
        velocity: AngleDirection { angle: 18; angleVariation: 14; magnitude: 95; magnitudeVariation: 25 }
    }

    // breeze: side-to-side sway + light gravity
    Wander { system: sys; anchors.fill: parent; xVariance: 55; yVariance: 18; pace: 90; affectedParameter: Wander.Velocity }
    Gravity { system: sys; anchors.fill: parent; angle: 90; magnitude: 4 }
}
