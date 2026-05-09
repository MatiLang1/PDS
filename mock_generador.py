"""
Mock del generador de ondas + Arduino, para inyectar señales por COM5
y que main.py las lea desde COM4 (par virtual com0com COM4↔COM5).

Emula lo que vería main.py si el Arduino real estuviera mandando: una
muestra ASCII por línea (`f"{0..255}\n"`) a ~1 kHz.

Convención de amplitud:
    Lo que el Arduino lee en A0 va de 0.7 V a 4.7 V (rango útil del ADC
    después del AmpOp inversor). Como el ADC es 8 bit (0..255 ↔ 0..5V):
        0.7 V → raw ≈ 36
        4.7 V → raw ≈ 240
    main.py invierte el AmpOp con: val_volts = 6 - (raw/255)*12
    Así que raw=36 → ~+4.3V en el dominio del generador,
            raw=240 → ~-5.3V. Centro en raw=138 → ~0V.

Controles en la GUI:
    - Forma: Senoidal / Cuadrada
    - Frecuencia: Spinbox 1-500 Hz (cambio en vivo, sin glitches de fase)
    - INICIAR / DETENER

Uso:
    1. Crear par com0com COM4↔COM5 (o el que prefieras)
    2. En main.py poner SERIAL_PORT='COM4'
    3. python mock_generador.py  → seleccionar COM5
    4. python main.py            → click INICIAR
"""

import serial
import serial.tools.list_ports
import threading
import tkinter as tk
from tkinter import ttk
import time
import math

# Resolución de timer 1 ms en Windows (igual que main.py)
try:
    import ctypes
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

BAUD_RATE = 115200
FS = 1000  # tasa de envío en Hz

# Rango del ADC del Arduino (lo que se ve en A0)
V_ADC_MIN = 0.7
V_ADC_MAX = 4.7
V_ADC_CENTER = (V_ADC_MAX + V_ADC_MIN) / 2.0   # 2.7 V
V_ADC_AMP = (V_ADC_MAX - V_ADC_MIN) / 2.0      # 2.0 V (pico)


def voltaje_adc_a_raw(v_adc):
    """Convierte voltaje en A0 (0..5V) al byte 0..255 que mandaría el Arduino."""
    raw = int((v_adc / 5.0) * 255.0)
    return max(0, min(255, raw))


