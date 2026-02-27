import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import paramiko
import re

BAUDRATE = 115200

class PynqManager:
    def __init__(self, root):
        self.root = root
        self.root.title("PYNQ Network Manager")
        self.root.geometry("750x550")

        self.create_widgets()
        self.refresh_ports()

    def create_widgets(self):
        frame = ttk.Frame(self.root)
        frame.pack(pady=10)

        ttk.Label(frame, text="COM Port:").grid(row=0, column=0, padx=5)

        self.port_combo = ttk.Combobox(frame, width=20)
        self.port_combo.grid(row=0, column=1)

        ttk.Button(frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=5)

        ttk.Label(frame, text="Username:").grid(row=1, column=0)
        self.username = ttk.Entry(frame)
        self.username.insert(0, "xilinx")
        self.username.grid(row=1, column=1)

        ttk.Label(frame, text="Password:").grid(row=2, column=0)
        self.password = ttk.Entry(frame, show="*")
        self.password.insert(0, "xilinx")
        self.password.grid(row=2, column=1)

        ttk.Button(frame, text="Run Auto Setup", command=self.start_thread).grid(row=3, column=0, columnspan=3, pady=10)

        self.log_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD)
        self.log_area.pack(expand=True, fill='both')

    def log(self, text):
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)

    def start_thread(self):
        thread = threading.Thread(target=self.run_setup)
        thread.start()

    def expect_login(self, ser, username, password):
        buffer = ""
        start_time = time.time()

        while time.time() - start_time < 20:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting).decode(errors='ignore')
                buffer += data
                self.log(data.strip())

                if "login:" in buffer:
                    ser.write((username + "\n").encode())
                    buffer = ""

                elif "Password:" in buffer:
                    ser.write((password + "\n").encode())
                    buffer = ""

                elif "$" in buffer or "#" in buffer:
                    return True
            time.sleep(0.5)
        return False

    def run_setup(self):
        port = self.port_combo.get()
        username = self.username.get()
        password = self.password.get()

        if not port:
            messagebox.showerror("Error", "No COM port selected")
            return

        try:
            self.log("[*] Connecting to serial...")
            ser = serial.Serial(port, BAUDRATE, timeout=1)
            time.sleep(2)

            logged_in = self.expect_login(ser, username, password)

            if not logged_in:
                self.log("[!] Login failed")
                return

            self.log("[*] Setting DHCP...")

            dhcp_script = """sudo bash -c 'cat > /etc/network/interfaces <<EOF
auto lo
iface lo inet loopback

auto eth0
allow-hotplug eth0
iface eth0 inet dhcp
EOF'"""

            ser.write((dhcp_script + "\n").encode())
            time.sleep(2)
            ser.write((password + "\n").encode())
            time.sleep(2)

            ser.write(b"sudo systemctl restart networking || sudo service networking restart\n")
            time.sleep(5)

            ser.write(b"ip -4 addr show eth0\n")
            time.sleep(3)

            output = ser.read_all().decode(errors="ignore")
            self.log(output)

            ip_match = re.search(r'\b\d+\.\d+\.\d+\.\d+\b', output)

            if ip_match:
                ip_addr = ip_match.group()
                self.log(f"[+] IP detected: {ip_addr}")
                ser.close()
                self.ssh_fallback(ip_addr, username, password)
            else:
                self.log("[!] No IP detected")

        except Exception as e:
            self.log(str(e))

    def ssh_fallback(self, ip, username, password):
        self.log("[*] Switching to SSH...")

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password, timeout=10)

            self.log("[+] SSH Connected")

            stdin, stdout, stderr = ssh.exec_command("sudo apt update -y")
            stdout.channel.recv_exit_status()
            self.log(stdout.read().decode())

            stdin, stdout, stderr = ssh.exec_command("sudo apt upgrade -y")
            stdout.channel.recv_exit_status()
            self.log(stdout.read().decode())

            ssh.close()
            self.log("[✔] Setup Complete")

        except Exception as e:
            self.log(f"[!] SSH failed: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = PynqManager(root)
    root.mainloop()
