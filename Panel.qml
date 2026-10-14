import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Ui.Panel {
  id: root
  moduleName: "soheib.screenpad"
  manageIpc: false

  readonly property string helper: decodeURIComponent(Qt.resolvedUrl("screenpadctl").toString().replace(/^file:\/\//, ""))
  readonly property string screenName: button.QsWindow.window && button.QsWindow.window.screen
    ? button.QsWindow.window.screen.name : ""
  property int brightness: 0
  property int pending: -1
  property int raw: 0
  property bool available: false
  property bool poweredOff: false
  property string lastError: ""
  property real wheelRemainder: 0
  readonly property bool busy: writer.running || debounce.running || pending >= 0
  readonly property string percentage: poweredOff ? "OFF" : brightness + "%"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refresh() {
    if (!reader.running && !busy && !slider.dragging) reader.running = true
  }

  function applyState(text, fromWriter) {
    var state
    try { state = JSON.parse(text) }
    catch (error) {
      root.lastError = "Réponse du contrôleur ScreenPad invalide."
      return
    }
    // A read started before a drag must not overwrite the user's preview.
    if (!fromWriter && (root.busy || slider.dragging)) return
    root.available = state.available === true
    root.lastError = state.error || ""
    if (!root.available) return
    root.raw = state.raw
    root.poweredOff = state.off
    if (root.pending < 0 && !debounce.running && !slider.dragging)
      root.brightness = state.percent
  }

  function preview(value) {
    if (!available) return
    brightness = Math.max(1, Math.min(100, Math.round(value)))
    poweredOff = false
    pending = brightness
    debounce.restart()
  }

  function flush() {
    if (writer.running || pending < 0) return
    var value = pending
    pending = -1
    writer.command = ["python3", helper, "set", String(value)]
    writer.running = true
  }

  function setBrightness(value) {
    if (!Number.isFinite(value) || value < 1 || value > 100) return false
    preview(value)
    debounce.stop()
    flush()
    return available
  }

  function togglePower() {
    if (!available || busy) return
    writer.command = ["python3", helper, "toggle"]
    writer.running = true
  }

  onOpenedChanged: if (opened) refresh()
  Component.onCompleted: refresh()

  Timer {
    interval: root.opened ? 1000 : 3000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Timer {
    id: debounce
    interval: 90
    onTriggered: root.flush()
  }

  Process {
    id: reader
    command: ["python3", root.helper, "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyState(text, false)
    }
  }

  Process {
    id: writer
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyState(text, true)
    }
    onExited: function(exitCode) {
      if (exitCode !== 0 && root.lastError === "")
        root.lastError = "Impossible de régler la luminosité du ScreenPad."
      if (root.pending >= 0 && !debounce.running) Qt.callLater(root.flush)
    }
  }

  // A unique target per bar screen avoids duplicate handlers on dual screens.
  IpcHandler {
    enabled: root.screenName !== ""
    target: "screenpad-" + root.screenName
    function state(): string {
      return JSON.stringify({available: root.available, brightness: root.brightness,
        raw: root.raw, off: root.poweredOff, busy: root.busy,
        opened: root.opened, error: root.lastError})
    }
    function brightness(percent: string): string {
      return root.setBrightness(Number(percent)) ? "ok" : "invalid or unavailable"
    }
    function togglePower(): void { root.togglePower() }
  }

  Ui.WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰍺 " + (root.available ? root.percentage : "!")
    active: root.opened
    tooltipText: "ASUS ScreenPad · " + (root.available ? root.percentage : "indisponible")
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton || buttonCode === Qt.RightButton) root.toggle()
    }
    onWheelMoved: function(delta) {
      if (!root.available) return
      var wheel = Util.wheelSteps(root.wheelRemainder, delta)
      root.wheelRemainder = wheel.remainder
      if (wheel.steps !== 0) root.setBrightness(Math.max(1, Math.min(100, root.brightness + wheel.steps * 5)))
    }
  }

  Ui.KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keys
    contentWidth: panel.fittedContentWidth(Style.space(300))
    contentHeight: panel.fittedContentHeight(content.implicitHeight)

    Ui.PanelKeyCatcher {
      id: keys
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onMoveRequested: function(dx, dy) {
        if (dx !== 0) root.setBrightness(Math.max(1, Math.min(100, root.brightness + dx * 5)))
      }
      onActivateRequested: root.togglePower()

      Column {
        id: content
        width: parent.width
        spacing: Style.space(12)

        Text {
          text: "ASUS ScreenPad"
          color: root.barForeground
          font.family: Style.font.family
          font.pixelSize: Style.font.title
          font.bold: true
        }
        Text {
          width: parent.width
          text: root.available ? (root.poweredOff ? "Écran secondaire éteint" : "Luminosité · " + root.brightness + " %")
            : "ScreenPad indisponible"
          color: root.barForeground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          wrapMode: Text.WordWrap
        }
        Ui.PanelSlider {
          id: slider
          width: parent.width
          bar: root.bar
          minimum: 1
          maximum: 100
          step: 1
          integer: true
          value: Math.max(1, root.brightness)
          enabled: root.available
          opacity: enabled ? 1 : 0.4
          onMoved: function(value) { root.preview(value) }
          onReleased: function(value) { root.setBrightness(value) }
        }
        Row {
          spacing: Style.space(6)
          Repeater {
            model: [25, 50, 75, 100]
            Ui.Button {
              required property int modelData
              text: modelData + "%"
              foreground: root.barForeground
              enabled: root.available
              bordered: true
              selected: !root.poweredOff && root.brightness === modelData
              onClicked: root.setBrightness(modelData)
            }
          }
        }
        Ui.Button {
          width: parent.width
          text: root.poweredOff ? "Allumer le ScreenPad" : "Éteindre le ScreenPad"
          iconText: "⏻"
          foreground: root.barForeground
          bordered: true
          enabled: root.available && !root.busy
          onClicked: root.togglePower()
        }
        Text {
          width: parent.width
          visible: root.lastError !== ""
          text: root.lastError
          color: Color.urgent
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
