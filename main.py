import serial
import threading
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi #para realizar los calculos matematicos necesarios para aplicar los filtros
import time
import math

# En Windows, time.sleep() tiene resolución por defecto ~15 ms, lo que hace
# imposible pacear el MockSerial a 1 kHz con sleep. timeBeginPeriod(1) baja
# esa resolución a ~1 ms para todo el proceso. Sin esto, el mock con sleep
# corre a ~60 Hz por starvation del GIL bajo matplotlib.
try:
    import ctypes
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

# --- CONFIGURACIÓN ---
SERIAL_PORT = 'COM3' 
BAUD_RATE = 115200 
BUFFER_SIZE = 512  
FS = 1000          

class MockSerial:
    # signal: 'square' → onda cuadrada ±6V 50Hz (con armónicas)
    #         'sine'   → senoidal pura  ±6V 50Hz (sin armónicas)
    def __init__(self, signal='square'):
        self.signal = signal
        # start_time se resetea en la primera llamada a readline() para no
        # acumular "deuda temporal" entre creación del mock y click en INICIAR
        self.start_time = None
        self.samples_sent = 0
        print("--- MOCK SERIAL INICIADO ---")
        if signal == 'sine':
            print("Simulando señal: senoidal pura 50Hz ±6V (sin armónicas)")
        else:
            print("Simulando señal: onda cuadrada 50Hz ±6V (con armónicas impares)")

    @property
    def in_waiting(self):
        return 1 # Siempre tiene datos disponibles

    def write(self, data):
        pass # El mock no necesita escribir a ningún lado

    def readline(self):
        # Paceo a 1000 Hz usando time.sleep(). Requiere timeBeginPeriod(1)
        # para resolución de 1ms en Windows (hecho en import del módulo).
        # Usamos sleep en vez de busy-wait para liberar el GIL y que
        # matplotlib pueda dibujar sin starvar al thread del mock.
        if self.start_time is None:
            self.start_time = time.perf_counter()

        target_time = self.start_time + self.samples_sent * (1.0 / FS)
        wait = target_time - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
        # Si wait < 0 (catchup): no dormimos, seguimos y que la próxima
        # muestra retome el ritmo. El clamp de fs_real en read_serial ya
        # absorbe picos transitorios.

        t = self.samples_sent * (1.0 / FS)
        self.samples_sent += 1

        if self.signal == 'sine':
            # Senoidal pura ±6V a 50 Hz — sin armónicas, solo F₀ en el espectro
            val_volts = 6.0 * math.sin(2 * math.pi * 50 * t)
        else:
            # Onda cuadrada ±6V a 50 Hz — armónicas impares: 50, 150, 250 Hz...
            # Amplitudes teóricas: 4A/π ≈ 7.64V, 4A/(3π) ≈ 2.55V, 4A/(5π) ≈ 1.53V
            val_volts = 6.0 if math.sin(2 * math.pi * 50 * t) >= 0 else -6.0
                    
        # Empaquetado según tu nuevo protocolo: 0 = 6V, 255 = -6V
        adc_val = int(((6.0 - val_volts) / 12.0) * 255.0)
        
        # Clampear entre 0 y 255
        adc_val = max(0, min(255, adc_val))
        
        return f"{adc_val}\n".encode()

