import QtQuick
import QtQuick.Controls

TextField {
    id: field
    property color focusBorder: palette.highlight
    property color errorBorder: focusBorder
    property bool invalid: false

    background: Rectangle {
        radius: 10
        color: field.palette.base
        border.color: field.invalid ? field.errorBorder : (field.activeFocus ? field.focusBorder : field.palette.mid)
        border.width: field.activeFocus || field.invalid ? 2 : 1
    }
}
