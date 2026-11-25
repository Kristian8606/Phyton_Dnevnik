import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: view
    required property var report
    required property var tones
    required property bool administrator
    property string feedback: ""
    signal closeRequested()
    spacing: 10

    readonly property var columns: [
        {key: "date", label: "Дата", width: 130},
        {key: "profit", label: "Печалба (€)", width: 109},
        {key: "sold_gold", label: "Прод. зл. (г)", width: 106},
        {key: "sold_new_gold", label: "Прод. ново зл. (г)", width: 127},
        {key: "sold_silver", label: "Прод. ср. (г)", width: 106},
        {key: "sold_new_silver", label: "Прод. ново ср. (г)", width: 128},
        {key: "income", label: "Приход (€)", width: 110},
        {key: "cost", label: "Разход (€)", width: 110},
        {key: "bought_gold", label: "Куп. зл. (€)", width: 110},
        {key: "bought_silver", label: "Куп. ср. (€)", width: 110},
        {key: "closing", label: "Каса в края (€)", width: 123}
    ]
    readonly property real tableWidth: columns.reduce((total, column) => total + column.width, 0)

    component Cell: Rectangle {
        id: cell
        required property string value
        required property bool numeric
        property bool heading: false

        height: heading ? 38 : 45
        color: heading ? view.tones.header : "transparent"

        Rectangle {
            anchors.right: parent.right
            height: parent.height
            width: 1
            color: view.tones.line
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: view.tones.line
        }
        Label {
            anchors.fill: parent
            anchors.leftMargin: 9
            anchors.rightMargin: 9
            text: cell.value
            color: view.tones.ink
            font.pixelSize: 13
            font.weight: cell.heading ? Font.DemiBold : Font.Normal
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 10
            horizontalAlignment: cell.numeric ? Text.AlignRight : Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }
    }

    component RevisionRow: Row {
        id: line
        required property var values
        property bool current: false

        Repeater {
            model: view.columns
            Cell {
                required property var modelData
                objectName: line.current ? "revision_" + modelData.key : ""
                width: modelData.width + (table.contentWidth - view.tableWidth) / view.columns.length
                value: line.values[modelData.key] || ""
                numeric: modelData.key !== "date"
                color: line.current ? view.tones.alternate : "transparent"
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            text: "Ревизии"
            color: view.tones.ink
            font.pixelSize: 23
            font.weight: Font.DemiBold
        }
        Button {
            id: closeButton
            objectName: "closeRevisionButton"
            visible: view.administrator
            enabled: Boolean(view.report.ok) && view.report.operationCount > 0
            text: "Нов период"
            padding: 9
            onClicked: view.closeRequested()
            contentItem: Label {
                text: closeButton.text
                color: closeButton.enabled ? view.tones.accentText : view.tones.ink
                font.weight: Font.DemiBold
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 7
                color: closeButton.enabled ? view.tones.accent : view.tones.header
                border.color: closeButton.activeFocus ? view.tones.ink : "transparent"
            }
        }
    }

    Label {
        Layout.fillWidth: true
        visible: text.length > 0
        text: view.report.message || view.feedback
        color: view.tones.ink
        wrapMode: Text.WordWrap
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        color: view.tones.paper
        border.color: view.tones.line

        Flickable {
            id: table
            anchors.fill: parent
            anchors.margins: 1
            clip: true
            contentWidth: Math.max(width, view.tableWidth)
            contentHeight: height
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.HorizontalFlick
            ScrollBar.horizontal: ScrollBar {}

            ColumnLayout {
                width: table.contentWidth
                height: table.height
                spacing: 0

                Row {
                    Repeater {
                        model: view.columns
                        Cell {
                            required property var modelData
                            width: modelData.width + (table.contentWidth - view.tableWidth) / view.columns.length
                            heading: true
                            value: modelData.label
                            numeric: modelData.key !== "date"
                        }
                    }
                }
                Label {
                    Layout.leftMargin: 9
                    Layout.topMargin: 7
                    Layout.bottomMargin: 5
                    visible: Boolean(view.report.ok)
                    text: "Текущ период"
                    color: view.tones.ink
                    font.weight: Font.DemiBold
                }
                RevisionRow {
                    visible: Boolean(view.report.ok)
                    current: true
                    values: view.report.row || ({})
                }
                Label {
                    Layout.leftMargin: 9
                    Layout.topMargin: 9
                    Layout.bottomMargin: 5
                    visible: Boolean(view.report.history && view.report.history.length)
                    text: "Приключени ревизии"
                    color: view.tones.ink
                    font.weight: Font.DemiBold
                }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: view.report.history || []
                    delegate: RevisionRow {
                        required property var modelData
                        values: modelData
                    }
                    ScrollBar.vertical: ScrollBar {}
                }
            }
        }
    }
}
