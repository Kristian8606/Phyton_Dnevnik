import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: picker
    required property QtObject controller
    required property string selectedIso
    required property string todayIso
    property string earliestIso: "0001-01-01"
    required property string localeName
    required property var tones
    signal dateChosen(string iso)

    readonly property var todayParts: todayIso.split("-")
    readonly property int latestYear: Number(todayParts[0])
    readonly property int latestMonth: Number(todayParts[1]) - 1
    readonly property var months: [
        qsTr("Януари"), qsTr("Февруари"), qsTr("Март"), qsTr("Април"), qsTr("Май"), qsTr("Юни"),
        qsTr("Юли"), qsTr("Август"), qsTr("Септември"), qsTr("Октомври"), qsTr("Ноември"), qsTr("Декември")
    ]
    property int shownYear: latestYear
    property int shownMonth: latestMonth
    property var markedDays: []

    width: 326
    padding: 12
    margins: 8
    x: 0
    y: parent.height + 7
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
    palette.window: tones.surface
    palette.base: tones.surface
    palette.text: tones.text
    palette.buttonText: tones.text
    palette.highlight: tones.selection
    palette.highlightedText: tones.onAccent

    function setMonth(year, month) {
        const limit = latestYear * 12 + latestMonth
        const target = Math.max(12, Math.min(limit, year * 12 + month))
        shownYear = Math.floor(target / 12)
        shownMonth = target % 12
        refreshActivity()
    }

    function refreshActivity() {
        markedDays = controller ? controller.calendarDaysWithOperations(shownYear, shownMonth + 1) : []
    }

    Connections {
        target: picker.controller
        function onChanged() {
            if (picker.opened)
                picker.refreshActivity()
        }
    }

    onAboutToShow: {
        const selected = selectedIso.split("-")
        setMonth(Number(selected[0]), Number(selected[1]) - 1)
    }

    background: Item {
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 3
            anchors.bottomMargin: -3
            radius: 16
            color: picker.tones.shadow
        }
        Rectangle {
            anchors.fill: parent
            radius: 16
            color: picker.tones.surface
            border.color: picker.tones.line
        }
    }

    component CalendarAction: Button {
        id: action
        padding: 7
        hoverEnabled: true
        contentItem: Label {
            text: action.text
            color: action.enabled ? picker.tones.text : picker.tones.muted
            opacity: action.enabled ? 1 : 0.6
            font.pixelSize: 13
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 9
            color: action.hovered ? picker.tones.hover : "transparent"
            border.color: action.activeFocus ? picker.tones.accent : "transparent"
        }
    }

    component YearStep: Rectangle {
        id: step
        required property string symbol
        width: 25
        color: "transparent"
        radius: 8
        Label {
            anchors.centerIn: parent
            text: step.symbol
            color: step.enabled ? picker.tones.text : picker.tones.muted
            opacity: step.enabled ? 1 : 0.50
            font.pixelSize: 15
        }
    }

    contentItem: ColumnLayout {
        spacing: 7

        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            CalendarAction {
                objectName: "calendarPreviousMonth"
                text: "‹"
                Accessible.name: qsTr("Предишен месец")
                enabled: picker.shownYear > 1 || picker.shownMonth > 0
                onClicked: picker.setMonth(picker.shownYear, picker.shownMonth - 1)
            }
            ComboBox {
                id: monthSelect
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                Accessible.name: qsTr("Месец")
                model: picker.shownYear === picker.latestYear ? picker.latestMonth + 1 : 12
                currentIndex: picker.shownMonth
                displayText: picker.months[picker.shownMonth]
                onActivated: index => picker.setMonth(picker.shownYear, index)
                delegate: ItemDelegate {
                    required property int index
                    width: monthSelect.width
                    text: picker.months[index]
                    highlighted: monthSelect.highlightedIndex === index
                }
                background: Rectangle {
                    radius: 9
                    color: monthSelect.down ? picker.tones.hover : picker.tones.surface
                    border.color: monthSelect.activeFocus ? picker.tones.accent : picker.tones.line
                }
            }
            SpinBox {
                id: yearSelect
                Layout.preferredWidth: 104
                Layout.preferredHeight: 34
                Accessible.name: qsTr("Година")
                editable: true
                from: 1
                to: picker.latestYear
                value: picker.shownYear
                textFromValue: value => String(value)
                onValueModified: picker.setMonth(value, picker.shownMonth)
                down.indicator: YearStep {
                    height: yearSelect.height
                    symbol: "−"
                    color: yearSelect.down.pressed ? picker.tones.hover : "transparent"
                }
                up.indicator: YearStep {
                    x: yearSelect.width - width
                    height: yearSelect.height
                    symbol: "+"
                    color: yearSelect.up.pressed ? picker.tones.hover : "transparent"
                }
                background: Rectangle {
                    radius: 9
                    color: picker.tones.surface
                    border.color: yearSelect.activeFocus ? picker.tones.accent : picker.tones.line
                }
            }
            CalendarAction {
                objectName: "calendarNextMonth"
                text: "›"
                Accessible.name: qsTr("Следващ месец")
                enabled: picker.shownYear < picker.latestYear || picker.shownMonth < picker.latestMonth
                onClicked: picker.setMonth(picker.shownYear, picker.shownMonth + 1)
            }
        }

        DayOfWeekRow {
            Layout.fillWidth: true
            Layout.preferredHeight: 22
            locale: calendar.locale
            padding: 0
            spacing: calendar.spacing
            delegate: Label {
                required property string shortName
                text: shortName
                color: picker.tones.muted
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        MonthGrid {
            id: calendar
            Layout.fillWidth: true
            Layout.preferredHeight: 206
            padding: 0
            spacing: 4
            locale: Qt.locale(picker.localeName)
            year: picker.shownYear
            month: picker.shownMonth

            delegate: Button {
                id: day
                required property var model
                readonly property string iso: String(model.year).padStart(4, "0") + "-" +
                                                  String(model.month + 1).padStart(2, "0") + "-" +
                                                  String(model.day).padStart(2, "0")
                readonly property bool picked: iso === picker.selectedIso
                readonly property bool today: iso === picker.todayIso
                readonly property bool hasOperations: picker.markedDays.includes(iso)
                objectName: "calendar_day_" + iso
                text: String(model.day)
                Accessible.name: calendar.locale.toString(model.date, "d MMMM yyyy")
                Accessible.selected: picked
                Accessible.description: hasOperations ? qsTr("Има записани операции") : ""
                enabled: iso >= picker.earliestIso && iso <= picker.todayIso
                hoverEnabled: true
                padding: 0
                onClicked: picker.dateChosen(iso)
                contentItem: Label {
                    text: day.text
                    color: day.picked ? picker.tones.onAccent :
                           (day.enabled && day.model.month === calendar.month ? picker.tones.text : picker.tones.muted)
                    bottomPadding: day.hasOperations ? 4 : 0
                    opacity: day.enabled ? 1 : 0.48
                    font.pixelSize: 13
                    font.weight: day.picked || day.today ? Font.DemiBold : Font.Normal
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 9
                    color: day.picked ? picker.tones.selection : (day.hovered ? picker.tones.hover : "transparent")
                    border.color: day.activeFocus || (day.today && !day.picked) ?
                                  picker.tones.accent : "transparent"
                }
                Rectangle {
                    objectName: "calendarActivityDot_" + day.iso
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 3
                    visible: day.hasOperations
                    width: 5
                    height: 5
                    radius: 2.5
                    color: day.picked ? picker.tones.onAccent : picker.tones.accent
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: picker.tones.line
        }
        CalendarAction {
            objectName: "calendarTodayButton"
            Layout.alignment: Qt.AlignRight
            text: qsTr("Днес")
            onClicked: picker.dateChosen(picker.todayIso)
        }
    }
}
