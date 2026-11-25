import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: view
    required property QtObject controller
    required property var tones
    required property color warningColor
    property string firstDate: controller.todayIso
    property string lastDate: controller.todayIso
    property bool choosingStart: true
    property var result: ({})

    readonly property string first: period.checked ? firstDate : ""
    readonly property string last: period.checked ? lastDate : ""
    readonly property bool validRange: !period.checked || firstDate <= lastDate

    onVisibleChanged: {
        if (visible) {
            today.checked = true
            firstDate = controller.todayIso
            lastDate = controller.todayIso
            result = ({})
        }
    }

    function chooseDate(start) {
        choosingStart = start
        calendar.open()
    }

    function displayDate(iso) {
        return iso.split("-").reverse().join(".")
    }

    component PrintAction: Button {
        id: button
        property bool primary: false
        padding: 9
        leftPadding: 13
        rightPadding: 13
        contentItem: Label {
            text: button.text
            color: button.primary && button.enabled ? view.tones.onAccent : view.tones.text
            font.weight: button.primary ? Font.DemiBold : Font.Normal
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            opacity: button.enabled ? 1 : 0.55
        }
        background: Rectangle {
            radius: 7
            color: button.primary && button.enabled ? view.tones.selection
                                                    : button.hovered ? view.tones.hover : view.tones.surface
            border.color: button.visualFocus ? view.tones.accent : view.tones.line
        }
    }

    Rectangle {
        anchors.top: parent.top
        anchors.topMargin: 28
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(560, parent.width - 32)
        implicitHeight: controls.implicitHeight + 40
        radius: 12
        color: view.tones.surface
        border.color: view.tones.line

        ColumnLayout {
            id: controls
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14

            Label {
                text: "Печат на операции"
                color: view.tones.text
                font.pixelSize: 21
                font.weight: Font.DemiBold
            }
            RowLayout {
                ButtonGroup { id: rangeMode }
                RadioButton {
                    id: today
                    objectName: "printTodayOption"
                    text: "Днес"
                    checked: true
                    ButtonGroup.group: rangeMode
                    onClicked: view.result = ({})
                }
                RadioButton {
                    id: period
                    objectName: "printPeriodOption"
                    text: "От–до"
                    ButtonGroup.group: rangeMode
                    onClicked: view.result = ({})
                }
            }
            RowLayout {
                visible: period.checked
                spacing: 8
                Label { text: "От"; color: view.tones.muted }
                PrintAction {
                    id: firstButton
                    objectName: "printFirstDate"
                    text: view.displayDate(view.firstDate)
                    Accessible.name: "Начална дата " + text
                    onClicked: view.chooseDate(true)
                }
                Label { text: "До"; color: view.tones.muted }
                PrintAction {
                    id: lastButton
                    objectName: "printLastDate"
                    text: view.displayDate(view.lastDate)
                    Accessible.name: "Крайна дата " + text
                    onClicked: view.chooseDate(false)
                }
            }
            Label {
                objectName: "printFeedback"
                Layout.fillWidth: true
                visible: text !== ""
                wrapMode: Text.WordWrap
                text: !view.validRange ? "Началната дата трябва да е преди или на крайната дата."
                                       : (view.result.message || "")
                color: view.validRange && view.result.ok ? view.tones.muted : view.warningColor
            }
            PrintAction {
                objectName: "printOperationsButton"
                Layout.alignment: Qt.AlignRight
                text: "Печат…"
                primary: true
                enabled: view.validRange
                onClicked: view.result = view.controller.printOperations(view.first, view.last)
            }
        }
    }

    CalendarPicker {
        id: calendar
        parent: view.choosingStart ? firstButton : lastButton
        controller: view.controller
        selectedIso: view.choosingStart ? view.firstDate : view.lastDate
        todayIso: view.controller.todayIso
        earliestIso: view.controller.periodStartIso
        tones: view.tones
        onDateChosen: iso => {
            if (view.choosingStart)
                view.firstDate = iso
            else
                view.lastDate = iso
            view.result = ({})
            close()
            parent.forceActiveFocus()
        }
    }
}