class MockGenerador:
    def __init__(self, root):
        self.root = root
        self.root.title("Mock Generador de Ondas → COM virtual")

        self.ser = None
        self.running = False
        self.thread = None

        # Estado de la señal — protegido por _lock para cambios en vivo
        self._lock = threading.Lock()
        self._forma = "sine"     # "sine" o "square"
        self._freq = 100.0       # Hz
        # Fase acumulada — se incrementa por delta-fase en cada muestra para
        # que cambiar freq en vivo NO produzca discontinuidades.
        self._fase = 0.0

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # Selector de puerto
        ttk.Label(frm, text="Puerto:").grid(row=0, column=0, sticky="w")
        self.var_port = tk.StringVar(value="COM5")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            ports = ["COM5"]
        self.cb_port = ttk.Combobox(frm, textvariable=self.var_port, values=ports, width=10)
        self.cb_port.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Button(frm, text="Refrescar", command=self._refrescar_puertos).grid(row=0, column=2, padx=4)

        # Forma de onda
        ttk.Label(frm, text="Forma:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.var_forma = tk.StringVar(value="Senoidal")
        cb_forma = ttk.Combobox(frm, textvariable=self.var_forma,
                                values=["Senoidal", "Cuadrada"], width=10, state="readonly")
        cb_forma.grid(row=1, column=1, sticky="w", padx=4, pady=(10, 0))
        cb_forma.bind("<<ComboboxSelected>>", self._on_forma_changed)

        # Frecuencia
        ttk.Label(frm, text="Frecuencia (Hz):").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.var_freq = tk.DoubleVar(value=100.0)
        sp_freq = ttk.Spinbox(frm, from_=1.0, to=500.0, increment=1.0,
                              textvariable=self.var_freq, width=8,
                              command=self._on_freq_changed)
        sp_freq.grid(row=2, column=1, sticky="w", padx=4, pady=(6, 0))
        # Cambio por escritura directa también
        self.var_freq.trace_add("write", lambda *a: self._on_freq_changed())

        # Botones
        self.btn_start = ttk.Button(frm, text="INICIAR", command=self.start)
        self.btn_start.grid(row=3, column=0, pady=(14, 0), sticky="w")
        self.btn_stop = ttk.Button(frm, text="DETENER", command=self.stop, state="disabled")
        self.btn_stop.grid(row=3, column=1, pady=(14, 0), sticky="w")

        # Status
        self.var_status = tk.StringVar(value="Detenido")
        ttk.Label(frm, textvariable=self.var_status, foreground="#444").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        # Info de amplitud (fija)
        info = (f"Amplitud emulada en A0: {V_ADC_MIN:.1f} V – {V_ADC_MAX:.1f} V\n"
                f"(centro {V_ADC_CENTER:.1f} V, ±{V_ADC_AMP:.1f} V)\n"
                f"Mandando a {FS} Hz en formato ASCII '{{0..255}}\\n'")
        ttk.Label(frm, text=info, foreground="#666", font=("Segoe UI", 8)).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _refrescar_puertos(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.cb_port["values"] = ports

    def _on_forma_changed(self, *_):
        forma = "sine" if self.var_forma.get() == "Senoidal" else "square"
        with self._lock:
            self._forma = forma

    def _on_freq_changed(self, *_):
        try:
            f = float(self.var_freq.get())
        except (tk.TclError, ValueError):
            return
        f = max(0.1, min(500.0, f))
        with self._lock:
            self._freq = f

    def start(self):
        if self.running:
            return
        port = self.var_port.get().strip()
        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        except Exception as e:
            self.var_status.set(f"Error abriendo {port}: {e}")
            return
        # Sincronizar estado con UI
        self._on_forma_changed()
        self._on_freq_changed()
        self._fase = 0.0
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.var_status.set(f"Enviando por {port} a {FS} Hz")

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.var_status.set("Detenido")

    def _run(self):
        """Loop de envío a 1 kHz. Pacing por deadline absoluto (igual que el
        MockSerial de main.py). Acumula fase por delta para no glitchear al
        cambiar frecuencia en vivo."""
        dt = 1.0 / FS
        start = time.perf_counter()
        n = 0
        last_log = start
        sent_since_log = 0

        while self.running:
            target = start + n * dt
            wait = target - time.perf_counter()
            if wait > 0:
                time.sleep(wait)

            with self._lock:
                forma = self._forma
                freq = self._freq

            # Avance de fase coherente: φ += 2π·f·dt. Si f cambia, la fase
            # sigue donde estaba — sin saltos en la onda.
            self._fase += 2.0 * math.pi * freq * dt
            if self._fase > 2.0 * math.pi * 1e6:
                self._fase = math.fmod(self._fase, 2.0 * math.pi)

            if forma == "sine":
                v_adc = V_ADC_CENTER + V_ADC_AMP * math.sin(self._fase)
            else:  # square
                v_adc = V_ADC_CENTER + (V_ADC_AMP if math.sin(self._fase) >= 0 else -V_ADC_AMP)

            raw = voltaje_adc_a_raw(v_adc)
            try:
                self.ser.write(f"{raw}\n".encode())
                # Drenar los bytes que main.py escribe al "DAC" de vuelta por el par
                # virtual. Sin esto el buffer de VSPE se llena y write() bloquea
                # cientos de ms → Fs cae y la señal se congela.
                if self.ser.in_waiting > 0:
                    self.ser.read(self.ser.in_waiting)
            except Exception as e:
                self.root.after(0, lambda: self.var_status.set(f"Error de escritura: {e}"))
                self.running = False
                break

            n += 1
            sent_since_log += 1
            now = time.perf_counter()
            if now - last_log >= 1.0:
                rate = sent_since_log / (now - last_log)
                msg = f"Enviando {forma} {freq:.1f} Hz | tasa real: {rate:.0f} muestras/s"
                self.root.after(0, lambda m=msg: self.var_status.set(m))
                last_log = now
                sent_since_log = 0


if __name__ == "__main__":
    root = tk.Tk()
    app = MockGenerador(root)
    def on_close():
        app.stop()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
