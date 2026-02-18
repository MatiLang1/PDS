#CODIGO PARA CORRER EN LA PC (recibe los valores del arduino y ejecuta los calculos matematicos y la visualizacion de los graficos de las distintas señales y sus armonicas)

import serial #para abrir el puerto COM (USB) y asi comunicarse con el Arduino
import threading #para correr procesos en paralelo (la GUI y la lectura del puerto serie)
import tkinter as tk #para crear la interfaz grafica
from tkinter import ttk #para crear la interfaz grafica
import matplotlib.pyplot as plt #para crear los graficos
from matplotlib.animation import FuncAnimation #para crear los graficos
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg #para crear los graficos
from collections import deque #para crear los graficos
import numpy as np #para realizar los calculos matematicos necesarios para la FFT
from scipy.signal import butter, lfilter #para realizar los calculos matematicos necesarios para aplicar los filtros

# Configuracion
SERIAL_PORT = 'COM4' #puerto COM donde se encuentra conectado el Arduino
BAUD_RATE = 115200 #velocidad de comunicacion entre la PC y el Arduino
BUFFER_SIZE = 512  #tamaño del buffer
FS = 1000 #frecuencia de muestreo

class AppDSP:
    def __init__(self, master):
        self.master = master
        self.master.title("Sistema DSP - Análisis de Señales")
        
        # Lock para bloquear la modificacion de la propiedad data_raw (hay 2 hilos modificando dicha propiedad, por lo q bloqueamos cuando uno la usa)
        self.lock = threading.Lock()

        # Buffer circular para almacenar los últimos N valores de la señal
        self.data_raw = deque([0]*BUFFER_SIZE, maxlen=BUFFER_SIZE)
        self.running = False # inicia en False porque al arrancar el programa no se esta leyendo el puerto serie
        
        # Variables para el estado del filtro (memoria)
        self.zi = None # inicializamos en None porque al arrancar el programa no se esta leyendo el puerto serie
        self.last_filter_type = "None" # inicializamos en None porque al arrancar el programa no se esta leyendo el puerto serie
        
        self.setup_ui()
        
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1) # abrimos el puerto serie
        except:
            print("Error: No se encontró el puerto.")

    # Creamos el metodo "setup_ui" en la clase "AppDSP" para que maneje la config de la interfaz grafica
    def setup_ui(self):
        controls = ttk.Frame(self.master, padding="10") # creamos un frame para los controles
        controls.pack(side=tk.TOP, fill=tk.X) # empaquetamos el frame
        
        ttk.Button(controls, text="INICIAR", command=self.start).grid(row=0, column=0) # creamos el boton iniciar
        ttk.Button(controls, text="DETENER", command=self.stop).grid(row=0, column=1) # creamos el boton detener
        
        ttk.Label(controls, text="Filtro:").grid(row=0, column=2) # creamos la etiqueta filtro
        self.filter_type = tk.StringVar(value="None") # creamos la variable filtro
        ttk.Combobox(controls, textvariable=self.filter_type, 
                     values=["None", "Lowpass", "Highpass", "Bandpass"]).grid(row=0, column=3) # creamos el combobox filtro
        
        self.armonicas_label = ttk.Label(controls, text="Esperando datos...") # creamos la etiqueta armonicas
        self.armonicas_label.grid(row=1, column=0, columnspan=4) # empaquetamos la etiqueta armonicas
        
        # Configuración de gráficos
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6)) # creamos la figura y los ejes
        
        # Gráfico Temporal
        self.line_raw, = self.ax1.plot([], [], label="Original (-6 a 6V)", color='blue', lw=1) # creamos la linea temporal
        self.line_filt, = self.ax1.plot([], [], label="Filtrada", color='red', lw=1.5) # creamos la linea temporal
        self.ax1.set_ylim(-7, 7) # establecemos los limites del eje y
        self.ax1.set_xlim(0, BUFFER_SIZE) # establecemos los limites del eje x
        self.ax1.grid(True) # activamos la grilla
        self.ax1.legend(loc='upper right') # creamos la leyenda
        
        # Gráfico FFT
        self.ax2.set_title("Espectro de Frecuencia (FFT)") # titulo del grafico FFT
        self.line_fft, = self.ax2.plot([], [], color='green') # creamos la linea FFT
        self.ax2.set_xlim(0, FS/2) # limites del eje x
        
        # Escalamos la FFT fija para evitar que se distorsione
        self.ax2.set_ylim(0, 500) 
        self.ax2.grid(True) # activamos la grilla
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self.read_serial, daemon=True).start()

            # Usamos blit=True para rendimiento
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
                        # Uso de Lock al escribir
                        with self.lock:
                            self.data_raw.append(int(line))
                except: pass

    def animate(self, frame):
        # Usamos Lock al leer para evitar RuntimeError
        with self.lock:
            y_adc = np.array(self.data_raw)
        
        # Destraducción: Recuperamos señal de 12Vpp
        y = ((y_adc * 5.0 / 1023.0) - 2.5) * 3.0
        
        # Mejoiramos el filtro (lfilter sobre el buffer actual)
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

        # Calculamos la FFT
        n = len(y)
        yf = np.abs(np.fft.rfft(y - np.mean(y))) 
        xf = np.fft.rfftfreq(n, 1/FS)
        
        # Realizamos la detección de armónicas
        idx = np.argsort(yf)[-3:][::-1]
        txt = "Armónicas detectadas: "
        for i in idx:
            txt += f"| {xf[i]:.1f}Hz (A:{yf[i]:.1f}) "
        self.armonicas_label.config(text=txt)

        # Actualizamos las lineas
        self.line_raw.set_data(np.arange(n), y)
        self.line_filt.set_data(np.arange(n), y_filt)
        self.line_fft.set_data(xf, yf)
        
        # No llamamos a canvas.draw(), retornamos artistas
        return self.line_raw, self.line_filt, self.line_fft

if __name__ == "__main__":
    root = tk.Tk()
    app = AppDSP(root)
    root.mainloop()