class AppDSP:
    def __init__(self, master):
        self.master = master
        self.master.title("Sistema DSP - Análisis de Señales Pro (MOCK ACTIVE)")
        
        # Lock para bloquear la modificacion de la propiedad data_raw (hay 2 hilos modificando dicha propiedad, por lo q bloqueamos cuando uno la usa)
        self.lock = threading.Lock()

        # Buffer circular para almacenar los últimos N valores de la señal
        self.data_raw = deque([0]*BUFFER_SIZE, maxlen=BUFFER_SIZE)
        self.data_filt = deque([0]*BUFFER_SIZE, maxlen=BUFFER_SIZE)
        self.running = False

        # Medición de Fs real (el Arduino no tiene gate temporal; Fs efectiva depende
        # del UART y del loop). Python mide la tasa real y la usa para FFT y filtros.
        self.fs_real = float(FS)
        self._sample_count = 0
        self._fs_timer = time.time()

        # Variables para el estado del filtro (Memoria)
        self.zi = None
        self.b = None
        self.a = None
        self.last_filter_type = "None"
        self.last_fc_low = 0
        self.last_fc_high = 0
        self.last_fs_real = self.fs_real
        
        self.setup_ui()
        
        # Conexión Forzosa (Sin Mock) - Si falla, te mostrará el error exacto en la terminal
        self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        print(f"Conectado a {SERIAL_PORT} Exitosamente!")
            
    def setup_ui(self):
        controls = ttk.Frame(self.master, padding="10") # creamos un frame para los controles
        controls.pack(side=tk.TOP, fill=tk.X) # empaquetamos el frame
        
        ttk.Button(controls, text="INICIAR", command=self.start).grid(row=0, column=0) # creamos el boton iniciar
        ttk.Button(controls, text="DETENER", command=self.stop).grid(row=0, column=1) # creamos el boton detener
        
        ttk.Label(controls, text="Filtro:").grid(row=0, column=2) # creamos la etiqueta filtro
        self.filter_type = tk.StringVar(value="None") # creamos la variable filtro
        ttk.Combobox(controls, textvariable=self.filter_type, 
                     values=["None", "Lowpass", "Highpass", "Bandpass"], width=10).grid(row=0, column=3)
                     
        ttk.Label(controls, text="Fc (Hz):").grid(row=0, column=4)
        self.fc_low = tk.DoubleVar(value=40.0)
        ttk.Spinbox(controls, from_=1.0, to=499.0, increment=1.0, textvariable=self.fc_low, width=5).grid(row=0, column=5)
        
        ttk.Label(controls, text="Fc2 (Hz):").grid(row=0, column=6)
        self.fc_high = tk.DoubleVar(value=100.0)
        ttk.Spinbox(controls, from_=1.0, to=499.0, increment=1.0, textvariable=self.fc_high, width=5).grid(row=0, column=7)
        
        self.armonicas_label = ttk.Label(controls, text="Esperando datos...") # creamos la etiqueta armonicas
        self.armonicas_label.grid(row=1, column=0, columnspan=4) # empaquetamos la etiqueta armonicas
        
        # Configuración de gráficos
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6)) # creamos la figura y los ejes
        
        # Gráfico Temporal
        self.line_raw, = self.ax1.plot([], [], label="Original (-6 a 6V)", color='blue', lw=1)
        self.line_filt, = self.ax1.plot([], [], label="Filtrada", color='red', lw=1.5)
        self.ax1.set_ylim(-8, 8) # Un poco mas de margen
        self.ax1.set_xlim(0, (BUFFER_SIZE / FS) * 1000)
        self.ax1.grid(True, linestyle='--', alpha=0.7)
        self.ax1.legend(loc='upper right')
        self.ax1.set_ylabel("Voltaje (V)")
        self.ax1.set_xlabel("Tiempo (ms)")
        
        # Gráfico FFT - Solo armónicas detectadas
        self.ax2.set_title("Espectro de Frecuencia - Armónicas Detectadas")
        self.ax2.set_xlim(0, 500)
        self.ax2.set_ylim(0, 500) 
        self.ax2.grid(True, linestyle='--', alpha=0.7)
        self.ax2.set_xlabel("Frecuencia (Hz)")
        self.ax2.set_ylabel("Amplitud (FFT)")
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def start(self):
        if not self.running:
            self.running = True
            # Reiniciar la medición de Fs real al arrancar
            self._sample_count = 0
            self._fs_timer = time.time()
            threading.Thread(target=self.read_serial, daemon=True).start()
            # blit=False para que ax2.cla() + redibujo de barras FFT funcione sin artefactos
            self.ani = FuncAnimation(self.fig, self.animate, interval=50, blit=False)
            self.canvas.draw()

    def stop(self):
        self.running = False
        if hasattr(self, 'ani'):
            self.ani.event_source.stop()

    def read_serial(self):
        while self.running:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode().strip()
                    if line.isdigit():
                        val_raw = int(line)
                        # Convertir inmediatamente a dominio de voltaje (-6V a 6V)
                        val_volts = 6.0 - (val_raw / 255.0) * 12.0

                        # Proceso de filtrado en tiempo real en Voltios
                        f_type = self.filter_type.get()
                        out_val_volts = val_volts

                        if f_type != "None":
                            fc1 = self.fc_low.get()
                            fc2 = self.fc_high.get()
                            # Recomputar coeficientes si cambió el tipo, fc o si Fs real se corrió > 5 Hz
                            fs_changed = abs(self.fs_real - self.last_fs_real) > 5.0
                            if (f_type != self.last_filter_type or fc1 != self.last_fc_low
                                    or fc2 != self.last_fc_high or fs_changed):
                                self.last_filter_type = f_type
                                self.last_fc_low = fc1
                                self.last_fc_high = fc2
                                self.last_fs_real = self.fs_real
                                nyq = 0.5 * self.fs_real
                                fc1_safe = max(1.0, min(fc1, nyq - 1))
                                fc2_safe = max(fc1_safe + 1.0, min(fc2, nyq - 1))
                                if f_type == "Lowpass": b, a = butter(4, fc1_safe/nyq, btype='low')
                                elif f_type == "Highpass": b, a = butter(4, fc1_safe/nyq, btype='high')
                                else: b, a = butter(4, [fc1_safe/nyq, fc2_safe/nyq], btype='band')
                                self.b, self.a = b, a
                                self.zi = lfilter_zi(b, a) * val_volts

                            if self.zi is not None:
                                filtered_arr, self.zi = lfilter(self.b, self.a, [val_volts], zi=self.zi)
                                out_val_volts = float(filtered_arr[0])
                        else:
                            self.last_filter_type = "None"
                            self.zi = None

                        # Guardar en ambos buffers bajo el mismo lock — lo que se grafica
                        # como "Filtrada" es exactamente lo que sale por el DAC.
                        with self.lock:
                            self.data_raw.append(val_volts)
                            self.data_filt.append(out_val_volts)

                        # Medición de Fs real (cada ~200 muestras).
                        # Clampeamos a un rango sensato para que ráfagas de
                        # catchup o stalls del GIL no corrompan el eje FFT.
                        self._sample_count += 1
                        if self._sample_count >= 200:
                            now = time.time()
                            elapsed = now - self._fs_timer
                            if elapsed > 0:
                                measured = self._sample_count / elapsed
                                if 200.0 <= measured <= 10000.0:
                                    self.fs_real = measured
                                    print(f"[read_serial] fs_real actualizado -> {measured:.1f} Hz (200 muestras en {elapsed*1000:.1f} ms)")
                                else:
                                    print(f"[read_serial] fs medida FUERA DE RANGO: {measured:.1f} Hz (descartada, se mantiene {self.fs_real:.1f} Hz)")
                            self._sample_count = 0
                            self._fs_timer = now

                        # Reconvertir de Voltios a byte crudo (0-255) para el DAC
                        out_val_raw = ((6.0 - out_val_volts) / 12.0) * 255.0

                        # Limitar al rango de 8 bits [0, 255]
                        out_val_raw = max(0, min(255, int(out_val_raw)))
                        byte_val = out_val_raw

                        # Enviar byte filtrado al Arduino
                        self.ser.write(bytes([byte_val]))
                except Exception as e:
                    print(f"[read_serial] {repr(e)}")

    def animate(self, frame):
        # Lock al leer AMBOS buffers para que raw y filtrada queden alineadas
        with self.lock:
            y = np.array(self.data_raw)
            y_filt = np.array(self.data_filt)

        # DEBUG: cada ~20 frames (1 seg) imprimir stats del buffer
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        self._debug_counter += 1
        if self._debug_counter >= 20:
            self._debug_counter = 0
            y_no_zero = y[y != 0]
            n_nozero = len(y_no_zero)
            y_min = float(np.min(y_no_zero)) if n_nozero > 0 else 0
            y_max = float(np.max(y_no_zero)) if n_nozero > 0 else 0
            print(f"[animate] n={len(y)} | muestras_no_cero={n_nozero} | "
                  f"rango=[{y_min:.2f}, {y_max:.2f}] V | fs_real={self.fs_real:.1f}")

        # Ignorar los primeros 256 puntos para evitar artefactos de inicialización
        # (al arrancar el buffer está lleno de ceros, que distorsionan la FFT)
        if len(y) >= 256:
            y = y[-256:]
            y_filt = y_filt[-256:]

        fs = self.fs_real if self.fs_real > 0 else float(FS)

        # CÁLCULO DE FFT
        n = len(y)
        if n > 0:
            # Ventana Hanning para mitigar leakage espectral.
            # Factor 2/n y 1/coherent_gain para obtener amplitud en Volts.
            window = np.hanning(n)
            coherent_gain = window.mean()  # 0.5 para Hanning
            y_w = (y - np.mean(y)) * window
            yf = np.abs(np.fft.rfft(y_w)) * (2.0 / n) / coherent_gain
            xf = np.fft.rfftfreq(n, 1.0 / fs)

            # Detección de armónicas con supresión de vecinos
            SUPPRESS_HZ = 15
            freq_resolution = xf[1] - xf[0] if len(xf) > 1 else 1.0
            suppress_bins = max(1, int(SUPPRESS_HZ / freq_resolution))

            yf_work = yf.copy()
            top_idxs = []
            yf_global_max = yf.max() if yf.size else 0.0
            for _ in range(3):
                # Umbral: ≥100 mV absolutos o ≥5% del pico principal (el mayor de ambos)
                if yf_work.max() < max(0.1, yf_global_max * 0.05):
                    break
                peak = int(np.argmax(yf_work))
                top_idxs.append(peak)
                lo = max(0, peak - suppress_bins)
                hi = min(len(yf_work), peak + suppress_bins + 1)
                yf_work[lo:hi] = 0

            # Redibujar gráfico FFT con barras verticales
            labels = ["F₀ (Fundamental)", "F₁ (1er Armónica)", "F₂ (2da Armónica)"]
            colors = ["#e63946", "#2a9d8f", "#e9c46a"]
            txt = f"Fs real: {fs:.0f} Hz | Armónicas: "

            self.ax2.cla()
            self.ax2.set_title("Espectro de Frecuencia - Armónicas Detectadas")
            self.ax2.set_xlim(0, 500)
            ymax = max(1.0, yf_global_max * 1.2)
            self.ax2.set_ylim(0, ymax)
            self.ax2.set_xlabel("Frecuencia (Hz)")
            self.ax2.set_ylabel("Amplitud (V)")
            self.ax2.grid(True, linestyle='--', alpha=0.7)

            # DEBUG: imprimir picos detectados cada ~20 frames
            if self._debug_counter == 0 and top_idxs:
                picos_str = ", ".join([f"{xf[i]:.1f}Hz@{yf[i]:.2f}V" for i in top_idxs])
                print(f"[animate] picos detectados: {picos_str}")

            for rank, i in enumerate(top_idxs):
                freq = xf[i]
                amp = yf[i]
                label = labels[rank] if rank < len(labels) else f"F{rank}"
                color = colors[rank] if rank < len(colors) else "gray"
                self.ax2.bar(freq, amp, width=4, color=color, alpha=0.85,
                             label=f"{label}: {freq:.1f} Hz | A={amp:.2f} V")
                self.ax2.annotate(f"{label}\n{freq:.1f} Hz\nA={amp:.2f} V",
                                  xy=(freq, amp), xytext=(freq + 8, amp * 0.92),
                                  fontsize=7.5, color=color,
                                  arrowprops=dict(arrowstyle='->', color=color, lw=0.8))
                txt += f"| {label}: {freq:.1f}Hz (A={amp:.2f}V) "

            if top_idxs:
                self.ax2.legend(loc='upper right', fontsize=7)
            self.armonicas_label.config(text=txt)

            # Actualizar líneas temporales (eje dependiente de la Fs real medida)
            t_ms = np.arange(n) * (1000.0 / fs)
            self.line_raw.set_data(t_ms, y)
            self.line_filt.set_data(t_ms, y_filt)
            if t_ms[-1] > 0:
                self.ax1.set_xlim(0, t_ms[-1])

        return self.line_raw, self.line_filt

if __name__ == "__main__":
    root = tk.Tk()
    app = AppDSP(root)
    root.mainloop()