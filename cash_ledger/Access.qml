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
    title: qsTr("Дневник")
    color: dark ? "#101b2a" : "#eaf5ff"

    readonly property string registrationRole: session ? session.registrationRole : ""
    readonly property bool registering: registrationRole !== ""
    readonly property bool addingUser: registrationRole === "user"
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
    palette.window: paper
    palette.windowText: ink
    palette.buttonText: ink
    palette.button: paper
    palette.base: paper
    palette.mid: borderColor
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
        if (registering) {
            event.accepted = false
            session.cancelRegistration()
        }
    }

    component AccountField: RoundedField {
        Layout.fillWidth: true
        implicitHeight: 40
        font.pixelSize: 14
        color: access.ink
        Accessible.name: placeholderText
        selectByMouse: true
        leftPadding: 10
        rightPadding: 10
        focusBorder: access.accent
    }

    RoundedDialog {
        id: resetDialog
        anchors.centerIn: Overlay.overlay
        width: Math.min(440, access.width - 32)
        modal: true
        property bool setupCode: false
        title: setupCode ? qsTr("Задай код за нулиране") : qsTr("Нулирай администратора")

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
            loginHint.text = setupCode ? qsTr("Кодът за нулиране е запазен.")
                                       : qsTr("Профилът е обновен. Влез с новото име и парола.")
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
                      ? qsTr("За да зададеш код за първи път, въведи името и паролата на текущия администратор.")
                      : qsTr("Въведи кода за нулиране и данните за администратора.")
            }
            AccountField {
                id: recoveryCode
                objectName: "resetRecoveryCode"
                placeholderText: resetDialog.setupCode ? qsTr("Четирицифрен код за нулиране") : qsTr("Код за нулиране")
                maximumLength: resetDialog.setupCode ? 4 : 128
                echoMode: TextInput.Password
                onAccepted: resetDialog.setupCode ? resetDialog.submitRecovery() : recoveryUsername.forceActiveFocus()
            }
            AccountField {
                id: recoveryUsername
                objectName: "resetUsername"
                placeholderText: resetDialog.setupCode ? qsTr("Име на текущия администратор") : qsTr("Име за вход")
                maximumLength: 64
                onAccepted: recoveryPassword.forceActiveFocus()
            }
            AccountField {
                id: recoveryPassword
                objectName: "resetPassword"
                placeholderText: resetDialog.setupCode ? qsTr("Парола на текущия администратор")
                                                       : qsTr("Парола за новия администратор")
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
                Button { text: qsTr("Отказ"); onClicked: resetDialog.close() }
                Button {
                    objectName: "confirmAdministratorReset"
                    text: resetDialog.setupCode ? qsTr("Запази кода") : qsTr("Потвърди")
                    onClicked: resetDialog.submitRecovery()
                }
            }
        }
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(360, parent.width - 28)
        height: form.implicitHeight + 48
        radius: 19
        color: access.paper
        border.color: access.borderColor

        ColumnLayout {
            id: form
            anchors.fill: parent
            anchors.margins: 24
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Дневник")
                    color: access.accent
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }
                ComboBox {
                    id: languagePicker
                    objectName: "loginLanguagePicker"
                    Layout.preferredWidth: 108
                    Accessible.name: qsTr("Език")
                    textRole: "label"
                    valueRole: "code"
                    model: [{label: "Български", code: "bg"}, {label: "English", code: "en"}]
                    currentIndex: access.preferences && access.preferences.language === "en" ? 1 : 0
                    onActivated: errorText.text = access.preferences.setLanguage(currentValue)
                    background: Rectangle {
                        radius: 10
                        color: access.paper
                        border.color: languagePicker.visualFocus ? access.accent : access.borderColor
                    }
                }
            }
            Label {
                objectName: "accountFormTitle"
                text: !access.registering ? qsTr("Вход")
                      : access.addingUser ? qsTr("Юзър") : qsTr("Администратор")
                color: access.ink
                font.pixelSize: 25
                font.weight: Font.DemiBold
                Layout.bottomMargin: 10
            }
            AccountField {
                id: username
                objectName: "loginUsername"
                placeholderText: qsTr("Име за вход")
                maximumLength: 64
                onAccepted: password.forceActiveFocus()
            }
            AccountField {
                id: password
                objectName: "loginPassword"
                placeholderText: !access.registering ? qsTr("Парола")
                                 : access.addingUser ? qsTr("Парола за юзъра") : qsTr("Парола за администратора")
                maximumLength: 512
                echoMode: TextInput.Password
                onAccepted: access.registering ? verification.forceActiveFocus() : access.submit()
            }
            AccountField {
                id: verification
                objectName: "registrationCode"
                placeholderText: access.addingUser ? qsTr("Код за верификация") : qsTr("Код за администратора")
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
                text: !access.registering ? qsTr("Влез")
                      : access.addingUser ? qsTr("Създай юзър") : qsTr("Създай администратор")
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
                    radius: 10
                    color: submitButton.down ? Qt.darker(access.actionFill, 1.08) : access.actionFill
                    border.color: submitButton.activeFocus ? access.ink : "transparent"
                }
            }
            RowLayout {
                visible: !access.registering
                Layout.alignment: Qt.AlignHCenter
                Button {
                    objectName: "userRegistrationButton"
                    text: qsTr("Юзър")
                    flat: true
                    onClicked: {
                        access.session.beginRegistration("user")
                        access.clearForm()
                    }
                }
                Button {
                    objectName: "administratorButton"
                    text: qsTr("Администратор")
                    flat: true
                    onClicked: {
                        if (access.session.canResetAdministrator)
                            resetDialog.open()
                        else {
                            access.session.beginRegistration("administrator")
                            access.clearForm()
                        }
                    }
                }
            }
            Button {
                objectName: "backToLoginButton"
                visible: access.registering
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Назад")
                flat: true
                onClicked: {
                    access.session.cancelRegistration()
                    access.clearForm()
                }
            }
        }
    }
}
