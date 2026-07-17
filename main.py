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
        
        # 1. สร้าง Frame ย่อยแถวบน เพื่อให้จัดเรียงซ้ายขวาได้อิสระ
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
        
        # 2. สร้าง Frame ย่อยแถวล่าง สำหรับการแสดง Status เพื่อให้ขึ้นบรรทัดใหม่
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
        
        self.clear_button = ttk.Button(button_row, text="Clear Response", command=self.clear_response)
        self.clear_button.pack(side="left", padx=5)
        
        self.response_title_label = ttk.Label(control_frame, text="Response:")
        self.response_title_label.pack(anchor="w", padx=5, pady=(10, 2))
        
        self.response_text = tk.Text(control_frame, state=tk.DISABLED, bg="#f4f4f4")
        self.response_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        # ---  ส่วนที่ 4: กล่องแสดงผล (System Log) ---
        log_frame = ttk.LabelFrame(main_frame, text="System Log", padding=10)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, state=tk.DISABLED, bg="#f4f4f4")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        clear_log_button = ttk.Button(log_frame, text="Clear Log", command=self.clear_log)
        clear_log_button.grid(row=1, column=0, pady=5)
        
        self.is_running = False
        self.refresh_devices()

    # --- ฟังก์ชันการทำงาน (Event Handlers) ---
    def log_message(self, message):
        """ฟังก์ชันช่วยเหลือสำหรับพิมพ์ข้อความลงในกล่อง Log"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def response_message(self, message):
        """ฟังก์ชันช่วยเหลือสำหรับพิมพ์ข้อความลงในกล่อง Response"""
        self.response_text.config(state=tk.NORMAL)
        self.response_text.insert(tk.END, message + "\n")
        self.response_text.see(tk.END)
        self.response_text.config(state=tk.DISABLED)

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

    def clear_response(self):
        self.response_text.config(state=tk.NORMAL)
        self.response_text.delete(1.0, tk.END)
        self.response_text.config(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

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