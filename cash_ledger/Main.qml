import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

ApplicationWindow {
    id: win
    required property QtObject controller
    required property QtObject preferences
    required property QtObject updates
    visible: true
    property bool testMode: false
    title: testMode ? "Дневник · Тестови дни" : "Дневник"
    width: Math.max(800, Math.min(1400, Screen.desktopAvailableWidth - 28))
    height: Math.max(540, Math.min(760, Screen.desktopAvailableHeight - 60))
    minimumWidth: 760
    minimumHeight: 520
    color: work

    readonly property bool dark: preferences.theme === "dark"
                                || (preferences.theme === "system"
                                    && Application.styleHints.colorScheme === Qt.ColorScheme.Dark)

    palette.window: win.paper
    palette.windowText: win.ink
    palette.base: win.paper
    palette.text: win.ink
    palette.button: win.paper
    palette.buttonText: win.ink
    palette.highlight: win.accent
    palette.highlightedText: win.accentText
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
    readonly property color balancePane: dark ? "#102626" : "#103736"
    readonly property color balanceLine: "#4c8a81"
    readonly property color balanceInk: "#f3fbf8"
    readonly property color balanceMuted: "#b6d9d3"
    readonly property color matchSurface: dark ? "#244954" : "#e0f2fa"
    readonly property color matchEdge: dark ? "#83c8dd" : "#237c95"
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
    property var searchSelection: null

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
    function showResult(result) {
        statusMessage = result.message
        statusError = !result.ok
    }
    function openOperation(block, operationId, field) {
        const record = controller.openEdit(block, operationId)
        if (!record.ok) {
            showResult(record)
            return
        }
        editDialog.title = record.title
        editDialog.operationDate = record.date
        editDialog.fields = record.fields
        editDialog.initialField = field
        editDialog.errorText = ""
        editDialog.weightProblem = ""
        editDialog.open()
    }
    function ensureFieldVisible(left, width) {
        if (left < tableScroll.contentX)
            tableScroll.contentX = left
        else if (left + width > tableScroll.contentX + tableScroll.width)
            tableScroll.contentX = left + width - tableScroll.width
    }
    function openMatch(match) {
        const result = controller.goToSearchMatch(match.iso, match.block, match.id)
        if (!result.ok) {
            numberSearch.message = result.message
            return
        }
        searchSelection = match
        showStatus("")
        numberSearch.close()
        Qt.callLater(() => {
            operations.positionViewAtIndex(result.row, ListView.Contain)
            ensureFieldVisible(groupWidth({ first: 0, count: result.column }), cellWidth(result.column))
        })
    }

    Shortcut { sequences: [StandardKey.Find]; onActivated: numberSearch.open() }

    component LedgerText: Label {
        color: win.ink
        font.pixelSize: 13
        verticalAlignment: Text.AlignVCenter
    }

    component ReportAmount: LedgerText {
        Layout.fillWidth: true
        Layout.preferredWidth: 120
        horizontalAlignment: Text.AlignRight
    }

    component LedgerButton: Button {
        id: control
        property bool primary: false
        property bool quiet: false
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
            radius: 7
            color: control.primary ? (control.down ? Qt.darker(win.accent, 1.1) : win.accent) :
                   (control.hovered || control.highlighted ? win.positiveBg : (control.quiet ? "transparent" : win.paper))
            opacity: control.enabled ? 1 : 0.45
            border.color: control.activeFocus ? win.accent : (control.quiet ? "transparent" : win.line)
        }
    }

    component ThemeMenuItem: MenuItem {
        required property string mode
        objectName: "theme_" + mode
        checkable: true
        checked: win.preferences.theme === mode
        ButtonGroup.group: themeGroup
        onTriggered: win.showStatus(win.preferences.setTheme(mode))
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
        height: 54
        color: win.paper
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 9
            Rectangle {
                implicitWidth: 28
                implicitHeight: 28
                color: win.positiveBg
                radius: 8
                LedgerText { anchors.centerIn: parent; text: "≡"; color: win.accent; font.pixelSize: 17 }
            }
            LedgerText { text: "Дневник"; font.pixelSize: 16; font.weight: Font.DemiBold }
            LedgerText {
                visible: win.testMode
                text: "Тестова база"
                color: win.accent
                font.weight: Font.DemiBold
            }
            Item { Layout.fillWidth: true }
            LedgerButton {
                objectName: "cashReportButton"
                text: "Каса по дни"
                onClicked: {
                    const report = win.controller.cashReport()
                    if (report.ok) {
                        cashReportDialog.days = report.days
                        cashReportDialog.open()
                    } else {
                        win.showResult(report)
                    }
                }
            }
            LedgerButton {
                id: settingsButton
                objectName: "settingsButton"
                text: "Настройки ▾"
                Accessible.name: "Настройки"
                highlighted: settingsMenu.opened
                onClicked: settingsMenu.open()

                Menu {
                    id: settingsMenu
                    objectName: "settingsMenu"
                    width: 192
                    x: settingsButton.width - width
                    y: settingsButton.height + 4

                    Menu {
                        objectName: "themeMenu"
                        title: "Тема"
                        width: 172
                        ButtonGroup { id: themeGroup }
                        ThemeMenuItem { mode: "system"; text: "Като системата" }
                        ThemeMenuItem { mode: "light"; text: "Светла" }
                        ThemeMenuItem { mode: "dark"; text: "Тъмна" }
                    }
                    MenuItem {
                        objectName: "updatesMenuItem"
                        text: win.updates.supported ? "Обновяване…" : "За „Дневник“…"
                        onTriggered: updatesDialog.open()
                    }
                }
            }
            LedgerButton {
                id: archiveButton
                text: "Архив"
                onClicked: archiveMenu.open()
                Menu {
                    id: archiveMenu
                    y: archiveButton.height
                    MenuItem { text: "Създай архив…"; onTriggered: backupPicker.open() }
                    MenuItem { text: "Възстанови от архив…"; onTriggered: restorePicker.open() }
                }
            }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: win.line }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 214
            Layout.fillHeight: true
            color: win.balancePane

            ColumnLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 15
                spacing: 9

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    LedgerButton {
                        id: findNumberButton
                        objectName: "findNumberButton"
                        Layout.fillWidth: true
                        text: "Търси"
                        Accessible.name: "Търси по номер"
                        onClicked: numberSearch.open()
                        contentItem: RowLayout {
                            spacing: 6
                            Item { Layout.fillWidth: true }
                            Item {
                                Layout.preferredWidth: 12
                                Layout.preferredHeight: 12
                                Rectangle { width: 8; height: 8; radius: 4; color: "transparent"; border.color: win.accent }
                                Rectangle { x: 6; y: 8; width: 6; height: 1; rotation: 45; color: win.accent }
                            }
                            LedgerText { text: findNumberButton.text }
                            Item { Layout.fillWidth: true }
                        }
                    }
                    LedgerButton { text: "Днес"; visible: !win.controller.isToday; onClicked: win.showStatus(win.controller.goToday()) }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: dateStrip.implicitHeight + 6
                    radius: 10
                    color: win.paper
                    border.color: win.line

                    RowLayout {
                        id: dateStrip
                        anchors.fill: parent
                        anchors.margins: 3
                        spacing: 2
                        LedgerButton {
                            text: "‹"
                            leftPadding: 7
                            rightPadding: 7
                            quiet: true
                            Accessible.name: "Предишен ден"
                            onClicked: win.showStatus(win.controller.shiftDay(-1))
                        }
                        LedgerButton {
                            id: dateButton
                            objectName: "datePickerButton"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            leftPadding: 3
                            rightPadding: 3
                            text: win.controller.dateText
                            quiet: true
                            highlighted: datePicker.opened
                            Accessible.name: "Избери дата, " + text
                            onClicked: datePicker.opened ? datePicker.close() : datePicker.open()
                            contentItem: RowLayout {
                                spacing: 4
                                Item {
                                    Layout.preferredWidth: 13
                                    Layout.preferredHeight: 13
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.topMargin: 2
                                        radius: 2
                                        color: "transparent"
                                        border.color: win.accent
                                    }
                                    Rectangle { x: 1; y: 5; width: 11; height: 1; color: win.accent }
                                    Rectangle { x: 3; width: 1; height: 4; color: win.accent }
                                    Rectangle { x: 9; width: 1; height: 4; color: win.accent }
                                }
                                LedgerText {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: dateButton.text
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    fontSizeMode: Text.HorizontalFit
                                    minimumPixelSize: 10
                                }
                            }
                            CalendarPicker {
                                id: datePicker
                                parent: dateButton
                                selectedIso: win.controller.dateIso
                                todayIso: win.controller.todayIso
                                tones: ({
                                    surface: win.paper, text: win.ink, muted: win.muted, line: win.line,
                                    accent: win.accent, onAccent: win.accentText, hover: win.positiveBg,
                                    shadow: win.dark ? "#55000000" : "#20192426"
                                })
                                onDateChosen: iso => {
                                    const problem = win.controller.goTo(iso)
                                    win.showStatus(problem)
                                    if (!problem) {
                                        close()
                                        dateButton.forceActiveFocus()
                                    }
                                }
                            }
                        }
                        LedgerButton {
                            text: "›"
                            leftPadding: 7
                            rightPadding: 7
                            quiet: true
                            enabled: !win.controller.isToday
                            Accessible.name: "Следващ ден"
                            onClicked: win.showStatus(win.controller.shiftDay(1))
                        }
                    }
                }

                Rectangle {
                    objectName: "balanceCard"
                    Layout.fillWidth: true
                    implicitHeight: 88
                    radius: 11
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#245e55" }
                        GradientStop { position: 1; color: win.cashBackdrop }
                    }
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 4
                        LedgerText { text: "Каса към датата"; color: win.balanceMuted; font.pixelSize: 12 }
                        LedgerText {
                            Layout.fillWidth: true
                            text: win.controller.summary.cash
                            color: win.balanceInk
                            font.pixelSize: 27
                            font.weight: Font.Bold
                            fontSizeMode: Text.HorizontalFit
                            minimumPixelSize: 11
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    LedgerText { text: "Пренос от предния ден"; color: win.balanceMuted; font.pixelSize: 11 }
                    LedgerText {
                        objectName: "carriedCash"
                        Layout.fillWidth: true
                        text: win.controller.summary.carried
                        color: win.balanceInk
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        fontSizeMode: Text.HorizontalFit
                        minimumPixelSize: 11
                    }
                }

                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: win.balanceLine; opacity: 0.55 }

                Repeater {
                    model: [
                        {label: "Печалба", key: "profit"}, {label: "Откуп", key: "redemption"},
                        {label: "Залози", key: "pledges"}, {label: "Лихви", key: "interest"}
                    ]
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 29
                        LedgerText { text: parent.modelData.label; color: win.balanceMuted; font.pixelSize: 12 }
                        Item { Layout.fillWidth: true }
                        LedgerText {
                            Layout.fillWidth: true
                            text: win.controller.summary[parent.modelData.key]
                            color: win.balanceInk
                            horizontalAlignment: Text.AlignRight
                            fontSizeMode: Text.HorizontalFit
                            minimumPixelSize: 10
                            font.weight: Font.DemiBold
                        }
                    }
                }

            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 16
            spacing: 10

            LedgerText { text: "Операции"; font.pixelSize: 23; font.weight: Font.DemiBold }

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
                            height: Math.max(0, tableScroll.height - groupHeader.height - columnHeader.height - entryRow.height - 10)
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
                                        objectName: "saved_" + operation.index + "_" + modelData.key
                                        readonly property bool isSearchMatch: win.searchSelection !== null &&
                                            win.searchSelection.iso === win.controller.dateIso &&
                                            win.searchSelection.block === modelData.block &&
                                            win.searchSelection.id === value.operationId
                                        width: win.cellWidth(index)
                                        height: operation.height
                                        color: isSearchMatch ? win.matchSurface :
                                               (editClick.containsMouse ? win.positiveBg : (operation.index % 2 ? win.alternate : win.paper))
                                        divided: index !== 0
                                        groupDivider: modelData.split
                                        Rectangle {
                                            width: parent.width
                                            height: 2
                                            color: win.matchEdge
                                            visible: bodyCell.isSearchMatch
                                        }

                                        MouseArea {
                                            id: editClick
                                            anchors.fill: parent
                                            enabled: bodyCell.value.operationId !== ""
                                            hoverEnabled: enabled
                                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            onClicked: win.openOperation(bodyCell.modelData.block, bodyCell.value.operationId, bodyCell.modelData.key)
                                        }
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
                                            if (inputCell.modelData.weight || inputCell.modelData.key === "marker")
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

            LedgerText {
                objectName: "weightWarning"
                Layout.fillWidth: true
                visible: text !== ""
                text: win.weightProblem || win.statusMessage
                color: win.weightProblem || win.statusError ? win.warningColor : win.muted
                wrapMode: Text.WordWrap
                Accessible.role: Accessible.StaticText
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: bottomBar.implicitHeight + 12
                color: win.paper
                border.color: win.line
                radius: 8

                RowLayout {
                    id: bottomBar
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 8
                    anchors.topMargin: 6
                    anchors.bottomMargin: 6
                    spacing: 12
                    Flow {
                        id: summaryFlow
                        Layout.fillWidth: true
                        Layout.preferredHeight: implicitHeight
                        spacing: 13
                        Row {
                            height: 28
                            spacing: 6
                            LedgerText { objectName: "receiptsLabel"; height: parent.height; text: "Постъпления"; color: win.muted; font.pixelSize: 11 }
                            LedgerText { height: parent.height; text: win.controller.summary.incoming; color: win.positive; font.weight: Font.DemiBold }
                        }
                        Row {
                            height: 28
                            spacing: 6
                            LedgerText { height: parent.height; text: "Плащания"; color: win.muted; font.pixelSize: 11 }
                            LedgerText { height: parent.height; text: win.controller.summary.outgoing; color: win.negative; font.weight: Font.DemiBold }
                        }
                        Rectangle {
                            width: movement.implicitWidth + 16
                            height: 28
                            radius: 6
                            color: win.headerSurface
                            Row {
                                id: movement
                                anchors.centerIn: parent
                                spacing: 6
                                LedgerText { text: "Движение за деня"; color: win.muted; font.pixelSize: 11; height: 24 }
                                LedgerText { text: win.controller.summary.net; font.weight: Font.DemiBold; height: 24 }
                            }
                        }
                    }
                    LedgerButton {
                        objectName: "saveOperationButton"
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignTop
                        text: win.controller.isToday ? "Запиши" : "Запиши за днес"
                        primary: true
                        onClicked: win.submit(-1)
                    }
                }
            }
        }
    }

    Dialog {
        id: updatesDialog
        objectName: "updatesDialog"
        anchors.centerIn: Overlay.overlay
        modal: true
        title: win.updates.supported ? "Обновяване" : "За „Дневник“"
        width: 390

        contentItem: ColumnLayout {
            spacing: 12
            LedgerText { text: "Версия " + win.preferences.version; color: win.muted }
            ColumnLayout {
                Layout.fillWidth: true
                visible: win.updates.supported
                spacing: 7
                LedgerButton {
                    text: win.updates.ready ? "Инсталирай обновяването" : "Провери за обновяване"
                    enabled: !win.updates.busy
                    primary: win.updates.ready
                    onClicked: {
                        if (win.updates.ready)
                            installUpdateDialog.open()
                        else
                            win.updates.check()
                    }
                }
                LedgerText {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                    text: win.updates.message
                }
            }
            LedgerButton {
                Layout.alignment: Qt.AlignRight
                text: "Затвори"
                onClicked: updatesDialog.close()
            }
        }
    }

    Dialog {
        id: installUpdateDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        title: "Инсталиране на обновяване"
        width: 390

        contentItem: ColumnLayout {
            spacing: 12
            LedgerText {
                text: "Запази въведените операции, преди да продължиш. След обновяването „Дневник“ ще се отвори отново."
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                LedgerButton { text: "Отказ"; onClicked: installUpdateDialog.close() }
                LedgerButton {
                    text: "Обнови и отвори отново"
                    primary: true
                    onClicked: {
                        installUpdateDialog.close()
                        if (win.updates.install())
                            Qt.quit()
                    }
                }
            }
        }
    }

    NumberSearch {
        id: numberSearch
        anchors.centerIn: Overlay.overlay
        controller: win.controller
        tones: ({
            surface: win.paper, text: win.ink, muted: win.muted, line: win.line,
            accent: win.accent, onAccent: win.accentText, hover: win.positiveBg, alternate: win.alternate
        })
        onMatchChosen: match => win.openMatch(match)
    }

    Dialog {
        id: cashReportDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        width: Math.min(610, win.width - 32)
        title: "Каса за последните 7 дни"
        property var days: []
        contentItem: ColumnLayout {
            spacing: 4
            RowLayout {
                Layout.fillWidth: true
                LedgerText { Layout.preferredWidth: 116; text: "Дата"; color: win.muted }
                ReportAmount { text: "Пренос"; color: win.muted }
                ReportAmount { text: "Движение"; color: win.muted }
                ReportAmount { text: "Каса"; color: win.muted }
            }
            Repeater {
                model: cashReportDialog.days
                delegate: RowLayout {
                    id: reportRow
                    required property var modelData
                    Layout.fillWidth: true
                    LedgerButton {
                        objectName: "report_day_" + reportRow.modelData.iso
                        Layout.preferredWidth: 116
                        text: reportRow.modelData.date
                        onClicked: {
                            win.showStatus(win.controller.goTo(reportRow.modelData.iso))
                            cashReportDialog.close()
                        }
                    }
                    ReportAmount { text: reportRow.modelData.carried }
                    ReportAmount { text: reportRow.modelData.movement }
                    ReportAmount {
                        text: reportRow.modelData.closing
                        font.weight: Font.DemiBold
                    }
                }
            }
            LedgerButton { Layout.alignment: Qt.AlignRight; text: "Затвори"; onClicked: cashReportDialog.close() }
        }
    }

    Dialog {
        id: editDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        width: Math.min(460, win.width - 32)
        property var fields: []
        property string initialField: ""
        property string operationDate: ""
        property string weightProblem: ""
        property string errorText: ""

        onOpened: {
            weightProblem = win.controller.draftWeightError(draft())
            const index = fields.findIndex(field => field.key === initialField)
            if (index < 0)
                return
            const editor = editFields.itemAt(index).editor
            editor.forceActiveFocus()
            const separator = editor.text.indexOf(" ")
            if (separator > 0 && /^[0-9]/.test(editor.text))
                editor.select(0, separator)
            else
                editor.selectAll()
        }

        function draft() {
            const values = {}
            for (let index = 0; index < editFields.count; index++) {
                const editor = editFields.itemAt(index)
                if (editor)
                    values[editor.modelData.key] = editor.editor.text
            }
            return values
        }
        function saveChanges() {
            if (weightProblem)
                return
            const result = win.controller.saveEdit(draft())
            if (!result.ok) {
                errorText = result.message
                return
            }
            close()
            win.showResult(result)
        }

        contentItem: ColumnLayout {
            spacing: 6
            LedgerText { text: editDialog.operationDate; color: win.muted }
            Repeater {
                id: editFields
                model: editDialog.fields
                delegate: RowLayout {
                    id: editRow
                    required property var modelData
                    property alias editor: editInput
                    Layout.fillWidth: true
                    LedgerText { text: editRow.modelData.label; Layout.preferredWidth: 175; wrapMode: Text.Wrap }
                    TextField {
                        id: editInput
                        objectName: "edit_" + editRow.modelData.key
                        Layout.fillWidth: true
                        Accessible.name: editRow.modelData.label
                        text: editRow.modelData.text
                        color: win.ink
                        readonly property bool conflict: editRow.modelData.weight && text.trim() !== "" && editDialog.weightProblem !== ""
                        background: Rectangle {
                            radius: 4
                            color: win.paper
                            border.color: editInput.conflict ? win.warningColor : (editInput.activeFocus ? win.accent : win.line)
                        }
                        onTextChanged: {
                            editDialog.errorText = ""
                            if (editRow.modelData.weight || editRow.modelData.key === "marker")
                                editDialog.weightProblem = win.controller.draftWeightError(editDialog.draft())
                        }
                        onAccepted: editDialog.saveChanges()
                    }
                }
            }
            LedgerText {
                objectName: "editWeightWarning"
                Layout.fillWidth: true
                text: editDialog.weightProblem || editDialog.errorText
                color: win.warningColor
                wrapMode: Text.WordWrap
                visible: text !== ""
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                LedgerButton { text: "Отказ"; onClicked: editDialog.close() }
                LedgerButton { text: "Запиши"; primary: true; onClicked: editDialog.saveChanges() }
            }
        }
    }

    NativeDialogs.FileDialog {
        id: backupPicker
        title: "Създай архив на дневника"
        fileMode: NativeDialogs.FileDialog.SaveFile
        defaultSuffix: "sqlite3"
        options: NativeDialogs.FileDialog.DontConfirmOverwrite
        nameFilters: ["SQLite (*.sqlite3 *.sqlite)"]
        onAccepted: win.showResult(win.controller.createArchive(selectedFile))
    }
    NativeDialogs.FileDialog {
        id: restorePicker
        title: "Избери архив на дневника"
        nameFilters: ["SQLite (*.sqlite3 *.sqlite)", "Всички файлове (*)"]
        onAccepted: {
            restoreConfirm.archive = selectedFile
            restoreConfirm.open()
        }
    }
    Dialog {
        id: restoreConfirm
        anchors.centerIn: Overlay.overlay
        modal: true
        title: "Възстановяване от архив"
        width: 390
        property url archive
        contentItem: ColumnLayout {
            spacing: 10
            LedgerText {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Архивът ще замени текущите записи. Текущата база ще се запази в отделен архив преди възстановяването."
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                LedgerButton { text: "Отказ"; onClicked: restoreConfirm.close() }
                LedgerButton {
                    text: "Възстанови"
                    primary: true
                    onClicked: {
                        const result = win.controller.restoreArchive(restoreConfirm.archive)
                        restoreConfirm.close()
                        win.showResult(result)
                    }
                }
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
