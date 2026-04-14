#!/usr/bin/env python
"""
Script para correr la GUI con MockSerial sin modificar main.py.

    python run_mock.py

La GUI abrirá simulando una señal de 50 Hz + 150 Hz.
"""

import tkinter as tk
import main

root = tk.Tk()
app = main.AppDSP.__new__(main.AppDSP)
app.master = root
app.lock = __import__('threading').Lock()
from collections import deque
app.data_raw = deque([0]*main.BUFFER_SIZE, maxlen=main.BUFFER_SIZE)
app.data_filt = deque([0]*main.BUFFER_SIZE, maxlen=main.BUFFER_SIZE)
app.running = False
app.fs_real = float(main.FS)
app._sample_count = 0
app._fs_timer = __import__('time').time()
app.zi = None
app.b = None
app.a = None
app.last_filter_type = "None"
app.last_fc_low = 0
app.last_fc_high = 0
app.last_fs_real = app.fs_real

# Reemplazar serial por mock ANTES de setup_ui
app.ser = main.MockSerial(signal='square')

app.setup_ui()
root.title("Sistema DSP - MOCK MODE (sin Arduino)")
print("[mock] Serial reemplazado por MockSerial. Clickeá INICIAR para ver la señal simulada (50Hz + 150Hz).")
root.mainloop()
