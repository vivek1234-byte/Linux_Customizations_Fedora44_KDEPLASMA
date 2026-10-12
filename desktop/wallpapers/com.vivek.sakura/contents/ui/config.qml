import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    property string cfg_Image
    property int cfg_Density
    QQC2.TextField {
        Kirigami.FormData.label: "Picture:"
        text: cfg_Image
        onTextEdited: cfg_Image = text
        Layout.minimumWidth: Kirigami.Units.gridUnit * 25
    }
    QQC2.SpinBox {
        Kirigami.FormData.label: "Petal amount (%):"
        from: 0; to: 300; stepSize: 25
        value: cfg_Density
        onValueModified: cfg_Density = value
    }
}
