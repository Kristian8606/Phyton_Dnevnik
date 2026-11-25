import QtQuick
import QtQuick.Controls

Dialog {
    id: dialog

    background: Rectangle {
        radius: 16
        color: dialog.palette.window
        border.color: dialog.palette.mid
    }

    header: Label {
        text: dialog.title
        visible: parent?.parent === Overlay.overlay && text.length > 0
        elide: Text.ElideRight
        font.bold: true
        padding: 12
    }
}
