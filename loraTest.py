#!/usr/bin/env python3
import threading
import time
import sys
from datetime import datetime
import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

DEFAULT_BAUDS = [4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800]

class SerialModule:
    def __init__(self, name, text_widget, log_file):
        self.name = name
        self.text_widget = text_widget
        self.log_file = log_file
        self.ser = None
        self.thread = None
        self.running = False
        self.lock = threading.Lock()

    def open(self, port, baud):
        with self.lock:
            self.close()
            try:
                self.ser = serial.Serial(port=port, baudrate=int(baud), timeout=0.2)
                self.running = True
            except Exception as e:
                self.ser = None
                raise e
        self.thread = threading.Thread(target=self.read_loop, daemon=True)
        self.thread.start()

    def close(self):
        with self.lock:
            self.running = False
            if self.ser is not None and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None

    def read_loop(self):
        while True:
            with self.lock:
                if not self.running or self.ser is None:
                    break
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.readline()
                else:
                    data = self.ser.read(256)
                if data:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    text = data.decode(errors="replace").rstrip("\r\n")
                    if text != "":
                        line = f"{timestamp} | {text}"
                        self.append_line(line)
            except Exception as e:
                self.append_line(f"ERROR: {e}")
                break
            time.sleep(0.01)

    def append_line(self, line):
        def inner():
            self.text_widget.configure(state="normal")
            self.text_widget.insert(tk.END, line + "\n")
            self.text_widget.see(tk.END)
            self.text_widget.configure(state="disabled")
        self.text_widget.after(0, inner)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("DTDS-622 Dual Logger")
        self.root.geometry("1000x700")
        self.serial1 = None
        self.serial2 = None
        self.create_ui()

    def get_ports(self):
        ports = serial.tools.list_ports.comports()
        names = [p.device for p in ports]
        # Add typical Linux usb-to-ttl names if missing
        if "/dev/ttyUSB0" not in names and "/dev/ttyUSB1" not in names:
            for n in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"]:
                if n not in names:
                    names.append(n)
        return names

    def create_module_frame(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        # Row 0 controls
        row = 0
        ttk.Label(frame, text="Port:").grid(row=row, column=0, sticky="w")
        port_cb = ttk.Combobox(frame, values=self.get_ports(), width=22)
        port_cb.grid(row=row, column=1, sticky="w", padx=4)
        if port_cb["values"]:
            port_cb.set(port_cb["values"][0])
        ttk.Label(frame, text="Baud:").grid(row=row, column=2, sticky="w", padx=(10,0))
        baud_cb = ttk.Combobox(frame, values=DEFAULT_BAUDS, width=10)
        baud_cb.grid(row=row, column=3, sticky="w")
        baud_cb.set(115200)
        ttk.Label(frame, text="Freq:").grid(row=row, column=4, sticky="w", padx=(10,0))
        freq_cb = ttk.Combobox(frame, values=["815", "868", "433", "902", "450"], width=8)
        freq_cb.grid(row=row, column=5, sticky="w")
        freq_cb.set("868")
        return frame, port_cb, baud_cb, freq_cb

    def create_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x", expand=False)

        module_top = ttk.Frame(top)
        module_top.pack(fill="x", expand=False)

        # Module 1
        self.mod1_frame, self.mod1_port, self.mod1_baud, self.mod1_freq = self.create_module_frame(module_top, "Module 1")
        self.mod1_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=2)
        # Module 2
        self.mod2_frame, self.mod2_port, self.mod2_baud, self.mod2_freq = self.create_module_frame(module_top, "Module 2")
        self.mod2_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=2)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", pady=6)
        self.connect_btn = ttk.Button(btn_frame, text="Connect", command=self.connect_all)
        self.connect_btn.pack(side="left", padx=4)
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect", command=self.disconnect_all, state="disabled")
        self.disconnect_btn.pack(side="left", padx=4)
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Ports", command=self.refresh_ports)
        self.refresh_btn.pack(side="left", padx=4)

        cont = ttk.Frame(self.root, padding=8)
        cont.pack(fill="both", expand=True)

        display1 = ttk.LabelFrame(cont, text="Module 1 RX", padding=5)
        display2 = ttk.LabelFrame(cont, text="Module 2 RX", padding=5)
        display1.pack(side="left", fill="both", expand=True, padx=4, pady=2)
        display2.pack(side="left", fill="both", expand=True, padx=4, pady=2)

        self.text1 = ScrolledText(display1, height=25, state="disabled", wrap="none")
        self.text1.pack(fill="both", expand=True)
        self.text2 = ScrolledText(display2, height=25, state="disabled", wrap="none")
        self.text2.pack(fill="both", expand=True)

    def refresh_ports(self):
        ports = self.get_ports()
        for cb in [self.mod1_port, self.mod2_port]:
            cb["values"] = ports
            if not cb.get() and ports:
                cb.set(ports[0])
        messagebox.showinfo("Ports Refreshed", "Serial ports list refreshed.")

    def connect_all(self):
        p1 = self.mod1_port.get().strip()
        b1 = self.mod1_baud.get().strip()
        p2 = self.mod2_port.get().strip()
        b2 = self.mod2_baud.get().strip()
        if not p1 or not b1 or not p2 or not b2:
            messagebox.showerror("Missing Info", "Please select port and baud for both modules.")
            return

        self.disconnect_all()

        self.text1.configure(state="normal"); self.text1.delete("1.0", tk.END); self.text1.configure(state="disabled")
        self.text2.configure(state="normal"); self.text2.delete("1.0", tk.END); self.text2.configure(state="disabled")

        self.serial1 = SerialModule("Module 1", self.text1, "module1_rx.log")
        self.serial2 = SerialModule("Module 2", self.text2, "module2_rx.log")
        errors = []
        try:
            self.serial1.open(p1, b1)
        except Exception as e:
            errors.append(f"Module1: {e}")
            self.serial1 = None
        try:
            self.serial2.open(p2, b2)
        except Exception as e:
            errors.append(f"Module2: {e}")
            self.serial2 = None

        if errors:
            messagebox.showerror("Connect errors", "\n".join(errors))
        else:
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")

    def disconnect_all(self):
        for s in [self.serial1, self.serial2]:
            if s:
                s.close()
        self.serial1 = None
        self.serial2 = None
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")

    def on_close(self):
        self.disconnect_all()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()