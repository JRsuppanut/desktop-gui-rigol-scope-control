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
        self.geometry("1000x700")
        self.scope_controller = ScopeController()
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
        
        button_row = ttk.Frame(control_frame)
        button_row.pack(fill="x", pady=(0, 8))

        self.run_toggle_button = ttk.Button(button_row, text="Run", command=self.toggle_run_stop, state=tk.DISABLED)
        self.run_toggle_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(button_row, text="Clear Output", command=self.clear_output)
        self.clear_button.pack(side="left", padx=5)

        channel_frame = ttk.LabelFrame(control_frame, text="Channel Controls", padding=10)
        channel_frame.pack(fill="x", pady=(0, 10))
        channel_frame.columnconfigure(0, weight=1)

        self.channel_widgets = {}
        for ch in range(1, 5):
            row_frame = ttk.Frame(channel_frame)
            row_frame.pack(fill="x", pady=2)

            ttk.Label(row_frame, text=f"CH{ch}:").pack(side="left", padx=(0, 6))

            toggle_btn = ttk.Button(row_frame, text="OFF", width=8, command=lambda c=ch: self.toggle_channel(c))
            toggle_btn.pack(side="left", padx=(0, 6))

            ttk.Label(row_frame, text="Coupling:").pack(side="left", padx=(6, 2))
            coupling_var = tk.StringVar(value="DC")
            coupling_box = ttk.Combobox(row_frame, textvariable=coupling_var, values=["DC", "AC", "GND"], width=7, state="readonly")
            coupling_box.pack(side="left", padx=2)

            ttk.Label(row_frame, text="Probe:").pack(side="left", padx=(6, 2))
            probe_var = tk.StringVar(value="10x")
            probe_box = ttk.Combobox(row_frame, textvariable=probe_var, values=["1x", "10x", "100x"], width=7, state="readonly")
            probe_box.pack(side="left", padx=2)

            ttk.Label(row_frame, text="Scale:").pack(side="left", padx=(6, 2))
            scale_var = tk.StringVar(value="1.0")
            scale_entry = ttk.Entry(row_frame, textvariable=scale_var, width=8)
            scale_entry.pack(side="left", padx=2)

            ttk.Label(row_frame, text="Offset:").pack(side="left", padx=(6, 2))
            offset_var = tk.StringVar(value="0.0")
            offset_entry = ttk.Entry(row_frame, textvariable=offset_var, width=8)
            offset_entry.pack(side="left", padx=2)

            ttk.Label(row_frame, text="BW:").pack(side="left", padx=(6, 2))
            bandwidth_var = tk.StringVar(value="FULL")
            bandwidth_box = ttk.Combobox(row_frame, textvariable=bandwidth_var, values=["FULL", "20M"], width=7, state="readonly")
            bandwidth_box.pack(side="left", padx=2)

            invert_var = tk.BooleanVar(value=False)
            invert_check = ttk.Checkbutton(row_frame, text="Invert", variable=invert_var)
            invert_check.pack(side="left", padx=(6, 2))

            apply_btn = ttk.Button(row_frame, text="Apply", command=lambda c=ch: self.apply_channel_settings(c))
            apply_btn.pack(side="left", padx=(6, 0))

            state_label = ttk.Label(row_frame, text="Disabled")
            state_label.pack(side="left", padx=(10, 0))

            self.channel_widgets[ch] = {
                "toggle": toggle_btn,
                "coupling": coupling_box,
                "probe": probe_box,
                "scale_entry": scale_entry,
                "offset_entry": offset_entry,
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

    def set_channel_controls_state(self, state):
        for widget_set in self.channel_widgets.values():
            widget_set["toggle"].config(state=state)
            widget_set["coupling"].config(state=state)
            widget_set["probe"].config(state=state)
            widget_set["scale_entry"].config(state=state)
            widget_set["offset_entry"].config(state=state)
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

        try:
            scale_value = float(widget_set["scale_entry"].get())
            offset_value = float(widget_set["offset_entry"].get())
            coupling_value = widget_set["coupling"].get().upper()
            probe_value = widget_set["probe"].get().replace("x", "")
            bandwidth_value = widget_set["bandwidth"].get().upper()
            invert_value = "ON" if widget_set["invert_var"].get() else "OFF"

            self.scope_controller.write(f":CHANnel{channel}:COUPling {coupling_value}")
            self.scope_controller.write(f":CHANnel{channel}:PROBe {probe_value}")
            self.scope_controller.write(f":CHANnel{channel}:SCALe {scale_value}")
            self.scope_controller.write(f":CHANnel{channel}:OFFSet {offset_value}")
            self.scope_controller.write(f":CHANnel{channel}:BANdwidth {bandwidth_value}")
            self.scope_controller.write(f":CHANnel{channel}:INVert {invert_value}")
            self.log_message(f"CH{channel} settings applied")
        except ValueError:
            self.log_message(f"[!] Invalid numeric value for CH{channel}")
        except Exception as e:
            self.log_message(f"[!] Error setting CH{channel} parameters: {e}")

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
                widget_set["scale_entry"].delete(0, tk.END)
                widget_set["scale_entry"].insert(0, scale_response)

            offset_response = self.scope_controller.query(f":CHANnel{channel}:OFFSet?").strip()
            if offset_response:
                widget_set["offset_entry"].delete(0, tk.END)
                widget_set["offset_entry"].insert(0, offset_response)

            bandwidth_response = self.scope_controller.query(f":CHANnel{channel}:BANdwidth?").strip().upper()
            if bandwidth_response in {"FULL", "20M"}:
                widget_set["bandwidth"].set(bandwidth_response)

            invert_response = self.scope_controller.query(f":CHANnel{channel}:INVert?").strip().upper()
            widget_set["invert_var"].set(invert_response in {"1", "ON", "TRUE"})
        except Exception as e:
            self.log_message(f"[!] Unable to read current CH{channel} settings: {e}")

    def connect_scope(self):
        # กรณีที่ 1: ถ้าปุ่มเป็น DISCONNECT ให้ทำการตัดการเชื่อมต่อ
        if self.connect_button.cget("text") == "DISCONNECT":
            self.scope_controller.disconnect()
            
            # อัปเดต UI กลับสู่สเตตเริ่มต้น
            self.connect_button.config(text="Connect")
            self.status_label.config(text="DISCONNECTED", foreground="red")
            self.log_message("[-------] Disconnected from device.")
            
            # ล็อกปุ่มอื่นๆ
            self.run_toggle_button.config(state=tk.DISABLED)
            self.send_button.config(state=tk.DISABLED)
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
            
            self.connect_button.config(text="Disconnect")
            self.status_label.config(text=f"{idn}", foreground="#4CAF50")
            
            # ปลดล็อกปุ่มควบคุมระบบหลัก
            self.run_toggle_button.config(state=tk.NORMAL)
            self.send_button.config(state=tk.NORMAL)
            self.set_channel_controls_state(tk.NORMAL)
            for channel in self.channel_widgets:
                self.populate_channel_settings(channel)
            
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

    def clear_output(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

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