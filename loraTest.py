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
        self.lock = threading.RLock()

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

    def send_at(self, cmd, timeout=1.0, expect_ok=True):
        with self.lock:
            if self.ser is None or not self.ser.is_open:
                raise RuntimeError("Serial port is not open")
            cmd_line = cmd.strip() + "\r\n"
            self.ser.reset_input_buffer()
            self.ser.write(cmd_line.encode())
            self.ser.flush()
            self.append_line(f"AT SENT: {cmd.strip()}")
            start = time.time()

            collected = []
            while time.time() - start < timeout:
                line = self.ser.readline()
                if not line:
                    continue
                try:
                    text = line.decode(errors="replace").strip()
                except Exception:
                    text = repr(line)
                if text:
                    self.append_line(f"AT> {text}")
                    collected.append(text)
                    if expect_ok and text in ("OK", "ERROR"):
                        break
            return "\n".join(collected)

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
        ttk.Label(frame, text="Freq (MHz):").grid(row=row, column=4, sticky="w", padx=(10,0))
        freq_cb = ttk.Combobox(frame, values=["815", "868", "433", "902", "450"], width=8)
        freq_cb.grid(row=row, column=5, sticky="w")
        freq_cb.set("868")
        row += 1
        ttk.Label(frame, text="Recv Mode:").grid(row=row, column=0, sticky="w", pady=(4,0))
        recv_mode_cb = ttk.Combobox(frame, values=["0", "1"], width=4)
        recv_mode_cb.grid(row=row, column=1, sticky="w", pady=(4,0))
        recv_mode_cb.set("0")
        ttk.Label(frame, text="Recv Verbose:").grid(row=row, column=2, sticky="w", padx=(10,0), pady=(4,0))
        recv_verbose_cb = ttk.Combobox(frame, values=["0", "1"], width=4)
        recv_verbose_cb.grid(row=row, column=3, sticky="w", pady=(4,0))
        recv_verbose_cb.set("1")
        ttk.Label(frame, text="Init AT:").grid(row=row, column=4, sticky="w", pady=(4,0))
        init_at = ttk.Entry(frame, width=26)
        init_at.grid(row=row, column=5, sticky="w", pady=(4,0))
        init_at.insert(0, "AT")
        ttk.Label(frame, text="Freq AT:").grid(row=row, column=2, sticky="w", padx=(10,0), pady=(4,0))
        freq_at = ttk.Entry(frame, width=22)
        freq_at.grid(row=row, column=3, sticky="w", pady=(4,0))
        freq_at.insert(0, "AT+FREQ={freq}")
        ttk.Label(frame, text="Send AT:").grid(row=row, column=4, sticky="w", padx=(10,0), pady=(4,0))
        send_at = ttk.Entry(frame, width=22)
        send_at.grid(row=row, column=5, sticky="w", pady=(4,0))
        send_at.insert(0, "AT")
        return frame, port_cb, baud_cb, freq_cb, recv_mode_cb, recv_verbose_cb, init_at, freq_at, send_at

    def create_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x", expand=False)

        module_top = ttk.Frame(top)
        module_top.pack(fill="x", expand=False)

        # Module 1
        self.mod1_frame, self.mod1_port, self.mod1_baud, self.mod1_freq, self.mod1_recv_mode, self.mod1_recv_verbose, self.mod1_init_at, self.mod1_freq_at, self.mod1_send_at = self.create_module_frame(module_top, "Module 1")
        self.mod1_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=2)
        # Module 2
        self.mod2_frame, self.mod2_port, self.mod2_baud, self.mod2_freq, self.mod2_recv_mode, self.mod2_recv_verbose, self.mod2_init_at, self.mod2_freq_at, self.mod2_send_at = self.create_module_frame(module_top, "Module 2")
        self.mod2_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=2)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", pady=6)
        self.connect_btn = ttk.Button(btn_frame, text="Connect", command=self.connect_all)
        self.connect_btn.pack(side="left", padx=4)
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect", command=self.disconnect_all, state="disabled")
        self.disconnect_btn.pack(side="left", padx=4)
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Ports", command=self.refresh_ports)
        self.refresh_btn.pack(side="left", padx=4)
        self.send_at_btn = ttk.Button(btn_frame, text="Send AT now", command=self.send_manual_at)
        self.send_at_btn.pack(side="left", padx=4)

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

    def freq_mhz_to_hz(self, freq_text):
        try:
            f = float(freq_text)
            if f < 1000:
                return int(f * 1_000_000)
            return int(f)
        except Exception:
            return None

    def initialize_dtds_module(self, module, freq_text, recv_mode, recv_verbose):
        if module is None:
            return
        freq_hz = self.freq_mhz_to_hz(freq_text)
        if freq_hz is None:
            module.append_line(f"INIT ERROR: invalid frequency '{freq_text}'")
            return
        recv_mode = str(recv_mode).strip() or "0"
        recv_verbose = str(recv_verbose).strip() or "1"
        if recv_mode not in ("0", "1"):
            recv_mode = "0"
        if recv_verbose not in ("0", "1"):
            recv_verbose = "1"
        try:
            module.send_at("AT", timeout=1.0)
            module.send_at("AT+RESET", timeout=2.0)
            module.send_at("ATE0", timeout=1.0)
            module.send_at("ATV1", timeout=1.0)
            module.send_at("AT+MODEM=1", timeout=1.0)
            module.send_at(f"AT+FREQ={freq_hz}", timeout=1.0)
            module.send_at("AT+LMCFG=7,0,1", timeout=1.0)
            module.send_at("AT+LPCFG=8,0,1,0,0", timeout=1.0)
            module.send_at("AT+LBT=1,-80,10,0", timeout=1.0)
            module.send_at("AT+TXPWR=22", timeout=1.0)
            module.send_at(f"AT+RECV={recv_mode},{recv_verbose}", timeout=1.0)
            module.append_line("DTDS initialization sequence complete.")
        except Exception as e:
            module.append_line(f"INIT ERROR: {e}")

    def send_init_commands(self, module, init_at, freq_at, freq_value):
        if module is None:
            return
        try:
            if init_at.strip():
                module.send_at(init_at.strip(), timeout=1.0)
            if freq_at.strip():
                cmd = freq_at.strip().replace("{freq}", str(freq_value))
                module.send_at(cmd, timeout=1.0)
        except Exception as e:
            module.append_line(f"INIT ERROR: {e}")

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

        if not errors:
            # Asynchronous initialization to keep GUI responsive
            if self.serial1:
                threading.Thread(
                    target=self.initialize_dtds_module,
                    args=(
                        self.serial1,
                        self.mod1_freq.get(),
                        self.mod1_recv_mode.get(),
                        self.mod1_recv_verbose.get(),
                    ),
                    daemon=True,
                ).start()
            if self.serial2:
                threading.Thread(
                    target=self.initialize_dtds_module,
                    args=(
                        self.serial2,
                        self.mod2_freq.get(),
                        self.mod2_recv_mode.get(),
                        self.mod2_recv_verbose.get(),
                    ),
                    daemon=True,
                ).start()
        else:
            # If any connect error, close all
            self.disconnect_all()

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

    def send_manual_at(self):
        if self.serial1:
            try:
                self.serial1.send_at(self.mod1_send_at.get())
            except Exception as e:
                self.serial1.append_line(f"SEND AT ERROR: {e}")
        if self.serial2:
            try:
                self.serial2.send_at(self.mod2_send_at.get())
            except Exception as e:
                self.serial2.append_line(f"SEND AT ERROR: {e}")

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