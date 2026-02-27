import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import sys

APP_TITLE = "PYNQ Professional Manager"
DEFAULT_BAUD = 115200


class SerialManager:
    def __init__(self, output_callback):
        self.ser = None
        self.running = False
        self.output_callback = output_callback

    def connect(self, port, baud):
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.running = True
            threading.Thread(target=self.read_loop, daemon=True).start()
            return True, f"Connected to {port} @ {baud}"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        return "Disconnected"

    def read_loop(self):
        while self.running:
            try:
                if self.ser and self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting).decode(errors="ignore")
                    self.output_callback(data)
            except:
                pass
            time.sleep(0.05)

    def send(self, data):
        if self.ser and self.ser.is_open:
            self.ser.write(data.encode())


class PynqGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x650")
        self.root.configure(bg="#0f172a")

        self.serial_manager = SerialManager(self.append_output)

        self.mode = tk.StringVar(value="terminal")
        self.create_ui()
        self.refresh_ports()

    # ================= UI ================= #

    def create_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=4)

        # ===== Top Bar =====
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(top_frame, text="COM Port").pack(side="left")
        self.port_combo = ttk.Combobox(top_frame, width=15)
        self.port_combo.pack(side="left", padx=5)

        ttk.Button(top_frame, text="Refresh", command=self.refresh_ports).pack(side="left", padx=5)

        ttk.Label(top_frame, text="Baudrate").pack(side="left", padx=10)
        self.baud_combo = ttk.Combobox(top_frame, width=10)
        self.baud_combo["values"] = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        self.baud_combo.set("115200")
        self.baud_combo.pack(side="left")

        self.connect_btn = ttk.Button(top_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=10)

        # ===== Mode Selection =====
        mode_frame = ttk.LabelFrame(self.root, text="Mode Selection")
        mode_frame.pack(fill="x", padx=10)

        ttk.Radiobutton(mode_frame, text="Terminal Mode", variable=self.mode, value="terminal").pack(side="left", padx=20)
        ttk.Radiobutton(mode_frame, text="AutoFlash Network Config", variable=self.mode, value="flash").pack(side="left")

        # ===== Terminal Output =====
        self.output = scrolledtext.ScrolledText(
            self.root,
            bg="#111827",
            fg="#00ffcc",
            insertbackground="white",
            font=("Consolas", 11)
        )
        self.output.pack(expand=True, fill="both", padx=10, pady=10)

        # ===== Command Entry =====
        cmd_frame = ttk.Frame(self.root)
        cmd_frame.pack(fill="x", padx=10)

        self.cmd_entry = ttk.Entry(cmd_frame)
        self.cmd_entry.pack(side="left", fill="x", expand=True)
        self.cmd_entry.bind("<Return>", lambda e: self.send_terminal())

        ttk.Button(cmd_frame, text="Send", command=self.send_terminal).pack(side="left", padx=5)

        # ===== Flash Config Panel =====
        flash_frame = ttk.LabelFrame(self.root, text="Network Configuration")
        flash_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(flash_frame, text="Interface").grid(row=0, column=0, padx=5, pady=5)
        self.iface_entry = ttk.Entry(flash_frame)
        self.iface_entry.insert(0, "eth0")
        self.iface_entry.grid(row=0, column=1)

        self.ip_mode = tk.StringVar(value="dhcp")
        ttk.Radiobutton(flash_frame, text="DHCP", variable=self.ip_mode, value="dhcp").grid(row=0, column=2)
        ttk.Radiobutton(flash_frame, text="Static", variable=self.ip_mode, value="static").grid(row=0, column=3)

        ttk.Label(flash_frame, text="Static IP").grid(row=1, column=0)
        self.static_ip = ttk.Entry(flash_frame)
        self.static_ip.grid(row=1, column=1)

        ttk.Label(flash_frame, text="Gateway").grid(row=1, column=2)
        self.gateway = ttk.Entry(flash_frame)
        self.gateway.grid(row=1, column=3)

        ttk.Button(flash_frame, text="Flash Config", command=self.auto_flash).grid(row=2, column=0, columnspan=4, pady=8)

    # ================= Serial ================= #

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)

    def toggle_connection(self):
        if self.serial_manager.running:
            msg = self.serial_manager.disconnect()
            self.connect_btn.config(text="Connect")
            self.append_output("\n" + msg + "\n")
        else:
            port = self.port_combo.get()

            if not port:
                messagebox.showerror("Error", "Select COM port")
                return

            if self.mode.get() == "flash":
                baud = DEFAULT_BAUD  # Force 115200
                self.baud_combo.set("115200")
            else:
                baud = int(self.baud_combo.get())

            success, msg = self.serial_manager.connect(port, baud)

            if success:
                self.connect_btn.config(text="Disconnect")
            else:
                messagebox.showerror("Connection Error", msg)

            self.append_output(msg + "\n")

    def append_output(self, text):
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    # ================= Terminal ================= #

    def send_terminal(self):
        if self.mode.get() != "terminal":
            return

        cmd = self.cmd_entry.get()
        if cmd.strip():
            self.serial_manager.send(cmd + "\n")
            self.cmd_entry.delete(0, tk.END)

    # ================= AutoFlash ================= #

    def auto_flash(self):
        if self.mode.get() != "flash":
            messagebox.showinfo("Info", "Switch to AutoFlash Mode")
            return

        iface = self.iface_entry.get()

        if self.ip_mode.get() == "dhcp":
            config = f"""sudo bash -c 'cat > /etc/network/interfaces <<EOF
auto lo
iface lo inet loopback

auto {iface}
iface {iface} inet dhcp
EOF'"""
        else:
            ip = self.static_ip.get()
            gw = self.gateway.get()

            if not ip or not gw:
                messagebox.showerror("Error", "Enter Static IP and Gateway")
                return

            config = f"""sudo bash -c 'cat > /etc/network/interfaces <<EOF
auto lo
iface lo inet loopback

auto {iface}
iface {iface} inet static
    address {ip}
    gateway {gw}
EOF'"""

        self.serial_manager.send(config + "\n")
        self.append_output("\nNetwork configuration flashed.\n")


if __name__ == "__main__":
    root = tk.Tk()
    app = PynqGUI(root)
    root.mainloop()
