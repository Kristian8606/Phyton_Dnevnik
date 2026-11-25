import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: view
    required property var report
    required property var tones
    spacing: 10

    readonly property var columns: [
        {key: "date", label: "Дата", width: 100},
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

    Label {
        text: "Текущ период"
        color: view.tones.ink
        font.pixelSize: 23
        font.weight: Font.DemiBold
    }

    Label {
        Layout.fillWidth: true
        visible: view.report.message !== undefined
        text: view.report.message || ""
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

            Column {
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
                Row {
                    visible: Boolean(view.report.ok)
                    Repeater {
                        model: view.columns
                        Cell {
                            required property var modelData
                            objectName: "revision_" + modelData.key
                            width: modelData.width + (table.contentWidth - view.tableWidth) / view.columns.length
                            value: view.report.ok ? view.report.row[modelData.key] : ""
                            numeric: modelData.key !== "date"
                        }
                    }
                }
            }
        }
    }
}
