import sys
import pyvisa
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton,
    QComboBox, QListWidget, QCheckBox, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class ScopeController:
    def __init__(self, backend="@py", timeout=2000):
        self.backend = backend
        self.timeout = timeout
        self.rm = None
        self.scope = None

    def connect(self, resource=None):
        self.rm = pyvisa.ResourceManager(self.backend)
        if resource:
            if not resource.startswith("USB"):
                raise RuntimeError("Invalid USB resource selected.")
            self.scope = self.rm.open_resource(resource)
            self.scope.timeout = self.timeout
            return

        for resource_name in self.rm.list_resources():
            if resource_name.startswith("USB"):
                self.scope = self.rm.open_resource(resource_name)
                self.scope.timeout = self.timeout
                return
        raise RuntimeError("No USB instrument found.")

    def list_usb_resources(self):
        rm = pyvisa.ResourceManager(self.backend)
        resources = [r for r in rm.list_resources() if r.startswith("USB")]
        rm.close()
        return resources

    def disconnect(self):
        if self.scope is not None:
            self.scope.close()
            self.scope = None
        if self.rm is not None:
            self.rm.close()
            self.rm = None

    def write(self, command):
        if self.scope is not None:
            self.scope.write(command)

    def query(self, command):
        if self.scope is not None:
            return self.scope.query(command).strip()

    def get_idn(self):
        return self.query("*IDN?")

    def run(self):
        self.write(":RUN")

    def stop(self):
        self.write(":STOP")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class ScopeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rigol Oscilloscope GUI from Suppanut")
        self.resize(1280, 900)

        self.scope_controller = ScopeController()
        self.command_history = []
        self.max_history_entries = 30
        self.is_connected = False
        self.is_running = False

        self.channel_widgets = {}
        self.mode_buttons = {}

        self.init_ui()
        self.refresh_devices()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- ส่วนที่ 1: การเชื่อมต่อและการควบคุมพื้นฐาน ---
        connection_box = QGroupBox("Connection")
        connection_layout = QVBoxLayout(connection_box)

        top_row_layout = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.addItem("Refresh devices")
        top_row_layout.addWidget(self.device_combo, stretch=1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        top_row_layout.addWidget(self.refresh_button)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_scope)
        top_row_layout.addWidget(self.connect_button)

        connection_layout.addLayout(top_row_layout)

        bottom_row_layout = QHBoxLayout()
        self.status_title_label = QLabel("Instrument ID: ")
        bottom_row_layout.addWidget(self.status_title_label)

        self.status_label = QLabel("DISCONNECTED")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        bottom_row_layout.addWidget(self.status_label)
        bottom_row_layout.addStretch()

        connection_layout.addLayout(bottom_row_layout)
        main_layout.addWidget(connection_box)

        # --- ส่วนที่ 2: Response & Command SCPI ---
        control_box = QGroupBox("SCPI Command Controls")
        control_layout = QVBoxLayout(control_box)

        # Command Line Row
        command_row_layout = QHBoxLayout()
        command_row_layout.addWidget(QLabel("Command:"))
        self.cmd_entry = QLineEdit("*IDN?")
        command_row_layout.addWidget(self.cmd_entry, stretch=1)

        self.send_button = QPushButton("Send")
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_command)
        command_row_layout.addWidget(self.send_button)
        control_layout.addLayout(command_row_layout)

        # Command History
        control_layout.addWidget(QLabel("Command History:"))
        history_row_layout = QHBoxLayout()
        self.history_listbox = QListWidget()
        self.history_listbox.setFixedHeight(80)
        self.history_listbox.itemClicked.connect(self.on_history_select)
        self.history_listbox.itemDoubleClicked.connect(self.on_history_activate)
        history_row_layout.addWidget(self.history_listbox)
        control_layout.addLayout(history_row_layout)

        clear_hist_layout = QHBoxLayout()
        clear_hist_layout.addStretch()
        self.clear_history_button = QPushButton("Clear History")
        self.clear_history_button.clicked.connect(self.clear_history)
        clear_hist_layout.addWidget(self.clear_history_button)
        control_layout.addLayout(clear_hist_layout)

        # Control Buttons Row
        button_row_layout = QHBoxLayout()
        self.run_toggle_button = QPushButton("Run")
        self.run_toggle_button.setEnabled(False)
        self.run_toggle_button.clicked.connect(self.toggle_run_stop)
        button_row_layout.addWidget(self.run_toggle_button)

        self.clear_button = QPushButton("Clear Output")
        self.clear_button.clicked.connect(self.clear_output)
        button_row_layout.addWidget(self.clear_button)
        button_row_layout.addStretch()
        control_layout.addLayout(button_row_layout)

        # Mode Selection Row
        mode_row_layout = QHBoxLayout()
        mode_row_layout.addWidget(QLabel("Mode:"))
        for label, scpi_mode in [("AUTO", "AUTO"), ("NORMAL", "NORMAL"), ("SINGLE", "SINGLE")]:
            btn = QPushButton(label)
            btn.setEnabled(False)
            btn.clicked.connect(lambda checked, m=scpi_mode: self.set_scope_mode(m))
            mode_row_layout.addWidget(btn)
            self.mode_buttons[label] = btn
        mode_row_layout.addStretch()
        control_layout.addLayout(mode_row_layout)

        # Trigger Controls Row
        trigger_row_layout = QHBoxLayout()
        trigger_row_layout.addWidget(QLabel("Offset:"))
        self.trigger_offset_entry = QLineEdit()
        self.trigger_offset_entry.setFixedWidth(80)
        self.trigger_offset_entry.setEnabled(False)
        trigger_row_layout.addWidget(self.trigger_offset_entry)

        trigger_row_layout.addWidget(QLabel("Duty (%):"))
        self.trigger_duty_entry = QLineEdit()
        self.trigger_duty_entry.setFixedWidth(80)
        self.trigger_duty_entry.setEnabled(False)
        trigger_row_layout.addWidget(self.trigger_duty_entry)

        self.trigger_apply_button = QPushButton("Apply Trigger")
        self.trigger_apply_button.setEnabled(False)
        self.trigger_apply_button.clicked.connect(self.apply_trigger_settings)
        trigger_row_layout.addWidget(self.trigger_apply_button)
        trigger_row_layout.addStretch()
        control_layout.addLayout(trigger_row_layout)

        # Channel Panels (1x4 Layout)
        panels_layout = QHBoxLayout()
        for ch in range(1, 5):
            ch_group = QGroupBox(f"CH{ch}")
            ch_layout = QVBoxLayout(ch_group)

            top_ch_layout = QHBoxLayout()
            toggle_btn = QPushButton("OFF")
            toggle_btn.setFixedWidth(50)
            toggle_btn.clicked.connect(lambda checked, c=ch: self.toggle_channel(c))
            top_ch_layout.addWidget(toggle_btn)

            state_label = QLabel("Disabled")
            top_ch_layout.addWidget(state_label)
            top_ch_layout.addStretch()
            ch_layout.addLayout(top_ch_layout)

            grid = QGridLayout()

            grid.addWidget(QLabel("Coupling"), 0, 0)
            coupling_box = QComboBox()
            coupling_box.addItems(["DC", "AC", "GND"])
            grid.addWidget(coupling_box, 0, 1)

            grid.addWidget(QLabel("Probe"), 0, 2)
            probe_box = QComboBox()
            probe_box.addItems(["1x", "10x", "100x"])
            grid.addWidget(probe_box, 0, 3)

            grid.addWidget(QLabel("Vert scale"), 1, 0)
            vertical_scale_entry = QLineEdit("1.0")
            grid.addWidget(vertical_scale_entry, 1, 1)

            grid.addWidget(QLabel("Vert unit"), 1, 2)
            vertical_unit_box = QComboBox()
            vertical_unit_box.addItems(["V/div", "mV/div"])
            grid.addWidget(vertical_unit_box, 1, 3)

            grid.addWidget(QLabel("Horiz scale"), 2, 0)
            horizontal_scale_entry = QLineEdit("1.0")
            grid.addWidget(horizontal_scale_entry, 2, 1)

            grid.addWidget(QLabel("Horiz unit"), 2, 2)
            horizontal_unit_box = QComboBox()
            horizontal_unit_box.addItems(["s/div", "ms/div", "us/div"])
            grid.addWidget(horizontal_unit_box, 2, 3)

            grid.addWidget(QLabel("Vert pos"), 3, 0)
            vertical_position_entry = QLineEdit("0.0")
            grid.addWidget(vertical_position_entry, 3, 1)

            grid.addWidget(QLabel("Horiz pos"), 3, 2)
            horizontal_position_entry = QLineEdit("0.0")
            grid.addWidget(horizontal_position_entry, 3, 3)

            invert_check = QCheckBox("Invert")
            grid.addWidget(invert_check, 4, 0)

            bandwidth_box = QComboBox()
            bandwidth_box.addItems(["FULL", "20M"])
            grid.addWidget(bandwidth_box, 4, 1)

            ch_layout.addLayout(grid)

            # Presets Layout
            presets_layout = QHBoxLayout()
            for val in [0.1, 0.2, 0.5, 1, 2, 5]:
                btn = QPushButton(str(val))
                btn.setFixedWidth(35)
                btn.clicked.connect(lambda checked, v=val, e=vertical_scale_entry: e.setText(str(v)))
                presets_layout.addWidget(btn)
            ch_layout.addLayout(presets_layout)

            apply_btn = QPushButton("Apply")
            apply_btn.clicked.connect(lambda checked, c=ch: self.apply_channel_settings(c))
            ch_layout.addWidget(apply_btn, alignment=Qt.AlignmentFlag.AlignRight)

            panels_layout.addWidget(ch_group)

            self.channel_widgets[ch] = {
                "group_box": ch_group,
                "toggle": toggle_btn,
                "coupling": coupling_box,
                "probe": probe_box,
                "vertical_scale_entry": vertical_scale_entry,
                "vertical_unit": vertical_unit_box,
                "horizontal_scale_entry": horizontal_scale_entry,
                "horizontal_unit": horizontal_unit_box,
                "vertical_position_entry": vertical_position_entry,
                "horizontal_position_entry": horizontal_position_entry,
                "bandwidth": bandwidth_box,
                "invert": invert_check,
                "apply_button": apply_btn,
                "state_label": state_label,
                "enabled": False,
            }

        control_layout.addLayout(panels_layout)

        # Output Text Console
        control_layout.addWidget(QLabel("Response / System Log:"))
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("background-color: #f4f4f4;")
        control_layout.addWidget(self.output_text)

        main_layout.addWidget(control_box)

        self.set_channel_controls_state(False)

    # --- ฟังก์ชันการทำงาน (Event Handlers & Utilities) ---
    def log_message(self, message):
        self.output_text.append(message)

    def response_message(self, message):
        self.log_message(message)

    def parse_unit_value(self, value_str, unit, unit_map):
        value = float(value_str)
        return value * unit_map.get(unit, 1.0)

    def format_float(self, value, precision=9):
        text = format(value, f".{precision}f").rstrip("0").rstrip(".")
        return text if text != "" else "0"

    def select_display_unit(self, value, units):
        if value == 0:
            return 0, units[0][0]
        for unit, factor in units:
            display_value = value / factor
            if abs(display_value) >= 0.1:
                return display_value, unit
        smallest_unit, smallest_factor = units[-1]
        return value / smallest_factor, smallest_unit

    def set_channel_controls_state(self, enabled: bool):
        for widget_set in self.channel_widgets.values():
            widget_set["toggle"].setEnabled(enabled)
            widget_set["coupling"].setEnabled(enabled)
            widget_set["probe"].setEnabled(enabled)
            widget_set["vertical_scale_entry"].setEnabled(enabled)
            widget_set["vertical_unit"].setEnabled(enabled)
            widget_set["horizontal_scale_entry"].setEnabled(enabled)
            widget_set["horizontal_unit"].setEnabled(enabled)
            widget_set["vertical_position_entry"].setEnabled(enabled)
            widget_set["horizontal_position_entry"].setEnabled(enabled)
            widget_set["bandwidth"].setEnabled(enabled)
            widget_set["invert"].setEnabled(enabled)
            widget_set["apply_button"].setEnabled(enabled)

    def toggle_channel(self, channel):
        widget_set = self.channel_widgets[channel]
        if self.scope_controller.scope is None:
            self.log_message(f"[!] Connect the instrument before controlling CH{channel}.")
            return

        widget_set["enabled"] = not widget_set["enabled"]
        label = "ON" if widget_set["enabled"] else "OFF"
        widget_set["toggle"].setText(label)
        widget_set["state_label"].setText("Enabled" if widget_set["enabled"] else "Disabled")

        try:
            state = "ON" if widget_set["enabled"] else "OFF"
            self.scope_controller.write(f":CHANnel{channel}:DISPlay {state}")
            self.log_message(f"CH{channel} set to {state}")
        except Exception as e:
            self.log_message(f"[!] Error controlling CH{channel}: {e}")

    def apply_channel_settings(self, channel):
        widget_set = self.channel_widgets[channel]
        if self.scope_controller.scope is None:
            self.log_message(f"[!] Connect the instrument before setting CH{channel} parameters.")
            return

        previous_values = {
            "vertical_scale": widget_set["vertical_scale_entry"].text(),
            "vertical_unit": widget_set["vertical_unit"].currentText(),
            "horizontal_scale": widget_set["horizontal_scale_entry"].text(),
            "horizontal_unit": widget_set["horizontal_unit"].currentText(),
            "vertical_position": widget_set["vertical_position_entry"].text(),
            "horizontal_position": widget_set["horizontal_position_entry"].text(),
            "coupling": widget_set["coupling"].currentText(),
            "probe": widget_set["probe"].currentText(),
            "bandwidth": widget_set["bandwidth"].currentText(),
            "invert": widget_set["invert"].isChecked(),
        }

        def restore_previous_values():
            widget_set["vertical_scale_entry"].setText(previous_values["vertical_scale"])
            widget_set["vertical_unit"].setCurrentText(previous_values["vertical_unit"])
            widget_set["horizontal_scale_entry"].setText(previous_values["horizontal_scale"])
            widget_set["horizontal_unit"].setCurrentText(previous_values["horizontal_unit"])
            widget_set["vertical_position_entry"].setText(previous_values["vertical_position"])
            widget_set["horizontal_position_entry"].setText(previous_values["horizontal_position"])
            widget_set["coupling"].setCurrentText(previous_values["coupling"])
            widget_set["probe"].setCurrentText(previous_values["probe"])
            widget_set["bandwidth"].setCurrentText(previous_values["bandwidth"])
            widget_set["invert"].setChecked(previous_values["invert"])

        try:
            vertical_scale_value = self.parse_unit_value(
                widget_set["vertical_scale_entry"].text(),
                widget_set["vertical_unit"].currentText(),
                {"V/div": 1.0, "mV/div": 1e-3}
            )
            horizontal_scale_value = self.parse_unit_value(
                widget_set["horizontal_scale_entry"].text(),
                widget_set["horizontal_unit"].currentText(),
                {"s/div": 1.0, "ms/div": 1e-3, "us/div": 1e-6}
            )
            vertical_position = float(widget_set["vertical_position_entry"].text())
            horizontal_position = float(widget_set["horizontal_position_entry"].text())
            coupling_value = widget_set["coupling"].currentText().upper()
            probe_value = widget_set["probe"].currentText().replace("x", "")
            bandwidth_value = widget_set["bandwidth"].currentText().upper()
            invert_value = "ON" if widget_set["invert"].isChecked() else "OFF"

            self.scope_controller.write(f":CHANnel{channel}:COUPling {coupling_value}")
            self.scope_controller.write(f":CHANnel{channel}:PROBe {probe_value}")
            self.scope_controller.write(f":CHANnel{channel}:SCALe {vertical_scale_value}")
            self.scope_controller.write(f":CHANnel{channel}:OFFSet {vertical_position}")
            self.scope_controller.write(f":TIMebase:SCALe {horizontal_scale_value}")
            self.scope_controller.write(f":TIMebase:OFFSet {horizontal_position}")
            self.scope_controller.write(f":CHANnel{channel}:BANdwidth {bandwidth_value}")
            self.scope_controller.write(f":CHANnel{channel}:INVert {invert_value}")
            self.log_message(f"CH{channel} settings applied")
        except ValueError:
            restore_previous_values()
            self.log_message(f"[!] Invalid numeric value for CH{channel}; restored previous values.")
        except Exception as e:
            restore_previous_values()
            self.log_message(f"[!] Error setting CH{channel} parameters: {e}; restored previous values.")

    def populate_channel_settings(self, channel):
        widget_set = self.channel_widgets[channel]
        if self.scope_controller.scope is None:
            return

        try:
            display_state = self.scope_controller.query(f":CHANnel{channel}:DISPlay?").strip().upper()
            enabled = display_state in {"1", "ON", "TRUE"}
            widget_set["enabled"] = enabled
            widget_set["toggle"].setText("ON" if enabled else "OFF")
            widget_set["state_label"].setText("Enabled" if enabled else "Disabled")

            coupling = self.scope_controller.query(f":CHANnel{channel}:COUPling?").strip().upper()
            if coupling in {"DC", "AC", "GND"}:
                widget_set["coupling"].setCurrentText(coupling)

            probe_response = self.scope_controller.query(f":CHANnel{channel}:PROBe?").strip()
            if probe_response:
                probe_value = probe_response.replace("X", "").replace("x", "")
                if probe_value in {"1", "10", "100"}:
                    widget_set["probe"].setCurrentText(f"{probe_value}x")

            scale_response = self.scope_controller.query(f":CHANnel{channel}:SCALe?").strip()
            if scale_response:
                scale_value = float(scale_response)
                display_value, display_unit = self.select_display_unit(
                    scale_value,
                    [("V/div", 1.0), ("mV/div", 1e-3)]
                )
                widget_set["vertical_unit"].setCurrentText(display_unit)
                widget_set["vertical_scale_entry"].setText(self.format_float(display_value))

            offset_response = self.scope_controller.query(f":CHANnel{channel}:OFFSet?").strip()
            if offset_response:
                widget_set["vertical_position_entry"].setText(self.format_float(float(offset_response)))

            timebase_scale = self.scope_controller.query(":TIMebase:SCALe?").strip()
            if timebase_scale:
                timebase_value = float(timebase_scale)
                display_value, display_unit = self.select_display_unit(
                    timebase_value,
                    [("s/div", 1.0), ("ms/div", 1e-3), ("us/div", 1e-6)]
                )
                widget_set["horizontal_unit"].setCurrentText(display_unit)
                widget_set["horizontal_scale_entry"].setText(self.format_float(display_value))

            timebase_offset = self.scope_controller.query(":TIMebase:OFFSet?").strip()
            if timebase_offset:
                widget_set["horizontal_position_entry"].setText(self.format_float(float(timebase_offset)))

            bandwidth_response = self.scope_controller.query(f":CHANnel{channel}:BANdwidth?").strip().upper()
            if bandwidth_response in {"FULL", "20M"}:
                widget_set["bandwidth"].setCurrentText(bandwidth_response)

            invert_response = self.scope_controller.query(f":CHANnel{channel}:INVert?").strip().upper()
            widget_set["invert"].setChecked(invert_response in {"1", "ON", "TRUE"})
        except Exception as e:
            self.log_message(f"[!] Unable to read current CH{channel} settings: {e}")

    def connect_scope(self):
        if self.is_connected:
            self.scope_controller.disconnect()
            self.is_connected = False

            self.connect_button.setText("Connect")
            self.status_label.setText("DISCONNECTED")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log_message("[-------] Disconnected from device.")

            self.run_toggle_button.setEnabled(False)
            self.send_button.setEnabled(False)
            for btn in self.mode_buttons.values():
                btn.setEnabled(False)
            self.trigger_offset_entry.setEnabled(False)
            self.trigger_duty_entry.setEnabled(False)
            self.trigger_apply_button.setEnabled(False)
            self.set_channel_controls_state(False)
            return

        selected = self.device_combo.currentText()
        if selected == "Refresh devices" or not selected:
            selected = None

        try:
            self.scope_controller.connect(resource=selected)
            idn = self.scope_controller.get_idn()
            self.log_message(f"Connected to: {idn}")

            self.is_connected = True
            self.connect_button.setText("Disconnect")
            self.status_label.setText(f"{idn}")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

            self.run_toggle_button.setEnabled(True)
            self.send_button.setEnabled(True)
            for btn in self.mode_buttons.values():
                btn.setEnabled(True)
            self.trigger_offset_entry.setEnabled(True)
            self.trigger_duty_entry.setEnabled(True)
            self.trigger_apply_button.setEnabled(True)
            self.set_channel_controls_state(True)

            for channel in self.channel_widgets:
                self.populate_channel_settings(channel)
            self.populate_trigger_settings()

        except RuntimeError as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def toggle_run_stop(self):
        if not self.is_running:
            try:
                self.scope_controller.run()
                self.is_running = True
                self.run_toggle_button.setText("Stop")
                self.log_message("Command executed: :RUN")
            except RuntimeError as e:
                QMessageBox.critical(self, "Error", str(e))
        else:
            try:
                self.scope_controller.stop()
                self.is_running = False
                self.run_toggle_button.setText("Run")
                self.log_message("Command executed: :STOP")
            except RuntimeError as e:
                QMessageBox.critical(self, "Error", str(e))

    def send_command(self):
        cmd = self.cmd_entry.text().strip()
        if not cmd:
            return
        self.append_history(cmd)

        try:
            self.log_message(f"> Sending: {cmd}")
            if "?" in cmd:
                response = self.scope_controller.query(cmd)
                self.log_message(f"< Response: {response}")
            else:
                self.scope_controller.write(cmd)
                self.log_message("< Success (No response expected)")
        except Exception as e:
            self.log_message(f"[!] Error: {e}")

    def append_history(self, command):
        if command in self.command_history:
            self.command_history.remove(command)
        self.command_history.insert(0, command)
        if len(self.command_history) > self.max_history_entries:
            self.command_history = self.command_history[: self.max_history_entries]

        self.history_listbox.clear()
        self.history_listbox.addItems(self.command_history)

    def on_history_select(self, item):
        self.cmd_entry.setText(item.text())

    def on_history_activate(self, item):
        self.cmd_entry.setText(item.text())
        self.send_command()

    def clear_history(self):
        self.command_history.clear()
        self.history_listbox.clear()

    def clear_output(self):
        self.output_text.clear()

    def set_scope_mode(self, mode):
        if self.scope_controller.scope is None:
            self.log_message("[!] Connect the instrument before changing mode.")
            return

        mode_map = {
            "AUTO": ("AUTO", "AUTO"),
            "NORMAL": ("NORM", "NORMAL"),
            "SINGLE": ("SING", "SINGLE"),
        }

        if mode not in mode_map:
            self.log_message(f"[!] Unsupported mode: {mode}")
            return

        sweep_value, mode_value = mode_map[mode]
        attempts = [
            (":TRIGger:SWEep", sweep_value),
            (":TRIGger:MODE", mode_value),
        ]

        last_error = None
        for command, value in attempts:
            try:
                self.scope_controller.write(f"{command} {value}")
                self.log_message(f"Mode set to {mode}")
                return
            except Exception as e:
                last_error = e

        self.log_message(f"[!] Unable to set mode {mode}: {last_error}")

    def apply_trigger_settings(self):
        if self.scope_controller.scope is None:
            self.log_message("[!] Connect the instrument before applying trigger settings.")
            return

        try:
            offset_value = float(self.trigger_offset_entry.text())
            duty_value = float(self.trigger_duty_entry.text())
            self.scope_controller.write(f":TRIGger:OFFSet {offset_value}")
            self.scope_controller.write(f":TRIGger:DUTY {duty_value}")
            self.log_message(f"Trigger offset set to {offset_value}, duty set to {duty_value}%")
        except ValueError:
            self.log_message("[!] Invalid trigger offset or duty value.")
        except Exception as e:
            self.log_message(f"[!] Unable to apply trigger settings: {e}")

    def populate_trigger_settings(self):
        if self.scope_controller.scope is None:
            return
        try:
            offset_response = self.scope_controller.query(":TRIGger:OFFSet?").strip()
            if offset_response:
                self.trigger_offset_entry.setText(self.format_float(float(offset_response)))

            duty_response = self.scope_controller.query(":TRIGger:DUTY?").strip()
            if duty_response:
                self.trigger_duty_entry.setText(self.format_float(float(duty_response)))
        except Exception as e:
            self.log_message(f"[!] Unable to read trigger settings: {e}")

    def refresh_devices(self):
        try:
            devices = self.scope_controller.list_usb_resources()
            self.device_combo.clear()
            if not devices:
                self.device_combo.addItem("No USB devices")
                return
            self.device_combo.addItems(devices)
            self.log_message(f"Found {len(devices)} USB device(s)")
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", str(e))
            self.device_combo.clear()
            self.device_combo.addItem("No USB devices")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScopeApp()
    window.show()
    sys.exit(app.exec())