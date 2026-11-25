import QtCore
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "recoveryCodeDialog"
    required property QtObject accountSession
    anchors.centerIn: Overlay.overlay
    width: Math.min(480, Overlay.overlay.width - 32)
    modal: true
    title: "Код за възстановяване"
    closePolicy: Popup.NoAutoClose

    function present(code) {
        value.text = code
        feedback.text = ""
        open()
    }

    onClosed: value.clear()

    contentItem: ColumnLayout {
        spacing: 10

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Запази кода на сигурно място, например в мениджър на пароли. Който има кода, може да замени администраторския профил."
        }
        TextField {
            id: value
            objectName: "issuedRecoveryCode"
            Layout.fillWidth: true
            readOnly: true
            selectByMouse: true
            font.family: "monospace"
            Accessible.name: "Код за възстановяване"
        }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Button {
                objectName: "copyRecoveryCode"
                text: "Копирай кода"
                onClicked: {
                    value.selectAll()
                    value.copy()
                    value.deselect()
                    feedback.text = "Кодът е копиран."
                }
            }
            Button {
                text: "Запази във файл…"
                onClicked: filePicker.open()
            }
        }
        Label {
            id: feedback
            Layout.fillWidth: true
            visible: text.length > 0
            wrapMode: Text.WordWrap
        }
        Button {
            objectName: "finishRecoveryCode"
            Layout.alignment: Qt.AlignRight
            text: "Готово"
            onClicked: dialog.close()
        }
    }

    NativeDialogs.FileDialog {
        id: filePicker
        title: "Запази кода за възстановяване"
        fileMode: NativeDialogs.FileDialog.SaveFile
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        nameFilters: ["Текстови файлове (*.txt)"]
        defaultSuffix: "txt"
        onAccepted: {
            const error = dialog.accountSession.saveRecoveryCode(selectedFile, value.text)
            feedback.text = error || "Кодът е записан във файл."
        }
    }
}
