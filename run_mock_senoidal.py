#!/usr/bin/env python
"""
Mock con señal SENOIDAL pura de 50Hz ±6V.
Simula lo que verías en la GUI al conectar el generador de ondas
enviando una senoidal real al Arduino.

    python run_mock_senoidal.py

Resultado esperado: solo F₀ a 50 Hz en el espectro (sin armónicas).
"""

import tkinter as tk
import main

root = tk.Tk()
app = main.AppDSP.__new__(main.AppDSP)
app.master = root
app.lock = __import__('threading').Lock()
from collections import deque
app.data_raw  = deque([0]*main.BUFFER_SIZE, maxlen=main.BUFFER_SIZE)
app.data_filt = deque([0]*main.BUFFER_SIZE, maxlen=main.BUFFER_SIZE)
app.running = False
app.fs_real = float(main.FS)
app._sample_count = 0
app._fs_timer = __import__('time').time()
app.zi = None
app.b  = None
app.a  = None
app.last_filter_type = "None"
app.last_fc_low  = 0
app.last_fc_high = 0
app.last_fs_real = app.fs_real

# Señal senoidal pura
app.ser = main.MockSerial(signal='sine')

app.setup_ui()
root.title("Sistema DSP - MOCK SENOIDAL 50Hz ±6V (sin Arduino)")
print("[mock senoidal] Clickeá INICIAR. Verás solo F₀ a 50 Hz — igual a una senoidal real del generador.")
root.mainloop()
