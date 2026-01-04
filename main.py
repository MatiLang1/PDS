import serial
import threading
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.animation import Animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import numpy as np
from scipy.signal import butter, lfilter

# --- CONFIGURACIÓN ---
SERIAL_PORT = 'COM4' 
BAUD_RATE = 115200 # Alta velocidad para evitar deformación [cite: 357]
BUFFER_SIZE = 512  # Potencia de 2 para que la FFT sea más rápida [cite: 23, 400]
FS = 1000          # Frecuencia de muestreo (Hz) [cite: 359]

class AppDSP:
    def __init__(self, master):
        self.master = master
        self.master.title("Sistema DSP - Análisis de Señales")
        
        # Buffers de datos
        self.data_raw = deque([0]*BUFFER_SIZE, maxlen=BUFFER_SIZE)
        self.running = False
        
        # Interfaz de Usuario (UI)
        self.setup_ui()
        
        # Conexión Serial
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        except:
            print("Error: No se encontró el puerto.")
            
    def setup_ui(self):
        # Frame de controles
        controls = ttk.Frame(self.master, padding="10")
        controls.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(controls, text="INICIAR", command=self.start).grid(row=0, column=0)
        ttk.Button(controls, text="DETENER", command=self.stop).grid(row=0, column=1)
        
        # Selección de Filtro [cite: 318, 319]
        ttk.Label(controls, text="Filtro:").grid(row=0, column=2)
        self.filter_type = tk.StringVar(value="Lowpass")
        ttk.Combobox(controls, textvariable=self.filter_type, 
                     values=["None", "Lowpass", "Highpass", "Bandpass"]).grid(row=0, column=3)
        
        # Etiquetas de Armónicas [cite: 316]
        self.armonicas_label = ttk.Label(controls, text="Esperando datos...")
        self.armonicas_label.grid(row=1, column=0, columnspan=4)
        
        # Gráficos [cite: 320]
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6))
        self.line_raw, = self.ax1.plot([], [], label="Original (ADC)", color='blue')
        self.line_filt, = self.ax1.plot([], [], label="Filtrada", color='red')
        self.ax1.set_ylim(0, 1024)
        self.ax1.legend()
        
        self.ax2.set_title("Espectro de Frecuencia (FFT)")
        self.line_fft, = self.ax2.plot([], [], color='green')
        self.ax2.set_xlim(0, FS/2) 
        self.ax2.set_ylim(0, 500)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def start(self):
        self.running = True
        threading.Thread(target=self.read_serial, daemon=True).start()
        self.animate()

    def stop(self):
        self.running = False

    def read_serial(self):
        """Lee datos muestra por muestra para evitar deformación [cite: 47]"""
        while self.running:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode().strip()
                    if line.isdigit():
                        self.data_raw.append(int(line))
                except: pass

    def animate(self):
        if not self.running: return
        
        y = np.array(self.data_raw)
        
        # 1. Aplicar Filtro [cite: 484, 485]
        y_filt = y
        f_type = self.filter_type.get()
        if f_type != "None":
            # Normalizamos frecuencias (0.0 a 1.0 donde 1.0 es Nyquist)
            nyq = 0.5 * FS
            low = 10 / nyq # Ejemplo 10Hz
            high = 100 / nyq # Ejemplo 100Hz
            
            if f_type == "Lowpass": b, a = butter(4, low, btype='low')
            elif f_type == "Highpass": b, a = butter(4, high, btype='high')
            else: b, a = butter(4, [low, high], btype='band')
            
            y_filt = lfilter(b, a, y)

        # 2. Calcular FFT y Armónicas [cite: 315, 474]
        n = len(y)
        yf = np.abs(np.fft.rfft(y - np.mean(y))) # rfft es más eficiente para señales reales
        xf = np.fft.rfftfreq(n, 1/FS)
        
        # Buscar las 3 armónicas principales [cite: 403, 475]
        idx = np.argsort(yf)[-3:][::-1]
        txt = "Armónicas detectadas: "
        for i in idx:
            txt += f"| {xf[i]:.1f}Hz ({yf[i]:.1f} amp) "
        self.armonicas_label.config(text=txt)

        # 3. Actualizar Gráficos
        self.line_raw.set_data(range(n), y)
        self.line_filt.set_data(range(n), y_filt)
        self.line_fft.set_data(xf, yf)
        
        self.canvas.draw()
        self.master.after(50, self.animate) # Ciclo de actualización de 50ms

if __name__ == "__main__":
    root = tk.Tk()
    app = AppDSP(root)
    root.mainloop()