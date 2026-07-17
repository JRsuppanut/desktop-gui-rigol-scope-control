import tkinter as tk
from tkinter import ttk, messagebox
import pyvisa

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
        # ตัดการเชื่อมต่อ
        if self.scope is not None:
            self.scope.close()
            self.scope = None
        if self.rm is not None:
            self.rm.close()
            self.rm = None

    def write(self, command):
        # ส่งคำสั่ง SCPI แบบไม่ต้องส่งผลลัพธ์กลับมา 
        if self.scope is not None:
            self.scope.write(command)

    def query(self, command):
        # ส่งคำสั่ง SCPI และอ่านค่าการตอบรับกลับมา 
        if self.scope is not None:
            return self.scope.query(command).strip()

    def get_idn(self):
        return self.query("*IDN?")

    def run(self):
        # สั่งให้ออสซิลโลสโคปเริ่มการทำงาน
        self.write(":RUN")

    def stop(self):
        # สั่งให้ออสซิลโลสโคปหยุดการทำงาน
        self.write(":STOP")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class ScopeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rigol Oscilloscope GUI from Suppanut")
        self.geometry("1980x1080")
        self.scope_controller = ScopeController()
        self.command_history = []
        self.max_history_entries = 30
        self.is_connected = False
        self.create_widgets()

    def create_widgets(self):
        # --- ส่วนที่ 1: การเชื่อมต่อและการควบคุมพื้นฐาน ---
        Connection_frame = ttk.LabelFrame(self, text="Connection", padding=10)
        Connection_frame.pack(pady=10, padx=20, fill="x")
        
        # สร้าง Frame ย่อยแถวบน สำหรับการเลือกอุปกรณ์และปุ่มเชื่อมต่อ
        top_row = ttk.Frame(Connection_frame)
        top_row.pack(fill="x", side="top", anchor="w")
        
        # กำหนด state="readonly" เพื่อไม่ให้ผู้ใช้แก้ไขข้อความเอง
        self.device_combo = ttk.Combobox(top_row, state="readonly")
        self.device_combo.set("Refresh devices")
        self.device_combo.pack(side="left", padx=(0, 5), fill="x", expand=True)
        
        self.refresh_button = ttk.Button(top_row, text="Refresh", command=self.refresh_devices)
        self.refresh_button.pack(side="right", padx=5)

        self.connect_button = ttk.Button(top_row, text="Connect", command=self.connect_scope)
        self.connect_button.pack(side="right", padx=0)
        
        # สร้าง Frame ย่อยแถวล่าง สำหรับการแสดง Status เพื่อให้ขึ้นบรรทัดใหม่
        bottom_row = ttk.Frame(Connection_frame)
        bottom_row.pack(fill="x", side="top", anchor="w", pady=(10, 0))
        
        self.status_title_label = ttk.Label(bottom_row, text="Instrument ID: ")
        self.status_title_label.pack(side="left")
        
        self.status_label = ttk.Label(bottom_row, text="DISCONNECTED", foreground="red", font=("Arial", 9, "bold"))
        self.status_label.pack(side="left")
        
        # --- ส่วนที่ 2: Response & Command SCPI ---
        main_frame = ttk.Frame(self)
        main_frame.pack(pady=10, padx=20, fill="both", expand=True)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        control_frame = ttk.LabelFrame(main_frame, text="SCPI Command Controls", padding=10)
        control_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        control_frame.rowconfigure(2, weight=1)

        command_row = ttk.Frame(control_frame)
        command_row.pack(fill="x", pady=(0, 8))

        ttk.Label(command_row, text="Command:").pack(side="left", padx=5)
        self.cmd_entry = ttk.Entry(command_row)
        self.cmd_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.cmd_entry.insert(0, "*IDN?") # คำสั่งเริ่มต้น

        self.send_button = ttk.Button(command_row, text="Send", command=self.send_command, state=tk.DISABLED)
        self.send_button.pack(side="left", padx=5)
        
        history_row = ttk.Frame(control_frame)
        history_row.pack(fill="both", pady=(0, 8), expand=True)

        history_label = ttk.Label(history_row, text="Command History:")
        history_label.pack(anchor="w", padx=5, pady=(0, 2))

        history_frame = ttk.Frame(history_row)
        history_frame.pack(fill="both", expand=True, padx=5)

        self.history_listbox = tk.Listbox(history_frame, height=5, exportselection=False)
        self.history_listbox.pack(side="left", fill="both", expand=True)
        self.history_listbox.bind("<<ListboxSelect>>", self.on_history_select)
        self.history_listbox.bind("<Double-Button-1>", self.on_history_activate)

        history_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_listbox.yview)
        history_scrollbar.pack(side="right", fill="y")
        self.history_listbox.config(yscrollcommand=history_scrollbar.set)

        self.clear_history_button = ttk.Button(history_row, text="Clear History", command=self.clear_history)
        self.clear_history_button.pack(anchor="e", padx=5, pady=(4, 0))
        
        button_row = ttk.Frame(control_frame)
        button_row.pack(fill="x", pady=(0, 8))

        self.run_toggle_button = ttk.Button(button_row, text="Run", command=self.toggle_run_stop, state=tk.DISABLED)
        self.run_toggle_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(button_row, text="Clear Output", command=self.clear_output)
        self.clear_button.pack(side="left", padx=5)

        mode_row = ttk.Frame(control_frame)
        mode_row.pack(fill="x", pady=(0, 8))

        ttk.Label(mode_row, text="Mode:").pack(side="left", padx=5)
        self.mode_buttons = {}
        for label, scpi_mode in [("AUTO", "AUTO"), ("NORMAL", "NORMAL"), ("SINGLE", "SINGLE")]:
            btn = ttk.Button(mode_row, text=label, state=tk.DISABLED,
                             command=lambda m=scpi_mode: self.set_scope_mode(m))
            btn.pack(side="left", padx=4)
            self.mode_buttons[label] = btn

        trigger_row = ttk.Frame(control_frame)
        trigger_row.pack(fill="x", pady=(0, 8))

        ttk.Label(trigger_row, text="Offset:").pack(side="left", padx=5)
        self.trigger_offset_entry = ttk.Entry(trigger_row, width=10, state=tk.DISABLED)
        self.trigger_offset_entry.pack(side="left", padx=4)

        ttk.Label(trigger_row, text="Duty (%):").pack(side="left", padx=5)
        self.trigger_duty_entry = ttk.Entry(trigger_row, width=10, state=tk.DISABLED)
        self.trigger_duty_entry.pack(side="left", padx=4)

        self.trigger_apply_button = ttk.Button(trigger_row, text="Apply Trigger", state=tk.DISABLED,
                                               command=self.apply_trigger_settings)
        self.trigger_apply_button.pack(side="left", padx=8)

        # Channel panels: 2x2 grid with richer controls per channel
        # Channel panels in a single horizontal row
        panels_frame = ttk.Frame(control_frame)
        panels_frame.pack(fill="x", pady=(0, 10))

        self.channel_widgets = {}
        for idx, ch in enumerate(range(1, 5)):
            col = idx
            ch_frame = ttk.LabelFrame(panels_frame, text=f"CH{ch}", padding=8)
            ch_frame.grid(row=0, column=col, padx=6, pady=6, sticky="nsew")
            panels_frame.columnconfigure(col, weight=1)

            top_row = ttk.Frame(ch_frame)
            top_row.pack(fill="x", pady=(0, 6))
            toggle_btn = ttk.Button(top_row, text="OFF", width=6, command=lambda c=ch: self.toggle_channel(c))
            toggle_btn.pack(side="left")

            state_label = ttk.Label(top_row, text="Disabled")
            state_label.pack(side="left", padx=(8,0))

            # controls grid inside channel
            grid = ttk.Frame(ch_frame)
            grid.pack(fill="x")

            ttk.Label(grid, text="Coupling").grid(row=0, column=0, sticky="w", padx=4, pady=2)
            coupling_var = tk.StringVar(value="DC")
            coupling_box = ttk.Combobox(grid, textvariable=coupling_var, values=["DC","AC","GND"], width=6, state="readonly")
            coupling_box.grid(row=0, column=1, sticky="w", padx=4)

            ttk.Label(grid, text="Probe").grid(row=0, column=2, sticky="w", padx=4)
            probe_var = tk.StringVar(value="10x")
            probe_box = ttk.Combobox(grid, textvariable=probe_var, values=["1x","10x","100x"], width=6, state="readonly")
            probe_box.grid(row=0, column=3, sticky="w", padx=4)

            ttk.Label(grid, text="Vert scale").grid(row=1, column=0, sticky="w", padx=4, pady=2)
            vertical_scale_var = tk.StringVar(value="1.0")
            vertical_scale_entry = ttk.Entry(grid, textvariable=vertical_scale_var, width=8)
            vertical_scale_entry.grid(row=1, column=1, sticky="w", padx=4)

            ttk.Label(grid, text="Vert unit").grid(row=1, column=2, sticky="w", padx=4)
            vertical_unit_var = tk.StringVar(value="V/div")
            vertical_unit_box = ttk.Combobox(grid, textvariable=vertical_unit_var, values=["V/div","mV/div"], width=8, state="readonly")
            vertical_unit_box.grid(row=1, column=3, sticky="w", padx=4)

            ttk.Label(grid, text="Horiz scale").grid(row=2, column=0, sticky="w", padx=4, pady=2)
            horizontal_scale_var = tk.StringVar(value="1.0")
            horizontal_scale_entry = ttk.Entry(grid, textvariable=horizontal_scale_var, width=8)
            horizontal_scale_entry.grid(row=2, column=1, sticky="w", padx=4)

            ttk.Label(grid, text="Horiz unit").grid(row=2, column=2, sticky="w", padx=4)
            horizontal_unit_var = tk.StringVar(value="s/div")
            horizontal_unit_box = ttk.Combobox(grid, textvariable=horizontal_unit_var, values=["s/div","ms/div","us/div"], width=8, state="readonly")
            horizontal_unit_box.grid(row=2, column=3, sticky="w", padx=4)

            ttk.Label(grid, text="Vert pos").grid(row=3, column=0, sticky="w", padx=4, pady=2)
            vertical_position_var = tk.StringVar(value="0.0")
            vertical_position_entry = ttk.Entry(grid, textvariable=vertical_position_var, width=8)
            vertical_position_entry.grid(row=3, column=1, sticky="w", padx=4)

            ttk.Label(grid, text="Horiz pos").grid(row=3, column=2, sticky="w", padx=4)
            horizontal_position_var = tk.StringVar(value="0.0")
            horizontal_position_entry = ttk.Entry(grid, textvariable=horizontal_position_var, width=8)
            horizontal_position_entry.grid(row=3, column=3, sticky="w", padx=4)

            invert_var = tk.BooleanVar(value=False)
            invert_check = ttk.Checkbutton(grid, text="Invert", variable=invert_var)
            invert_check.grid(row=4, column=0, sticky="w", padx=4, pady=2)

            bandwidth_var = tk.StringVar(value="FULL")
            bandwidth_box = ttk.Combobox(grid, textvariable=bandwidth_var, values=["FULL","20M"], width=6, state="readonly")
            bandwidth_box.grid(row=4, column=1, sticky="w", padx=4)

            # quick presets (common V/div choices)
            presets_frame = ttk.Frame(ch_frame)
            presets_frame.pack(fill="x", pady=(6,0))
            for val in [0.1, 0.2, 0.5, 1, 2, 5]:
                b = ttk.Button(presets_frame, text=f"{val}", width=4, command=lambda v=val, e=vertical_scale_entry: e.delete(0,tk.END) or e.insert(0,str(v)))
                b.pack(side="left", padx=2)

            apply_btn = ttk.Button(ch_frame, text="Apply", command=lambda c=ch: self.apply_channel_settings(c))
            apply_btn.pack(side="right", pady=(6,0))

            self.channel_widgets[ch] = {
                "frame": ch_frame,
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
                "invert_var": invert_var,
                "apply_button": apply_btn,
                "state_label": state_label,
                "enabled": False,
            }

        self.output_title_label = ttk.Label(control_frame, text="Response / System Log:")
        self.output_title_label.pack(anchor="w", padx=5, pady=(0, 2))
        
        self.output_text = tk.Text(control_frame, state=tk.DISABLED, bg="#f4f4f4")
        self.output_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self.set_channel_controls_state(tk.DISABLED)
        self.is_running = False
        self.refresh_devices()

    # --- ฟังก์ชันการทำงาน (Event Handlers) ---
    def log_message(self, message):
        """ฟังก์ชันช่วยเหลือสำหรับพิมพ์ข้อความลงในกล่อง output เดียว"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def response_message(self, message):
        self.log_message(message)

    def parse_unit_value(self, value_str, unit, unit_map):
        try:
            value = float(value_str)
        except ValueError:
            raise
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

    def set_channel_controls_state(self, state):
        for widget_set in self.channel_widgets.values():
            widget_set["toggle"].config(state=state)
            widget_set["coupling"].config(state=state)
            widget_set["probe"].config(state=state)
            widget_set["vertical_scale_entry"].config(state=state)
            widget_set["vertical_unit"].config(state=state)
            widget_set["horizontal_scale_entry"].config(state=state)
            widget_set["horizontal_unit"].config(state=state)
            widget_set["vertical_position_entry"].config(state=state)
            widget_set["horizontal_position_entry"].config(state=state)
            widget_set["bandwidth"].config(state=state)
            widget_set["invert"].config(state=state)
            widget_set["apply_button"].config(state=state)

    def toggle_channel(self, channel):
        widget_set = self.channel_widgets[channel]
        if self.scope_controller.scope is None:
            self.log_message(f"[!] Connect the instrument before controlling CH{channel}.")
            return

        widget_set["enabled"] = not widget_set["enabled"]
        label = "ON" if widget_set["enabled"] else "OFF"
        widget_set["toggle"].config(text=label)
        widget_set["state_label"].config(text="Enabled" if widget_set["enabled"] else "Disabled")

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
            "vertical_scale": widget_set["vertical_scale_entry"].get(),
            "vertical_unit": widget_set["vertical_unit"].get(),
            "horizontal_scale": widget_set["horizontal_scale_entry"].get(),
            "horizontal_unit": widget_set["horizontal_unit"].get(),
            "vertical_position": widget_set["vertical_position_entry"].get(),
            "horizontal_position": widget_set["horizontal_position_entry"].get(),
            "coupling": widget_set["coupling"].get(),
            "probe": widget_set["probe"].get(),
            "bandwidth": widget_set["bandwidth"].get(),
            "invert": widget_set["invert_var"].get(),
        }

        def restore_previous_values():
            widget_set["vertical_scale_entry"].delete(0, tk.END)
            widget_set["vertical_scale_entry"].insert(0, previous_values["vertical_scale"])
            widget_set["vertical_unit"].set(previous_values["vertical_unit"])
            widget_set["horizontal_scale_entry"].delete(0, tk.END)
            widget_set["horizontal_scale_entry"].insert(0, previous_values["horizontal_scale"])
            widget_set["horizontal_unit"].set(previous_values["horizontal_unit"])
            widget_set["vertical_position_entry"].delete(0, tk.END)
            widget_set["vertical_position_entry"].insert(0, previous_values["vertical_position"])
            widget_set["horizontal_position_entry"].delete(0, tk.END)
            widget_set["horizontal_position_entry"].insert(0, previous_values["horizontal_position"])
            widget_set["coupling"].set(previous_values["coupling"])
            widget_set["probe"].set(previous_values["probe"])
            widget_set["bandwidth"].set(previous_values["bandwidth"])
            widget_set["invert_var"].set(previous_values["invert"])

        try:
            vertical_scale_value = self.parse_unit_value(
                widget_set["vertical_scale_entry"].get(),
                widget_set["vertical_unit"].get(),
                {"V/div": 1.0, "mV/div": 1e-3}
            )
            horizontal_scale_value = self.parse_unit_value(
                widget_set["horizontal_scale_entry"].get(),
                widget_set["horizontal_unit"].get(),
                {"s/div": 1.0, "ms/div": 1e-3, "us/div": 1e-6}
            )
            vertical_position = float(widget_set["vertical_position_entry"].get())
            horizontal_position = float(widget_set["horizontal_position_entry"].get())
            coupling_value = widget_set["coupling"].get().upper()
            probe_value = widget_set["probe"].get().replace("x", "")
            bandwidth_value = widget_set["bandwidth"].get().upper()
            invert_value = "ON" if widget_set["invert_var"].get() else "OFF"

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
            widget_set["toggle"].config(text="ON" if enabled else "OFF")
            widget_set["state_label"].config(text="Enabled" if enabled else "Disabled")

            coupling = self.scope_controller.query(f":CHANnel{channel}:COUPling?").strip().upper()
            if coupling in {"DC", "AC", "GND"}:
                widget_set["coupling"].set(coupling)

            probe_response = self.scope_controller.query(f":CHANnel{channel}:PROBe?").strip()
            if probe_response:
                probe_value = probe_response.replace("X", "").replace("x", "")
                if probe_value in {"1", "10", "100"}:
                    widget_set["probe"].set(f"{probe_value}x")

            scale_response = self.scope_controller.query(f":CHANnel{channel}:SCALe?").strip()
            if scale_response:
                scale_value = float(scale_response)
                display_value, display_unit = self.select_display_unit(
                    scale_value,
                    [("V/div", 1.0), ("mV/div", 1e-3)]
                )
                widget_set["vertical_unit"].set(display_unit)
                widget_set["vertical_scale_entry"].delete(0, tk.END)
                widget_set["vertical_scale_entry"].insert(0, self.format_float(display_value))

            offset_response = self.scope_controller.query(f":CHANnel{channel}:OFFSet?").strip()
            if offset_response:
                widget_set["vertical_position_entry"].delete(0, tk.END)
                widget_set["vertical_position_entry"].insert(0, self.format_float(float(offset_response)))

            timebase_scale = self.scope_controller.query(":TIMebase:SCALe?").strip()
            if timebase_scale:
                timebase_value = float(timebase_scale)
                display_value, display_unit = self.select_display_unit(
                    timebase_value,
                    [("s/div", 1.0), ("ms/div", 1e-3), ("us/div", 1e-6)]
                )
                widget_set["horizontal_unit"].set(display_unit)
                widget_set["horizontal_scale_entry"].delete(0, tk.END)
                widget_set["horizontal_scale_entry"].insert(0, self.format_float(display_value))

            timebase_offset = self.scope_controller.query(":TIMebase:OFFSet?").strip()
            if timebase_offset:
                widget_set["horizontal_position_entry"].delete(0, tk.END)
                widget_set["horizontal_position_entry"].insert(0, self.format_float(float(timebase_offset)))

            bandwidth_response = self.scope_controller.query(f":CHANnel{channel}:BANdwidth?").strip().upper()
            if bandwidth_response in {"FULL", "20M"}:
                widget_set["bandwidth"].set(bandwidth_response)

            invert_response = self.scope_controller.query(f":CHANnel{channel}:INVert?").strip().upper()
            widget_set["invert_var"].set(invert_response in {"1", "ON", "TRUE"})
        except Exception as e:
            self.log_message(f"[!] Unable to read current CH{channel} settings: {e}")

    def connect_scope(self):
        # กรณีที่ 1: ถ้าปุ่มเป็น DISCONNECT ให้ทำการตัดการเชื่อมต่อ
        if self.is_connected:
            self.scope_controller.disconnect()
            self.is_connected = False
            
            # อัปเดต UI กลับสู่สเตตเริ่มต้น
            self.connect_button.config(text="Connect")
            self.status_label.config(text="DISCONNECTED", foreground="red")
            self.log_message("[-------] Disconnected from device.")
            
            # ล็อกปุ่มอื่นๆ
            self.run_toggle_button.config(state=tk.DISABLED)
            self.send_button.config(state=tk.DISABLED)
            for btn in self.mode_buttons.values():
                btn.config(state=tk.DISABLED)
            self.trigger_offset_entry.config(state=tk.DISABLED)
            self.trigger_duty_entry.config(state=tk.DISABLED)
            self.trigger_apply_button.config(state=tk.DISABLED)
            self.set_channel_controls_state(tk.DISABLED)
            return

        # กรณีที่ 2: ถ้าปุ่มเป็น Connect ให้เริ่มทำการเชื่อมต่อ
        selected = self.device_combo.get()
        if selected == "Refresh devices" or not selected:
            selected = None

        try:
            self.scope_controller.connect(resource=selected)
            idn = self.scope_controller.get_idn()
            self.log_message(f"Connected to: {idn}")
            self.response_message(f"Connected to: {idn}")
            
            self.is_connected = True
            self.connect_button.config(text="Disconnect")
            self.status_label.config(text=f"{idn}", foreground="#4CAF50")
            
            # ปลดล็อกปุ่มควบคุมระบบหลัก
            self.run_toggle_button.config(state=tk.NORMAL)
            self.send_button.config(state=tk.NORMAL)
            for btn in self.mode_buttons.values():
                btn.config(state=tk.NORMAL)
            self.trigger_offset_entry.config(state=tk.NORMAL)
            self.trigger_duty_entry.config(state=tk.NORMAL)
            self.trigger_apply_button.config(state=tk.NORMAL)
            self.set_channel_controls_state(tk.NORMAL)
            for channel in self.channel_widgets:
                self.populate_channel_settings(channel)
            self.populate_trigger_settings()
            
        except RuntimeError as e:
            messagebox.showerror("Connection Error", str(e))

    def toggle_run_stop(self):
        if not self.is_running:
            try:
                self.scope_controller.run()
                self.is_running = True
                self.run_toggle_button.config(text="Stop")
                self.log_message("Command executed: :RUN")
                self.response_message("Command executed: :RUN")
            except RuntimeError as e:
                messagebox.showerror("Error", str(e))
        else:
            try:
                self.scope_controller.stop()
                self.is_running = False
                self.run_toggle_button.config(text="Run")
                self.log_message("Command executed: :STOP")
                self.response_message("Command executed: :STOP")
            except RuntimeError as e:
                messagebox.showerror("Error", str(e))

    def send_command(self):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.append_history(cmd)
            
        try:
            self.log_message(f"> Sending: {cmd}")
            self.response_message(f"> Sending: {cmd}")
            # ตรวจสอบว่าเป็นคำสั่งที่ต้องการคำตอบหรือไม่ (มีเครื่องหมาย ?)
            if "?" in cmd:
                response = self.scope_controller.query(cmd)
                self.log_message(f"< Response: {response}")
                self.response_message(f"< Response: {response}")
            else:
                self.scope_controller.write(cmd)
                self.log_message("< Success (No response expected)")
                self.response_message("< Success (No response expected)")
        except Exception as e:
            self.log_message(f"[!] Error: {e}")
            self.response_message(f"[!] Error: {e}")

    def append_history(self, command):
        if command in self.command_history:
            self.command_history.remove(command)
        self.command_history.insert(0, command)
        if len(self.command_history) > self.max_history_entries:
            self.command_history = self.command_history[: self.max_history_entries]
        self.history_listbox.delete(0, tk.END)
        for entry in self.command_history:
            self.history_listbox.insert(tk.END, entry)

    def on_history_select(self, event):
        # Show selected command in the entry field when a history item is selected
        selection = self.history_listbox.curselection()
        if selection:
            command = self.history_listbox.get(selection[0])
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, command)

    def on_history_activate(self, event):
        # Double-click a history item to resend it immediately
        selection = self.history_listbox.curselection()
        if selection:
            command = self.history_listbox.get(selection[0])
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, command)
            self.send_command()

    def clear_history(self):
        self.command_history.clear()
        self.history_listbox.delete(0, tk.END)

    def clear_output(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

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
            offset_value = float(self.trigger_offset_entry.get())
            duty_value = float(self.trigger_duty_entry.get())
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
                self.trigger_offset_entry.delete(0, tk.END)
                self.trigger_offset_entry.insert(0, self.format_float(float(offset_response)))

            duty_response = self.scope_controller.query(":TRIGger:DUTY?").strip()
            if duty_response:
                self.trigger_duty_entry.delete(0, tk.END)
                self.trigger_duty_entry.insert(0, self.format_float(float(duty_response)))
        except Exception as e:
            self.log_message(f"[!] Unable to read trigger settings: {e}")

    def refresh_devices(self):
        try:
            devices = self.scope_controller.list_usb_resources()
            if not devices:
                self.device_combo['values'] = []
                self.device_combo.set("No USB devices")
                return
            self.device_combo['values'] = devices
            self.device_combo.set(devices[0])
            self.log_message(f"Found {len(devices)} USB device(s)")
        except Exception as e:
            messagebox.showerror("Refresh Error", str(e))
            self.device_combo['values'] = []
            self.device_combo.set("No USB devices")


if __name__ == "__main__":
    app = ScopeApp()
    app.mainloop()