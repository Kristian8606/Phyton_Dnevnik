import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RoundedDialog {
    id: search
    required property QtObject controller
    required property var tones
    signal matchChosen(var match)
    property var matches: []
    property string message: ""
    title: qsTr("Търсене в дневника")
    modal: true
    width: 525
    padding: 14
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    palette.window: tones.surface
    palette.base: tones.surface
    palette.mid: tones.line
    palette.text: tones.text
    palette.highlight: tones.selection
    palette.highlightedText: tones.onAccent

    onOpened: {
        query.forceActiveFocus()
        query.selectAll()
        runSearch()
    }
    onClosed: pending.stop()

    function runSearch() {
        pending.stop()
        if (!query.text.trim()) {
            matches = []
            message = ""
            return
        }
        const result = controller.findNumber(query.text)
        matches = result.ok ? result.matches : []
        message = !result.ok ? result.message
                            : (result.truncated ? qsTr("Уточни номера за по-тесен резултат.")
                                                : (matches.length === 0 ? qsTr("Няма съвпадения.") : ""))
        results.positionViewAtBeginning()
    }

    Timer {
        id: pending
        interval: 160
        onTriggered: search.runSearch()
    }

    contentItem: ColumnLayout {
        spacing: 10
        RoundedField {
            id: query
            objectName: "findNumberInput"
            Layout.fillWidth: true
            Layout.preferredHeight: 37
            placeholderText: qsTr("Номер на договор, етикет или залог")
            Accessible.name: placeholderText
            selectByMouse: true
            color: search.tones.text
            placeholderTextColor: search.tones.muted
            focusBorder: search.tones.accent
            onTextChanged: pending.restart()
            onAccepted: search.runSearch()
        }

        ListView {
            id: results
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(264, count * 53)
            clip: true
            spacing: 4
            model: search.matches
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Button {
                id: resultButton
                required property int index
                required property var modelData
                objectName: "findNumberResult_" + index
                width: results.width - 8
                height: 49
                hoverEnabled: true
                padding: 8
                Accessible.name: modelData.label + " " + modelData.number + ", " + modelData.date
                onClicked: search.matchChosen(modelData)
                contentItem: RowLayout {
                    spacing: 10
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            text: resultButton.modelData.number
                            color: search.tones.text
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        Label {
                            text: resultButton.modelData.label + "  ·  " + resultButton.modelData.date
                            color: search.tones.muted
                            font.pixelSize: 11
                        }
                    }
                    Label {
                        Layout.fillWidth: false
                        Layout.alignment: Qt.AlignRight
                        text: resultButton.modelData.amount
                        color: search.tones.text
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                }
                background: Rectangle {
                    radius: 10
                    color: resultButton.hovered || resultButton.activeFocus ? search.tones.hover : search.tones.alternate
                    border.color: resultButton.activeFocus ? search.tones.accent : "transparent"
                }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: search.message
            color: search.tones.muted
            wrapMode: Text.WordWrap
        }
    }
}
