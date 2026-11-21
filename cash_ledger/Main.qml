import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    required property QtObject controller
    visible: true
    title: "Касов дневник"
    width: Math.max(800, Math.min(1400, Screen.desktopAvailableWidth - 28))
    height: Math.max(540, Math.min(760, Screen.desktopAvailableHeight - 60))
    minimumWidth: 760
    minimumHeight: 520
    color: work

    readonly property bool dark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color ink: dark ? "#e6eeed" : "#192426"
    readonly property color muted: dark ? "#a7b9b8" : "#516265"
    readonly property color work: dark ? "#141e20" : "#f5f8f8"
    readonly property color paper: dark ? "#1b2527" : "#ffffff"
    readonly property color sidebar: dark ? "#192525" : "#edf3f3"
    readonly property color alternate: dark ? "#202d2e" : "#f8fafa"
    readonly property color headerSurface: dark ? "#263437" : "#f0f5f5"
    readonly property color line: dark ? "#354847" : "#d9e2e2"
    readonly property color thinLine: dark ? "#38494a" : "#e3ebeb"
    readonly property color accent: dark ? "#a1dfcc" : "#175d52"
    readonly property color accentText: dark ? "#102b26" : "#ffffff"
    readonly property color cashBackdrop: dark ? "#22483f" : "#19483f"
    readonly property color positive: dark ? "#a6e1c4" : "#13614d"
    readonly property color positiveBg: dark ? "#243d35" : "#e6f2ee"
    readonly property color negative: dark ? "#f5bb96" : "#854a26"
    readonly property color negativeBg: dark ? "#41312b" : "#faf0e8"
    readonly property color warningColor: dark ? "#f4a59b" : "#a5342c"
    readonly property color priceColor: dark ? "#97acab" : "#627476"
    readonly property real baseWidth: controller.widths.reduce((total, width) => total + width, 0)
    readonly property var groups: [
        {label: "Договори и продажби", first: 0, count: 8},
        {label: "Приход / разход", first: 8, count: 2},
        {label: "Залози", first: 10, count: 2},
        {label: "Покупки", first: 12, count: 2}
    ]
    readonly property var enterFields: [3, 4, 5, 6, 7, 8, 9, 11, 12, 13]
    property string weightProblem: ""
    property string statusMessage: ""
    property bool statusError: false

    function cellWidth(index) {
        return controller.widths[index] + Math.max(0, tableScroll.width - baseWidth) / controller.columns.length
    }
    function groupWidth(group) {
        let width = 0
        for (let column = group.first; column < group.first + group.count; column++)
            width += cellWidth(column)
        return width
    }
    function draft() {
        const values = {}
        for (let index = 0; index < entries.count; index++) {
            const item = entries.itemAt(index)
            if (item)
                values[item.modelData.key] = item.editor.text
        }
        return values
    }
    function submit(sourceIndex) {
        if (weightProblem) {
            statusMessage = ""
            return
        }
        const result = controller.saveDraft(draft())
        statusMessage = result.message
        statusError = !result.ok
        if (!result.ok)
            return

        for (let index = 0; index < entries.count; index++) {
            const item = entries.itemAt(index)
            if (result.cleared.includes(item.modelData.key))
                item.editor.text = item.modelData.key === "pledge" ? result.pledge : ""
        }
        weightProblem = ""
        operations.positionViewAtEnd()
        if (sourceIndex === 3)
            entries.itemAt(1).editor.forceActiveFocus()
        else if (sourceIndex >= 4 && sourceIndex <= 7)
            entries.itemAt(0).editor.forceActiveFocus()
    }
    function showStatus(message) {
        statusMessage = message
        statusError = message.length > 0
    }
    function ensureFieldVisible(left, width) {
        if (left < tableScroll.contentX)
            tableScroll.contentX = left
        else if (left + width > tableScroll.contentX + tableScroll.width)
            tableScroll.contentX = left + width - tableScroll.width
    }

    component LedgerText: Label {
        color: win.ink
        font.pixelSize: 13
        verticalAlignment: Text.AlignVCenter
    }

    component LedgerButton: Button {
        id: control
        property bool primary: false
        padding: 8
        leftPadding: 11
        rightPadding: 11
        font.pixelSize: 13
        hoverEnabled: true
        contentItem: LedgerText {
            text: control.text
            font.weight: control.primary ? Font.DemiBold : Font.Normal
            color: control.primary ? win.accentText : win.ink
            horizontalAlignment: Text.AlignHCenter
        }
        background: Rectangle {
            radius: 5
            color: control.primary ? win.accent :
                   (control.hovered ? win.positiveBg : win.paper)
            opacity: control.enabled ? 1 : 0.45
            border.color: control.activeFocus ? win.accent : win.line
        }
    }

    component ColumnCell: Rectangle {
        id: cell
        property bool divided: false
        property bool groupDivider: false
        Rectangle {
            visible: cell.divided
            width: 1
            height: parent.height
            color: cell.groupDivider ? win.line : win.thinLine
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: win.thinLine
        }
    }

    header: Rectangle {
        height: 48
        color: win.paper
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 9
            Rectangle {
                implicitWidth: 24
                implicitHeight: 24
                color: win.positiveBg
                radius: 5
                LedgerText { anchors.centerIn: parent; text: "≡"; color: win.accent; font.pixelSize: 17 }
            }
            LedgerText { text: "Касов дневник"; font.pixelSize: 15; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: win.line }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 178
            Layout.fillHeight: true
            color: win.sidebar
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: win.line }

            ColumnLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 12
                spacing: 7

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 72
                    color: win.cashBackdrop
                    radius: 7
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 3
                        LedgerText { text: "Каса към датата"; color: "#c4ded7"; font.pixelSize: 11 }
                        LedgerText {
                            Layout.fillWidth: true
                            text: win.controller.summary.cash
                            color: "#f4fbf9"
                            font.pixelSize: 23
                            font.weight: Font.Bold
                            fontSizeMode: Text.HorizontalFit
                            minimumPixelSize: 11
                        }
                    }
                }

                Repeater {
                    model: [
                        {label: "Печалба", key: "profit"}, {label: "Откуп", key: "redemption"},
                        {label: "Залози", key: "pledges"}, {label: "Лихви", key: "interest"}
                    ]
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 29
                        LedgerText { text: parent.modelData.label; color: win.muted; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        LedgerText {
                            Layout.fillWidth: true
                            text: win.controller.summary[parent.modelData.key]
                            horizontalAlignment: Text.AlignRight
                            fontSizeMode: Text.HorizontalFit
                            minimumPixelSize: 10
                            font.weight: Font.DemiBold
                        }
                    }
                }

                LedgerButton {
                    Layout.fillWidth: true
                    text: "Начална каса"
                    onClicked: {
                        openingEdit.text = win.controller.openingText
                        openingError.text = ""
                        openingDialog.open()
                        openingEdit.selectAll()
                        openingEdit.forceActiveFocus()
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 13
            spacing: 9

            RowLayout {
                Layout.fillWidth: true
                LedgerText { text: "Операции"; font.pixelSize: 21; font.weight: Font.DemiBold }
                Item { Layout.fillWidth: true }
                LedgerButton { text: "Днес"; visible: !win.controller.isToday; onClicked: win.showStatus(win.controller.goToday()) }
                LedgerButton { text: "‹"; Accessible.name: "Предишен ден"; onClicked: win.showStatus(win.controller.shiftDay(-1)) }
                LedgerButton {
                    text: win.controller.dateText
                    Accessible.name: "Избери дата"
                    onClicked: {
                        dateEdit.text = win.controller.dateIso
                        dateError.text = ""
                        dateDialog.open()
                        dateEdit.selectAll()
                        dateEdit.forceActiveFocus()
                    }
                }
                LedgerButton {
                    text: "›"
                    enabled: !win.controller.isToday
                    Accessible.name: "Следващ ден"
                    onClicked: win.showStatus(win.controller.shiftDay(1))
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: win.paper
                border.color: win.line
                clip: true

                Flickable {
                    id: tableScroll
                    anchors.fill: parent
                    anchors.margins: 1
                    clip: true
                    contentWidth: Math.max(width, win.baseWidth)
                    contentHeight: height
                    flickableDirection: Flickable.HorizontalFlick
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.horizontal: ScrollBar {
                        policy: tableScroll.contentWidth > tableScroll.width ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                    }

                    Column {
                        width: tableScroll.contentWidth

                        Row {
                            id: groupHeader
                            height: 28
                            Repeater {
                                model: win.groups
                                delegate: ColumnCell {
                                    required property var modelData
                                    required property int index
                                    width: win.groupWidth(modelData)
                                    height: groupHeader.height
                                    color: win.headerSurface
                                    divided: index !== 0
                                    groupDivider: true
                                    LedgerText { x: 8; height: parent.height; text: parent.modelData.label; color: win.muted; font.weight: Font.DemiBold }
                                }
                            }
                        }

                        Row {
                            id: columnHeader
                            height: 31
                            Repeater {
                                model: win.controller.columns
                                delegate: ColumnCell {
                                    id: heading
                                    required property var modelData
                                    required property int index
                                    width: win.cellWidth(index)
                                    height: columnHeader.height
                                    color: modelData.side === "+" ? win.positiveBg : (modelData.side === "−" ? win.negativeBg : win.alternate)
                                    divided: index !== 0
                                    groupDivider: modelData.split
                                    LedgerText {
                                        anchors.fill: parent
                                        anchors.margins: 7
                                        text: heading.modelData.title + (heading.modelData.side ? "  " + heading.modelData.side : "")
                                        horizontalAlignment: heading.modelData.number ? Text.AlignRight : Text.AlignLeft
                                        color: heading.modelData.side === "+" ? win.positive : (heading.modelData.side === "−" ? win.negative : win.ink)
                                        font.weight: Font.DemiBold
                                    }
                                    HoverHandler { id: headingHover }
                                    ToolTip.visible: headingHover.hovered
                                    ToolTip.delay: 400
                                    ToolTip.text: modelData.label
                                }
                            }
                        }

                        ListView {
                            id: operations
                            width: tableScroll.contentWidth
                            height: Math.max(0, tableScroll.height - groupHeader.height - columnHeader.height - subtotals.height - entryRow.height - 10)
                            model: win.controller.rows
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: Row {
                                id: operation
                                required property int index
                                required property var cells
                                height: cells.some(cell => cell.note && cell.price) ? 65 :
                                        (cells.some(cell => cell.note || cell.price) ? 49 : 34)
                                Repeater {
                                    model: win.controller.columns
                                    delegate: ColumnCell {
                                        id: bodyCell
                                        required property int index
                                        required property var modelData
                                        readonly property var value: operation.cells[index]
                                        width: win.cellWidth(index)
                                        height: operation.height
                                        color: operation.index % 2 ? win.alternate : win.paper
                                        divided: index !== 0
                                        groupDivider: modelData.split

                                        Column {
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 8
                                            LedgerText {
                                                width: parent.width
                                                text: bodyCell.value.text
                                                horizontalAlignment: bodyCell.modelData.number ? Text.AlignRight : Text.AlignLeft
                                                font.pixelSize: bodyCell.modelData.weight ? 15 : 13
                                                font.weight: bodyCell.modelData.weight ? Font.Bold : Font.Normal
                                            }
                                            LedgerText {
                                                width: parent.width
                                                visible: text !== ""
                                                text: bodyCell.value.price
                                                color: win.priceColor
                                                font.pixelSize: 11
                                                horizontalAlignment: Text.AlignRight
                                                HoverHandler { id: priceHover }
                                                ToolTip.visible: priceHover.hovered
                                                ToolTip.delay: 400
                                                ToolTip.text: bodyCell.value.calculation
                                            }
                                            Button {
                                                id: noteButton
                                                width: parent.width
                                                height: visible ? 15 : 0
                                                visible: text !== ""
                                                text: bodyCell.value.note
                                                padding: 0
                                                hoverEnabled: true
                                                background: null
                                                contentItem: LedgerText {
                                                    text: noteButton.text
                                                    color: win.accent
                                                    font.pixelSize: 11
                                                    font.underline: true
                                                    elide: Text.ElideRight
                                                    horizontalAlignment: bodyCell.modelData.number ? Text.AlignRight : Text.AlignLeft
                                                }
                                                ToolTip.visible: hovered
                                                ToolTip.delay: 400
                                                ToolTip.text: text
                                                onClicked: {
                                                    noteDialog.title = bodyCell.modelData.label
                                                    noteText.text = text
                                                    noteDialog.open()
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Row {
                            id: subtotals
                            height: 31
                            Repeater {
                                model: win.controller.columns
                                delegate: ColumnCell {
                                    required property int index
                                    required property var modelData
                                    width: win.cellWidth(index)
                                    height: subtotals.height
                                    color: win.headerSurface
                                    divided: index !== 0
                                    groupDivider: modelData.split
                                    LedgerText {
                                        anchors.fill: parent
                                        anchors.margins: 7
                                        text: parent.index === 0 ? "Общо" : win.controller.totals[parent.index]
                                        horizontalAlignment: parent.modelData.number ? Text.AlignRight : Text.AlignLeft
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }
                        }

                        Row {
                            id: entryRow
                            height: 40
                            Repeater {
                                id: entries
                                model: win.controller.columns
                                delegate: ColumnCell {
                                    id: inputCell
                                    required property int index
                                    required property var modelData
                                    property alias editor: draftField
                                    width: win.cellWidth(index)
                                    height: entryRow.height
                                    color: win.sidebar
                                    divided: index !== 0
                                    groupDivider: modelData.split

                                    TextField {
                                        id: draftField
                                        objectName: "entry_" + inputCell.modelData.key
                                        anchors.fill: parent
                                        anchors.margins: 4
                                        placeholderText: inputCell.modelData.title
                                        Accessible.name: inputCell.modelData.label
                                        Accessible.description: conflict ? win.weightProblem : ""
                                        horizontalAlignment: inputCell.modelData.number ? Text.AlignRight : Text.AlignLeft
                                        color: win.ink
                                        placeholderTextColor: win.muted
                                        selectedTextColor: win.accentText
                                        selectionColor: win.accent
                                        selectByMouse: true
                                        font.pixelSize: 13
                                        readonly property bool conflict: inputCell.modelData.weight && text.trim() !== "" && win.weightProblem !== ""
                                        background: Rectangle {
                                            color: win.paper
                                            border.color: draftField.conflict ? win.warningColor : (draftField.activeFocus ? win.accent : win.line)
                                            border.width: draftField.activeFocus || draftField.conflict ? 2 : 1
                                            radius: 4
                                        }
                                        onTextChanged: {
                                            if (inputCell.modelData.weight)
                                                win.weightProblem = win.controller.draftWeightError(win.draft())
                                        }
                                        onActiveFocusChanged: {
                                            if (activeFocus)
                                                win.ensureFieldVisible(inputCell.x, inputCell.width)
                                        }
                                        onAccepted: {
                                            if (win.enterFields.includes(inputCell.index))
                                                win.submit(inputCell.index)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                LedgerText {
                    anchors.centerIn: parent
                    visible: operations.count === 0
                    text: "Добави първата операция от полетата долу."
                    color: win.muted
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 9
                LedgerText {
                    text: win.controller.isToday ? "Бързо въвеждане" : "Бързо въвеждане за днес"
                    font.weight: Font.DemiBold
                }
                LedgerText {
                    objectName: "weightWarning"
                    Layout.fillWidth: true
                    text: win.weightProblem || win.statusMessage
                    color: win.weightProblem || win.statusError ? win.warningColor : win.muted
                    wrapMode: Text.WordWrap
                    Accessible.role: Accessible.StaticText
                }
                LedgerButton { text: "Запиши"; primary: true; onClicked: win.submit(-1) }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 13
                Item { Layout.fillWidth: true }
                LedgerText { text: "Постъпления"; color: win.muted; font.pixelSize: 11 }
                LedgerText { text: win.controller.summary.incoming; color: win.positive; font.weight: Font.DemiBold }
                LedgerText { text: "Плащания"; color: win.muted; font.pixelSize: 11 }
                LedgerText { text: win.controller.summary.outgoing; color: win.negative; font.weight: Font.DemiBold }
                LedgerText { text: "Движение за деня"; color: win.muted; font.pixelSize: 11 }
                LedgerText { text: win.controller.summary.net; font.weight: Font.DemiBold }
            }
        }
    }

    Dialog {
        id: openingDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        title: "Начална каса"
        function saveOpening() {
            openingError.text = win.controller.setOpening(openingEdit.text)
            if (!openingError.text)
                close()
        }
        contentItem: ColumnLayout {
            spacing: 9
            LedgerText { text: "Салдо преди първия запис (€)" }
            TextField { id: openingEdit; Layout.fillWidth: true; onAccepted: openingDialog.saveOpening() }
            LedgerText { id: openingError; Layout.fillWidth: true; visible: text !== ""; color: win.warningColor }
            RowLayout {
                Item { Layout.fillWidth: true }
                LedgerButton { text: "Отказ"; onClicked: openingDialog.close() }
                LedgerButton { text: "Запиши"; primary: true; onClicked: openingDialog.saveOpening() }
            }
        }
    }

    Dialog {
        id: dateDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        title: "Избор на дата"
        function selectDate() {
            dateError.text = win.controller.goTo(dateEdit.text.trim())
            if (!dateError.text) {
                win.showStatus("")
                close()
            }
        }
        contentItem: ColumnLayout {
            spacing: 9
            TextField { id: dateEdit; Layout.fillWidth: true; placeholderText: "ГГГГ-ММ-ДД"; onAccepted: dateDialog.selectDate() }
            LedgerText { id: dateError; Layout.fillWidth: true; visible: text !== ""; color: win.warningColor }
            RowLayout {
                Item { Layout.fillWidth: true }
                LedgerButton { text: "Отказ"; onClicked: dateDialog.close() }
                LedgerButton { text: "Покажи"; primary: true; onClicked: dateDialog.selectDate() }
            }
        }
    }

    Dialog {
        id: noteDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        width: Math.min(440, win.width - 40)
        standardButtons: Dialog.Close
        contentItem: ScrollView {
            implicitHeight: Math.max(54, Math.min(noteText.implicitHeight + 8, win.height / 2))
            TextArea {
                id: noteText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: win.ink
            }
        }
    }
}
