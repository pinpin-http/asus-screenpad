#!/usr/bin/env python3
"""Desktop-independent ScreenPad controls for X11 and Wayland."""

import argparse
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap, QColor
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
    QMenu, QPushButton, QSlider, QSystemTrayIcon, QVBoxLayout, QWidget)


def autostart_file():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'autostart/asus-screenpad.desktop'


def set_autostart(enabled):
    path = autostart_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Desktop Entry Exec uses double quotes, not shell quoting.
        def quote(value):
            return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
        command = quote(sys.executable) + ' ' + quote(Path(__file__).resolve()) + ' --background'
        path.write_text('[Desktop Entry]\nType=Application\nName=ASUS ScreenPad\n'
                        'Exec=' + command + '\nIcon=asus-screenpad\nTerminal=false\n')
    else:
        path.unlink(missing_ok=True)


def tray_icon():
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#8bd5ff'), 2))
    painter.drawRoundedRect(3, 3, 26, 16, 2, 2)
    painter.fillRect(4, 23, 24, 6, QColor('#8bd5ff'))
    painter.end()
    return QIcon(image)


class Controls(QWidget):
    def __init__(self, helper=None):
        super().__init__()
        self.helper = Path(helper or Path(__file__).with_name('screenpadctl'))
        self.available = False
        self.powered_off = False
        self.percent = 0
        self.pending = None
        self.tray = None
        self.setWindowTitle('ASUS ScreenPad')
        self.setWindowIcon(tray_icon())
        self.setMinimumWidth(320)
        self.setMaximumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        title = QLabel('ASUS ScreenPad')
        font = title.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        self.label = QLabel('…')
        layout.addWidget(self.label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.valueChanged.connect(self.preview)
        layout.addWidget(self.slider)
        presets = QHBoxLayout()
        self.preset_buttons = []
        for value in (25, 50, 75, 100):
            button = QPushButton(f'{value}%')
            button.clicked.connect(lambda checked=False, value=value: self.set_brightness(value))
            presets.addWidget(button)
            self.preset_buttons.append(button)
        layout.addLayout(presets)
        self.power = QPushButton('Éteindre le ScreenPad')
        self.power.clicked.connect(self.toggle_power)
        layout.addWidget(self.power)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #e78284')
        self.error.hide()
        layout.addWidget(self.error)
        self.startup = QCheckBox('Lancer à la connexion')
        self.startup.setChecked(autostart_file().exists())
        self.startup.toggled.connect(self.change_autostart)
        layout.addWidget(self.startup)

        self.reader = QProcess(self)
        self.reader.finished.connect(self.read_finished)
        self.reader.errorOccurred.connect(lambda error: self.show_error('Impossible de lancer le contrôleur.'))
        self.writer = QProcess(self)
        self.writer.finished.connect(self.write_finished)
        self.writer.errorOccurred.connect(lambda error: self.show_error('Impossible de lancer le contrôleur.'))
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(90)
        self.debounce.timeout.connect(self.flush)
        self.poll = QTimer(self)
        self.poll.setInterval(2000)
        self.poll.timeout.connect(self.refresh)
        self.poll.start()
        self.setFixedSize(360, self.layout().sizeHint().height())
        self.refresh()

    def change_autostart(self, enabled):
        try:
            set_autostart(enabled)
        except OSError as error:
            self.show_error(str(error))
            self.startup.blockSignals(True)
            self.startup.setChecked(not enabled)
            self.startup.blockSignals(False)

    def show_error(self, message):
        self.error.setText(message)
        self.error.setVisible(bool(message))
        self.setFixedSize(360, self.layout().sizeHint().height())

    def busy(self):
        return self.writer.state() != QProcess.ProcessState.NotRunning or self.pending is not None or self.debounce.isActive()

    def refresh(self):
        if self.reader.state() == QProcess.ProcessState.NotRunning and not self.busy() and not self.slider.isSliderDown():
            self.reader.start(sys.executable, [str(self.helper), 'status'])

    def apply_state(self, output):
        try:
            state = json.loads(bytes(output))
        except (ValueError, TypeError):
            self.show_error('Réponse du contrôleur invalide.')
            return
        self.available = state.get('available') is True
        self.show_error(state.get('error', ''))
        self.slider.setEnabled(self.available)
        for button in self.preset_buttons:
            button.setEnabled(self.available)
        if self.available:
            self.percent = state['percent']
            self.powered_off = state['off']
            self.slider.blockSignals(True)
            self.slider.setValue(max(1, self.percent))
            self.slider.blockSignals(False)
        self.update_labels()

    def update_labels(self):
        value = 'OFF' if self.powered_off else f'{self.percent} %'
        self.label.setText(f'Luminosité · {value}' if self.available else 'ScreenPad indisponible')
        self.power.setText('Allumer le ScreenPad' if self.powered_off else 'Éteindre le ScreenPad')
        self.power.setEnabled(self.available and not self.busy())
        if self.tray:
            self.tray.setToolTip('ASUS ScreenPad · ' + (value if self.available else 'indisponible'))

    def read_finished(self, code, status):
        output = self.reader.readAllStandardOutput()
        if not self.busy() and not self.slider.isSliderDown():
            self.apply_state(output)

    def preview(self, value):
        if not self.available:
            return
        self.percent = max(1, min(100, int(value)))
        self.powered_off = False
        self.pending = ['set', str(self.percent)]
        self.debounce.start()
        self.update_labels()

    def set_brightness(self, value):
        self.preview(value)
        self.debounce.stop()
        self.flush()

    def toggle_power(self):
        if self.available and not self.busy():
            self.pending = ['toggle']
            self.flush()

    def flush(self):
        if self.writer.state() != QProcess.ProcessState.NotRunning or self.pending is None:
            return
        args, self.pending = self.pending, None
        self.writer.start(sys.executable, [str(self.helper), *args])
        self.update_labels()

    def write_finished(self, code, status):
        output = self.writer.readAllStandardOutput()
        if self.pending is None and not self.debounce.isActive() and not self.slider.isSliderDown():
            self.apply_state(output)
        elif code:
            self.apply_state(output)
        if not self.debounce.isActive():
            self.flush()
        self.update_labels()

    def closeEvent(self, event):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
        else:
            QApplication.instance().quit()
        event.accept()

    def shutdown(self):
        self.poll.stop()
        self.debounce.stop()
        self.pending = None
        for process in (self.reader, self.writer):
            if process.state() != QProcess.ProcessState.NotRunning:
                process.terminate()
                if not process.waitForFinished(1000):
                    process.kill()
                    process.waitForFinished(1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--background', action='store_true')
    parser.add_argument('--autostart', choices=['enable', 'disable'])
    args = parser.parse_args()
    if args.autostart:
        set_autostart(args.autostart == 'enable')
        return 0

    app = QApplication([sys.argv[0]])
    app.setApplicationName('ASUS ScreenPad')
    app.setDesktopFileName('asus-screenpad')
    app.setQuitOnLastWindowClosed(False)
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/tmp/asus-screenpad-{os.getuid()}'))
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    socket_name = str(runtime / 'asus-screenpad.sock')
    client = QLocalSocket()
    client.connectToServer(socket_name)
    if client.waitForConnected(500):
        if not args.background:
            client.write(b'show')
            client.waitForBytesWritten(500)
        client.disconnectFromServer()
        return 0
    QLocalServer.removeServer(socket_name)
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(socket_name):
        print(server.errorString(), file=sys.stderr)
        return 1

    window = Controls()
    app.aboutToQuit.connect(window.shutdown)
    tray = QSystemTrayIcon(tray_icon(), app)
    window.tray = tray
    menu = QMenu()
    show_action = menu.addAction('Luminosité')
    show_action.triggered.connect(lambda: (window.show(), window.raise_(), window.activateWindow()))
    menu.addSeparator()
    menu.addAction('Quitter', app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: show_action.trigger() if reason in (
        QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
    tray.show()
    window.update_labels()

    def connected():
        connection = server.nextPendingConnection()
        def ready():
            if bytes(connection.readAll()) == b'show':
                show_action.trigger()
            connection.disconnectFromServer()
        connection.readyRead.connect(ready)
        connection.disconnected.connect(connection.deleteLater)
        if connection.bytesAvailable():
            ready()
    server.newConnection.connect(connected)
    if not args.background:
        show_action.trigger()
    else:
        QTimer.singleShot(5000, lambda: show_action.trigger() if not QSystemTrayIcon.isSystemTrayAvailable() else None)
    result = app.exec()
    server.close()
    return result


if __name__ == '__main__':
    sys.exit(main())
