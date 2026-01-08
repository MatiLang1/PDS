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

# Configuracion
SERIAL_PORT = 'COM4' 
BAUD_RATE = 115200 
BUFFER_SIZE = 512  
FS = 1000          

class AppDSP:
    def __init__(self, master):
        self.master = master
        self.master.title("Sistema DSP - Análisis de Señales Pro")
        
        # 1. SOLUCIÓN CRÍTICA: Lock para evitar el crash (Race Condition)
        self.lock = threading.Lock()
        self.data_raw = deque([0]*BUFFER_SIZE, maxlen=BUFFER_SIZE)
        self.running = False
        
        # Variables para el estado del filtro (Memoria)
        self.zi = None
        self.last_filter_type = "None"
        
        self.setup_ui()
        
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        except:
            print("Error: No se encontró el puerto.")
            
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
        self.ax1.set_ylim(-7, 7)
        self.ax1.set_xlim(0, BUFFER_SIZE)
        self.ax1.grid(True)
        self.ax1.legend(loc='upper right')
        
        # Gráfico FFT
        self.ax2.set_title("Espectro de Frecuencia (FFT)")
        self.line_fft, = self.ax2.plot([], [], color='green')
        self.ax2.set_xlim(0, FS/2) 
        # 4. SOLUCIÓN: Escala FFT fija para evitar que "baile"
        self.ax2.set_ylim(0, 500) 
        self.ax2.grid(True)
        
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
        yf = np.abs(np.fft.rfft(y - np.mean(y))) 
        xf = np.fft.rfftfreq(n, 1/FS)
        
        # Detección de armónicas
        idx = np.argsort(yf)[-3:][::-1]
        txt = "Armónicas detectadas: "
        for i in idx:
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