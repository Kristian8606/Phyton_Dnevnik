import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: access
    required property QtObject session
    required property QtObject preferences

    width: 560
    height: 495
    minimumWidth: 340
    minimumHeight: 460
    title: "Дневник"
    color: dark ? "#141e20" : "#edf3f3"

    readonly property bool registering: session !== null && session.registering
    readonly property bool addingUser: session !== null && session.addingUser
    readonly property string theme: preferences ? preferences.theme : "system"
    readonly property bool dark: theme === "dark"
                                 || (theme === "system"
                                     && Application.styleHints.colorScheme === Qt.ColorScheme.Dark)
    readonly property color ink: dark ? "#e6eeed" : "#192426"
    readonly property color paper: dark ? "#1b2527" : "#ffffff"
    readonly property color borderColor: dark ? "#38494a" : "#d9e2e2"
    readonly property color accent: dark ? "#a1dfcc" : "#175d52"
    readonly property color accentText: dark ? "#102b26" : "#ffffff"

    palette.text: ink
    palette.windowText: ink
    palette.base: paper
    palette.highlight: accent
    palette.highlightedText: accentText

    function submit() {
        const problem = session.submit(username.text, password.text, verification.text)
        errorText.text = problem
        if (!problem)
            clearForm()
    }

    function clearForm() {
        username.clear()
        password.clear()
        verification.clear()
        errorText.text = ""
        username.forceActiveFocus()
    }

    onVisibleChanged: if (visible) clearForm()
    onClosing: event => {
        if (addingUser) {
            event.accepted = false
            session.cancelRegistration()
        }
    }

    component AccountField: TextField {
        id: field
        Layout.fillWidth: true
        implicitHeight: 40
        font.pixelSize: 14
        color: access.ink
        Accessible.name: placeholderText
        selectByMouse: true
        leftPadding: 10
        rightPadding: 10
        background: Rectangle {
            radius: 7
            color: access.paper
            border.color: field.activeFocus ? access.accent : access.borderColor
        }
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(360, parent.width - 28)
        height: form.implicitHeight + 48
        radius: 15
        color: access.paper
        border.color: access.borderColor

        ColumnLayout {
            id: form
            anchors.fill: parent
            anchors.margins: 24
            spacing: 8

            Label {
                text: "Дневник"
                color: access.accent
                font.pixelSize: 17
                font.weight: Font.DemiBold
            }
            Label {
                text: access.addingUser ? "Нов потребител"
                                                : (access.registering ? "Регистрация" : "Вход")
                color: access.ink
                font.pixelSize: 25
                font.weight: Font.DemiBold
                Layout.bottomMargin: 10
            }
            AccountField {
                id: username
                objectName: "loginUsername"
                placeholderText: "Потребителско име"
                maximumLength: 64
                onAccepted: password.forceActiveFocus()
            }
            AccountField {
                id: password
                objectName: "loginPassword"
                placeholderText: "Парола"
                maximumLength: 512
                echoMode: TextInput.Password
                onAccepted: access.registering ? verification.forceActiveFocus() : access.submit()
            }
            AccountField {
                id: verification
                objectName: "registrationCode"
                placeholderText: "Код за верификация"
                visible: access.registering
                maximumLength: 4
                inputMethodHints: Qt.ImhDigitsOnly
                echoMode: TextInput.Password
                onAccepted: access.submit()
            }
            Label {
                id: errorText
                objectName: "loginError"
                Layout.fillWidth: true
                visible: text.length > 0
                wrapMode: Text.WordWrap
                color: access.dark ? "#f4a59b" : "#a5342c"
            }
            Button {
                id: submitButton
                objectName: "accountSubmitButton"
                text: access.registering ? "Регистрирай" : "Влез"
                Layout.fillWidth: true
                implicitHeight: 41
                Layout.topMargin: 7
                onClicked: access.submit()
                contentItem: Label {
                    text: submitButton.text
                    color: access.accentText
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 7
                    color: submitButton.down ? Qt.darker(access.accent, 1.12) : access.accent
                    border.color: submitButton.activeFocus ? access.ink : "transparent"
                }
            }
            Button {
                visible: access.addingUser
                Layout.alignment: Qt.AlignHCenter
                text: "Отказ"
                flat: true
                onClicked: access.session.cancelRegistration()
            }
        }
    }
}
