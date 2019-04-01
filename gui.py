import sys
from PyQt5 import QtCore, QtWidgets
from design.design import Ui_MainWindow
from design.options import Ui_OptionsWindow
from classes.inputs import Inputs
from classes.window import Window
from distutils.util import strtobool
from PIL import Image
import json
import itopod
import questing
import inspect
import math
import time
import coordinates as coords
import pytesseract
import win32gui


class NguScriptApp(QtWidgets.QMainWindow, Ui_MainWindow):
    """Main window."""

    def __init__(self, parent=None):
        """Generate UI."""
        super(NguScriptApp, self).__init__(parent)
        self.setupUi(self)  # generate the UI
        self.mutex = QtCore.QMutex()  # lock for script thread to enable pausing
        self.w = Window()
        self.i = Inputs(self.w, self.mutex)

        self.setup()

    def setup(self):
        """Add logic to UI elements."""
        self.rebirth_progress.setAlignment(QtCore.Qt.AlignCenter)
        self.task_progress.setAlignment(QtCore.Qt.AlignCenter)
        self.get_ngu_window()
        self.test_tesseract()
        self.task_progress.setValue(0)
        self.rebirth_progress.setValue(0)
        self.task_progress_animation = QtCore.QPropertyAnimation(self.task_progress, b"value")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.action_stop)
        self.run_button.clicked.connect(self.action_run)
        self.run_options.clicked.connect(self.action_options)

        try:
            with open("stats.txt", "r") as f:  # load stats from file if it exists
                data = json.loads(f.read())
                self.lifetime_itopod_kills = int(data["itopod_snipes"])
                self.lifetime_itopod_kills_data.setText(str(self.human_format(self.lifetime_itopod_kills)))
                self.lifetime_itopod_time_saved_data.setText(data["itopod_time_saved"])
        except FileNotFoundError:
            self.lifetime_itopod_kills_data.setText("0")
            self.lifetime_itopod_time_saved_data.setText("0")
            self.lifetime_itopod_kills = 0
        # self.tabWidget.setFixedSize(self.sizeHint())  # shrink window

    def closeEvent(self, event):
        """Event fired when exiting the application. This will save the current stats to file."""
        quit_msg = "Are you sure you want to exit?"
        reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               quit_msg, QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            with open("stats.txt", "w") as f:
                data = {"itopod_snipes": self.lifetime_itopod_kills,
                        "itopod_time_saved": self.lifetime_itopod_time_saved_data.text()}
                f.write(json.dumps(data))
            event.accept()
        else:
            event.ignore()
    def window_enumeration_handler(self, hwnd, top_windows):
        """Add window title and ID to array."""
        top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))

    def get_ngu_window(self):
        """Get window ID for NGU IDLE."""
        window_name = "debugg"
        top_windows = []
        win32gui.EnumWindows(self.window_enumeration_handler, top_windows)
        for i in top_windows:
            if window_name in i[1].lower():
                self.w.id = i[0]
        self.window_retry.disconnect()
        if self.w.id:
            self.window_retry.setText("Show Window")
            self.window_retry.clicked.connect(self.action_show_window)
            self.window_info_text.setText("Window detected!")
            self.get_top_left()
            if Window.x and Window.y:
                self.window_info_text.setStyleSheet("color: green")
                self.window_info_text.setText(f"Window detected! Game detected at: {Window.x}, {Window.y}")
                self.run_button.setEnabled(True)
        else:
            self.window_retry.clicked.connect(self.get_ngu_window)
            self.run_button.setEnabled(False)

    def test_tesseract(self):
        """Check if tesseract is installed."""
        try:
            pytesseract.image_to_string(Image.open("images/consumable.png"))
            self.get_ngu_window()
        except pytesseract.pytesseract.TesseractNotFoundError:
            self.window_info_text.setStyleSheet("color: red")
            self.window_info_text.setText("Tesseract not found")
            self.window_retry.setText("Try again")
            self.window_retry.disconnect()
            self.window_retry.clicked.connect(self.test_tesseract)
            self.run_button.setEnabled(False)

    def get_top_left(self):
        """Get coordinates for top left of game."""
        try:
            Window.x, Window.y = self.i.pixel_search(coords.TOP_LEFT_COLOR, 0, 0, 400, 600)
        except TypeError:
            self.window_info_text.setText(f"Window detected, but game not found!")
            self.window_info_text.setStyleSheet("color: red")
            self.window_retry.setText("Retry")
            self.window_retry.disconnect()
            self.window_retry.clicked.connect(self.get_ngu_window)

    def action_show_window(self):
        """Activate game window."""
        win32gui.ShowWindow(self.w.id, 5)
        win32gui.SetForegroundWindow(self.w.id)

    def action_stop(self, thread):
        """Stop script thread."""
        if self.mutex.tryLock(1000):  # only way to check if we have the lock without crashing?
            self.run_thread.terminate()
            self.run_button.setText("Run")
            self.run_button.disconnect()
            self.run_button.clicked.connect(self.action_run)
            self.stop_button.setEnabled(False)
            self.mutex.unlock()
        else:
            QtWidgets.QMessageBox.information(self, "Error", "Couldn't acquire lock of script thread.")

    def action_pause(self, thread):
        """Attempt to block script thread by acquiring lock."""
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(False)  # stopping while paused causes a deadlock
        self.run_button.setText("Pausing...")
        self.mutex.lock()
        self.run_button.disconnect()
        self.run_button.clicked.connect(self.action_resume)
        self.run_button.setText("Resume")
        self.run_button.setEnabled(True)

    def action_resume(self, thread):
        """Attempt to release lock to un-block script thread."""
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.run_button.setText("Pause")
        self.run_button.disconnect()
        self.mutex.unlock()
        self.run_button.setEnabled(True)
        self.run_button.clicked.connect(self.action_pause)

    def action_options(self):
        """Display option window."""
        index = self.combo_run.currentIndex()
        self.options = OptionsWindow(index)
        self.options.setFixedSize(300, 240)
        self.options.show()

    def human_format(self, num):
        """Convert large integer to readable format."""
        num = float('{:.3g}'.format(num))
        if num > 1e14:
            return
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0
        return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

    def timestamp(self):
        """Update timestamp for elapsed time."""
        n = time.time() - self.start_time
        days = math.floor(n // (24 * 3600))
        n = n % (24 * 3600)

        if days > 0:
            result = f"{days} days, {time.strftime('%H:%M:%S', time.gmtime(n))}"
        else:
            result = f"{time.strftime('%H:%M:%S', time.gmtime(n))}"
        self.elapsed_data.setText(result)

    def update(self, result):
        """Update data in UI upon event."""
        for k, v in result.items():
            if k == "exp":
                self.exp_data.setText(self.human_format(v))
            elif k == "pp":
                self.pp_data.setText(self.human_format(v))
            elif k == "qp":
                self.qp_data.setText(self.human_format(v))
            elif k == "xph":
                self.exph_data.setText(self.human_format(v))
            elif k == "pph":
                self.pph_data.setText(self.human_format(v))
            elif k == "qph":
                self.qph_data.setText(self.human_format(v))
            elif k == "task_progress":
                self.task_progress_animation.setDuration(200)
                self.task_progress_animation.setStartValue(self.task_progress.value())
                self.task_progress_animation.setEndValue(v)
                print(f"start: {self.task_progress.value()}, end: {v}")
                self.task_progress_animation.start()
                #self.task_progress.setValue(math.ceil(v))
            elif k == "itopod_snipes":
                self.lifetime_itopod_kills += 1
                self.lifetime_itopod_kills_data.setText(str(self.human_format(self.lifetime_itopod_kills)))

                n = self.lifetime_itopod_kills * 0.8
                days = math.floor(n // (24 * 3600))
                n = n % (24 * 3600)
                hours = math.floor(n // 3600)
                n %= 3600
                minutes = math.floor(n // 60)
                n %= 60
                seconds = math.floor(n)

                self.lifetime_itopod_time_saved_data.setText(f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds")

            elif k == "task":
                self.current_task_text.setText(v)

    def action_run(self):
        """Start the selected script."""
        run = self.combo_run.currentIndex()
        self.start_time = time.time()
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1010)
        self.timer.timeout.connect(self.timestamp)
        self.timer.start()
        if run == 0:
            self.run_thread = ScriptThread(0, self.w, self.mutex)
            self.run_thread.signal.connect(self.update)
            self.run_button.setText("Pause")
            self.run_button.disconnect()
            self.run_button.clicked.connect(self.action_pause)
            self.w_exp.show()
            self.w_pp.hide()
            self.w_pph.hide()
            self.w_exph.show()
            self.w_qp.show()
            self.w_qph.show()
            self.current_rb_text.hide()
            self.rebirth_progress.hide()
            self.setFixedSize(300, 320)
            self.current_task_text.show()
            self.task_progress.show()
            self.task_progress.setValue(0)
            self.stop_button.setEnabled(True)
            self.run_thread.start()

        elif run == 1:
            self.run_thread = ScriptThread(1, self.w, self.mutex)
            self.run_thread.signal.connect(self.update)
            self.run_button.setText("Pause")
            self.run_button.disconnect()
            self.run_button.clicked.connect(self.action_pause)
            self.w_exp.show()
            self.w_pp.show()
            self.w_pph.show()
            self.w_exph.show()
            self.w_qp.hide()
            self.w_qph.hide()
            self.current_rb_text.hide()
            self.rebirth_progress.hide()
            self.setFixedSize(300, 320)
            self.current_task_text.show()
            self.task_progress.show()
            self.task_progress.setValue(0)
            self.stop_button.setEnabled(True)
            self.run_thread.start()


class OptionsWindow(QtWidgets.QMainWindow, Ui_OptionsWindow):
    """Option window."""

    def __init__(self, index, parent=None):
        """Setup UI."""
        super(OptionsWindow, self).__init__(parent)
        self.setupUi(self)
        self.index = index
        self.settings = QtCore.QSettings("Kujan", "NGU-Scripts")
        self.button_ok.clicked.connect(self.action_ok)
        self.check_gear.stateChanged.connect(self.state_changed_gear)
        self.check_boost_inventory.stateChanged.connect(self.state_changed_boost_inventory)
        self.check_merge_inventory.stateChanged.connect(self.state_changed_merge_inventory)
        self.radio_group_gear = QtWidgets.QButtonGroup(self)
        self.radio_group_gear.addButton(self.radio_equipment)
        self.radio_group_gear.addButton(self.radio_cube)
        self.gui_load()

    def state_changed_gear(self, int):
        """Update UI."""
        if self.check_gear.isChecked():
            self.radio_equipment.setEnabled(True)
            self.radio_cube.setEnabled(True)
        else:
            self.radio_equipment.setEnabled(False)
            self.radio_equipment.setChecked(False)
            self.radio_cube.setEnabled(False)
            self.radio_cube.setChecked(False)

    def state_changed_boost_inventory(self, int):
        """Update UI."""
        if self.check_boost_inventory.isChecked():
            self.line_boost_inventory.setEnabled(True)
        else:
            self.line_boost_inventory.setEnabled(False)

    def state_changed_merge_inventory(self, int):
        """Update UI."""
        if self.check_merge_inventory.isChecked():
            self.line_merge_inventory.setEnabled(True)
        else:
            self.line_merge_inventory.setEnabled(False)

    def gui_load(self):
        """Load settings from registry."""
        for name, obj in inspect.getmembers(self):
            if isinstance(obj, QtWidgets.QComboBox):
                index = obj.currentIndex()
                text = obj.itemText(index)
                name = obj.objectName()
                value = (self.settings.value(name))

                if value == "":
                    continue

                index = obj.findText(value)

                if index == -1:
                    obj.insertItems(0, [value])
                    index = obj.findText(value)
                    obj.setCurrentIndex(index)
                else:
                    obj.setCurrentIndex(index)

            if isinstance(obj, QtWidgets.QLineEdit):
                name = obj.objectName()
                value = (self.settings.value(name))
                obj.setText(value)

            if isinstance(obj, QtWidgets.QCheckBox):
                name = obj.objectName()
                value = self.settings.value(name)
                if value is not None:
                    obj.setChecked(strtobool(value))
            if isinstance(obj, QtWidgets.QRadioButton):
                name = obj.objectName()
                value = self.settings.value(name)
                if value is not None:
                    obj.setChecked(strtobool(value))

    def action_ok(self):
        """Save settings and close window."""
        print("value")
        self.settings.setValue('size', self.size())
        self.settings.setValue('pos', self.pos())

        for name, obj in inspect.getmembers(self):
            if isinstance(obj, QtWidgets.QComboBox):
                name = obj.objectName()
                index = obj.currentIndex()
                text = obj.itemText(index)
                self.settings.setValue(name, text)
                self.settings.setValue(name + "_index", index)

            if isinstance(obj, QtWidgets.QLineEdit):
                name = obj.objectName()
                value = obj.text()
                self.settings.setValue(name, value)

            if isinstance(obj, QtWidgets.QCheckBox):
                name = obj.objectName()
                state = obj.isChecked()
                self.settings.setValue(name, state)

            if isinstance(obj, QtWidgets.QRadioButton):
                name = obj.objectName()
                value = obj.isChecked()
                self.settings.setValue(name, value)
        self.close()


class ScriptThread(QtCore.QThread):
    """Thread class for script."""

    signal = QtCore.pyqtSignal("PyQt_PyObject")

    def __init__(self, run, w, mutex):
        """Init thread variables."""
        QtCore.QThread.__init__(self)
        self.run = run
        self.w = w
        self.mutex = mutex

    def run(self):
        """Check which script to run."""
        if self.run == 0:
            questing.run(self.w, self.mutex, self.signal)
        if self.run == 1:
            itopod.run(self.w, self.mutex, self.signal)


def run():
    """Start GUI thread."""
    app = QtWidgets.QApplication(sys.argv)
    GUI = NguScriptApp()
    GUI.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    run()

"""
Ideas

Progressbars tracking current long running task (sniping, questing)
Progressbar tracking run progression (if applicable)
Tools for annoying actions while playing manually (cap all diggers)
Quickstart for infinite questing/itopod sniping
Track minor/major quests done
Track current function (via object?)
"""