import serial
import threading
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import numpy as np
from scipy.signal import butter, lfilter
import time
import math

# --- CONFIGURACIÓN ---
SERIAL_PORT = 'COM4' 
BAUD_RATE = 115200 
BUFFER_SIZE = 512  
FS = 1000          

class MockSerial:
    def __init__(self):
        self.start_time = time.time()
        print("--- MOCK SERIAL INICIADO ---")
        print("Simulando señal de generador: Senoidal 50Hz +/- 6V")
        
    @property
    def in_waiting(self):
        return 1 # Siempre tiene datos disponibles
        
    def readline(self):
        # Simula el tiempo real para genera la onda
        t = time.time() - self.start_time
        
        # Generar señal teórica (-6V a 6V)
        # Fundamental 50Hz + Armónica pequeña 150Hz
        val_volts = 6.0 * math.sin(2 * math.pi * 50 * t) + \
                    1.0 * math.sin(2 * math.pi * 150 * t)
                    
        # Limitar a rango físico del generador si fuera necesario, pero la matemática es ideal
        
        # Simular circuito de acondicionamiento (Hardware):
        # 1. Divisor y Offset: V_pin = (V_gen / 3.0) + 2.5V
        #    Si V_gen = -6V -> -2 + 2.5 = 0.5V
        #    Si V_gen =  6V ->  2 + 2.5 = 4.5V
        v_pin = (val_volts / 3.0) + 2.5
        
        # Ruido aleatorio pequeño
        noise = np.random.normal(0, 0.02)
        v_pin += noise
        
        # Convertir a ADC (0-1023 para 0-5V)
        adc_val = int((v_pin / 5.0) * 1023)
        
        # Clampear entre 0 y 1023
        adc_val = max(0, min(1023, adc_val))
        
        # Simular delay de transmisión serial (aprox 1kHz -> 1ms)
        time.sleep(1/FS) 
        
        return f"{adc_val}\n".encode()

class AppDSP:
    def __init__(self, master):
        self.master = master
        self.master.title("Sistema DSP - Análisis de Señales Pro (MOCK ACTIVE)")
        
        # 1. SOLUCIÓN CRÍTICA: Lock para evitar el crash (Race Condition)
        self.lock = threading.Lock()
        self.data_raw = deque([0]*BUFFER_SIZE, maxlen=BUFFER_SIZE)
        self.running = False
        
        # Variables para el estado del filtro (Memoria)
        self.zi = None
        
        self.setup_ui()
        
        # Intentar conectar serial, si falla usar Mock
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
            print(f"Conectado a {SERIAL_PORT}")
        except Exception as e:
            print(f"Error Serial: {e}")
            print("Iniciando modo Simulación (Mock)...")
            self.ser = MockSerial()
            self.master.title("Sistema DSP - MODO SIMULACIÓN")
            
    def setup_ui(self):
        controls = ttk.Frame(self.master, padding="10")
        controls.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(controls, text="INICIAR", command=self.start).grid(row=0, column=0)
        ttk.Button(controls, text="DETENER", command=self.stop).grid(row=0, column=1)
        
        ttk.Label(controls, text="Filtro:").grid(row=0, column=2)
        self.filter_type = tk.StringVar(value="None")
        ttk.Combobox(controls, textvariable=self.filter_type, 
                     values=["None", "Lowpass", "Highpass", "Bandpass"]).grid(row=0, column=3)
        
        self.armonicas_label = ttk.Label(controls, text="Esperando datos...")
        self.armonicas_label.grid(row=1, column=0, columnspan=4)
        
        # Configuración de gráficos
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6))
        
        # Gráfico Temporal
        self.line_raw, = self.ax1.plot([], [], label="Original (-6 a 6V)", color='blue', lw=1)
        self.line_filt, = self.ax1.plot([], [], label="Filtrada", color='red', lw=1.5)
        self.ax1.set_ylim(-8, 8) # Un poco mas de margen
        self.ax1.set_xlim(0, BUFFER_SIZE)
        self.ax1.grid(True, linestyle='--', alpha=0.7)
        self.ax1.legend(loc='upper right')
        self.ax1.set_ylabel("Voltaje (V)")
        
        # Gráfico FFT
        self.ax2.set_title("Espectro de Frecuencia (FFT)")
        self.line_fft, = self.ax2.plot([], [], color='green')
        self.ax2.set_xlim(0, FS/2) 
        # 4. SOLUCIÓN: Escala FFT fija para evitar que "baile"
        self.ax2.set_ylim(0, 400) 
        self.ax2.grid(True, linestyle='--', alpha=0.7)
        self.ax2.set_xlabel("Frecuencia (Hz)")
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self.read_serial, daemon=True).start()
            # 3. SOLUCIÓN: Usamos blit=True para rendimiento
            self.ani = FuncAnimation(self.fig, self.animate, interval=50, blit=True)
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
                        # 1. SOLUCIÓN: Uso de Lock al escribir
                        with self.lock:
                            self.data_raw.append(int(line))
                except: pass

    def animate(self, frame):
        # 1. SOLUCIÓN: Uso de Lock al leer para evitar RuntimeError
        with self.lock:
            y_adc = np.array(self.data_raw)
        
        # Destraducción: Recuperamos señal de 12Vpp
        # Hardware: (Vin_real / 3) + 2.5 = V_pin
        # Software inv: (V_pin - 2.5) * 3 = Vin_real
        y = ((y_adc * 5.0 / 1023.0) - 2.5) * 3.0
        
        # 2. MEJORA DE FILTRO: lfilter sobre el buffer actual
        y_filt = y
        f_type = self.filter_type.get()
        if f_type != "None":
            try:
                nyq = 0.5 * FS
                if f_type == "Lowpass": b, a = butter(4, 40/nyq, btype='low')
                elif f_type == "Highpass": b, a = butter(4, 100/nyq, btype='high')
                else: b, a = butter(4, [40/nyq, 100/nyq], btype='band')
                
                y_filt = lfilter(b, a, y)
            except: pass

        # 3. CÁLCULO DE FFT
        n = len(y)
        if n > 0:
            yf = np.abs(np.fft.rfft(y - np.mean(y))) 
            xf = np.fft.rfftfreq(n, 1/FS)
            
            # Detección de armónicas
            # Filtramos indices con magnitud > 10 para ignorar ruido de piso
            threshold = 10
            peak_idxs = np.where(yf > threshold)[0]
            
            # Ordenamos por magnitud
            sorted_peak_idxs = peak_idxs[np.argsort(yf[peak_idxs])][::-1]
            
            # Tomamos hasta 3
            top_idxs = sorted_peak_idxs[:3]
            
            txt = "Armónicas detectadas: "
            for i in top_idxs:
                txt += f"| {xf[i]:.1f}Hz (A:{yf[i]:.1f}) "
            self.armonicas_label.config(text=txt)

            # ACTUALIZACIÓN DE LÍNEAS (Para blit=True)
            self.line_raw.set_data(np.arange(n), y)
            self.line_filt.set_data(np.arange(n), y_filt)
            self.line_fft.set_data(xf, yf)
        
        # 3. SOLUCIÓN: No llamamos a canvas.draw(), retornamos artistas
        return self.line_raw, self.line_filt, self.line_fft

if __name__ == "__main__":
    root = tk.Tk()
    app = AppDSP(root)
    root.mainloop()