import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: access
    required property QtObject session
    required property QtObject preferences

    width: 560
    height: 515
    minimumWidth: 340
    minimumHeight: 460
    title: "Дневник"
    color: dark ? "#101b2a" : "#eaf5ff"

    readonly property bool registering: session !== null && session.registering
    readonly property bool addingUser: session !== null && session.addingUser
    readonly property string theme: preferences ? preferences.theme : "system"
    readonly property bool dark: theme === "dark"
                                 || (theme === "system"
                                     && Application.styleHints.colorScheme === Qt.ColorScheme.Dark)
    readonly property color ink: dark ? "#eaf3ff" : "#162f48"
    readonly property color paper: dark ? "#182536" : "#ffffff"
    readonly property color borderColor: dark ? "#344c62" : "#c5d9ed"
    readonly property color accent: dark ? "#a2cdf7" : "#245d93"
    readonly property color actionFill: dark ? "#9dccf5" : "#acd6fa"
    readonly property color accentText: "#102a43"

    palette.text: ink
    palette.windowText: ink
    palette.buttonText: ink
    palette.button: paper
    palette.base: paper
    palette.highlight: actionFill
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
        loginHint.text = ""
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

    Dialog {
        id: resetDialog
        anchors.centerIn: Overlay.overlay
        width: Math.min(440, access.width - 32)
        modal: true
        property bool setupCode: false
        title: setupCode ? "Задай код за нулиране" : "Нулирай администратора"

        function submitRecovery() {
            const error = access.session.submitAdministratorRecovery(
                recoveryCode.text, recoveryUsername.text, recoveryPassword.text, setupCode)
            if (error) {
                resetError.text = error
                return
            }
            close()
            access.session.cancelRegistration()
            access.clearForm()
            loginHint.text = setupCode ? "Кодът за нулиране е запазен."
                                       : "Профилът е обновен. Влез с новото име и парола."
        }

        onAboutToShow: setupCode = access.session.needsRecoveryCode()
        onOpened: (setupCode ? recoveryUsername : recoveryCode).forceActiveFocus()
        onClosed: {
            recoveryCode.clear()
            recoveryUsername.clear()
            recoveryPassword.clear()
            resetError.text = ""
        }

        contentItem: ColumnLayout {
            spacing: 8
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: resetDialog.setupCode
                      ? "За да зададеш код за първи път, въведи името и паролата на текущия администратор."
                      : "Въведи кода за нулиране и данните за администратора."
            }
            AccountField {
                id: recoveryCode
                objectName: "resetRecoveryCode"
                placeholderText: resetDialog.setupCode ? "Четирицифрен код за нулиране" : "Код за нулиране"
                maximumLength: resetDialog.setupCode ? 4 : 128
                echoMode: TextInput.Password
                onAccepted: resetDialog.setupCode ? resetDialog.submitRecovery() : recoveryUsername.forceActiveFocus()
            }
            AccountField {
                id: recoveryUsername
                objectName: "resetUsername"
                placeholderText: resetDialog.setupCode ? "Име на текущия администратор" : "Име за вход"
                maximumLength: 64
                onAccepted: recoveryPassword.forceActiveFocus()
            }
            AccountField {
                id: recoveryPassword
                objectName: "resetPassword"
                placeholderText: resetDialog.setupCode ? "Парола на текущия администратор"
                                                       : "Парола за новия администратор"
                maximumLength: 512
                echoMode: TextInput.Password
                onAccepted: resetDialog.setupCode ? recoveryCode.forceActiveFocus() : resetDialog.submitRecovery()
            }
            Label {
                id: resetError
                objectName: "resetError"
                Layout.fillWidth: true
                visible: text.length > 0
                wrapMode: Text.WordWrap
                color: access.dark ? "#f4a59b" : "#a5342c"
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                Button { text: "Отказ"; onClicked: resetDialog.close() }
                Button {
                    objectName: "confirmAdministratorReset"
                    text: resetDialog.setupCode ? "Запази кода" : "Потвърди"
                    onClicked: resetDialog.submitRecovery()
                }
            }
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
                objectName: "accountFormTitle"
                text: !access.registering ? "Вход"
                      : access.addingUser ? "Юзър" : "Администратор"
                color: access.ink
                font.pixelSize: 25
                font.weight: Font.DemiBold
                Layout.bottomMargin: 10
            }
            AccountField {
                id: username
                objectName: "loginUsername"
                placeholderText: "Име за вход"
                maximumLength: 64
                onAccepted: password.forceActiveFocus()
            }
            AccountField {
                id: password
                objectName: "loginPassword"
                placeholderText: !access.registering ? "Парола"
                                 : access.addingUser ? "Парола за юзъра" : "Парола за администратора"
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
            Label {
                id: loginHint
                Layout.fillWidth: true
                visible: text.length > 0
                wrapMode: Text.WordWrap
                color: access.accent
            }
            Button {
                id: submitButton
                objectName: "accountSubmitButton"
                text: !access.registering ? "Влез"
                      : access.addingUser ? "Създай юзър" : "Създай администратор"
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
                    color: submitButton.down ? Qt.darker(access.actionFill, 1.08) : access.actionFill
                    border.color: submitButton.activeFocus ? access.ink : "transparent"
                }
            }
            Button {
                objectName: "registrationButton"
                visible: !access.registering || access.addingUser
                Layout.alignment: Qt.AlignHCenter
                text: access.addingUser ? "Назад" : "Регистрация на юзър"
                flat: true
                onClicked: {
                    if (access.addingUser)
                        access.session.cancelRegistration()
                    else
                        access.session.add_user()
                    access.clearForm()
                }
            }
            Button {
                objectName: "resetAdministratorButton"
                visible: access.session && access.session.canResetAdministrator
                Layout.alignment: Qt.AlignHCenter
                text: "Нулирай администратора…"
                flat: true
                onClicked: resetDialog.open()
            }
        }
    }
}
