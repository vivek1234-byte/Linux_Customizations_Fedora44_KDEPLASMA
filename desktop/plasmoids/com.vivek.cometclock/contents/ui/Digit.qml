import QtQuick

// One character that rolls up (old slides out, new slides in) when it changes.
Item {
    id: d
    property string value: ""
    property font font
    property color color: "white"
    property string sizer: "0"      // widest glyph this slot can show

    TextMetrics { id: tm; font: d.font; text: d.sizer }
    implicitWidth: value === "" ? 0 : tm.advanceWidth
    implicitHeight: tm.height
    clip: true
    Behavior on implicitWidth { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

    Text {
        id: a
        width: d.width; height: d.height
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        font: d.font; color: d.color
    }
    Text {
        id: b
        width: d.width; height: d.height
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        font: d.font; color: d.color; opacity: 0
    }

    ParallelAnimation {
        id: roll
        NumberAnimation { target: a; property: "y"; to: -d.height * 0.55; duration: 700; easing.type: Easing.InOutCubic }
        NumberAnimation { target: a; property: "opacity"; to: 0; duration: 450 }
        NumberAnimation { target: b; property: "y"; from: d.height * 0.55; to: 0; duration: 700; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
        NumberAnimation { target: b; property: "opacity"; from: 0; to: 1; duration: 600; easing.type: Easing.OutCubic }
        onFinished: { a.text = b.text; a.y = 0; a.opacity = 1; b.opacity = 0 }
    }

    onValueChanged: {
        if (a.text === "") { a.text = value; return }
        if (roll.running) roll.complete()
        b.text = value
        roll.start()
    }
    Component.onCompleted: a.text = value
}
