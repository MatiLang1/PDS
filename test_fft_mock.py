"""
Test headless del DSP: corre el mock, aplica FFT y filtros, imprime resultados.
No requiere GUI ni Arduino. Usarlo para verificar que el core DSP funciona bien.

    python test_fft_mock.py
"""

import math
import time
import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi

# ---- Parámetros (deben coincidir con main.py) ----
FS_NOMINAL = 1000
BUFFER_SIZE = 256   # puntos que usa animate() para la FFT
N_SAMPLES   = 2000  # cuántas muestras generar en total (2 segundos nominales)
SUPPRESS_HZ = 15
# --------------------------------------------------

def generar_muestra(t):
    """Misma fórmula que MockSerial.readline()."""
    val_volts = 6.5 * math.sin(2 * math.pi * 50 * t) + \
                0.5 * math.sin(2 * math.pi * 150 * t)
    return val_volts

def calcular_fft(y, fs):
    n = len(y)
    window = np.hanning(n)
    coherent_gain = window.mean()
    y_w = (y - np.mean(y)) * window
    yf = np.abs(np.fft.rfft(y_w)) * (2.0 / n) / coherent_gain
    xf = np.fft.rfftfreq(n, 1.0 / fs)
    return xf, yf

def detectar_picos(xf, yf, n_picos=3):
    freq_resolution = xf[1] - xf[0] if len(xf) > 1 else 1.0
    suppress_bins = max(1, int(SUPPRESS_HZ / freq_resolution))
    yf_work = yf.copy()
    yf_global_max = yf.max() if yf.size else 0.0
    picos = []
    for _ in range(n_picos):
        umbral = max(0.1, yf_global_max * 0.05)
        if yf_work.max() < umbral:
            break
        peak = int(np.argmax(yf_work))
        picos.append((xf[peak], yf[peak]))
        lo = max(0, peak - suppress_bins)
        hi = min(len(yf_work), peak + suppress_bins + 1)
        yf_work[lo:hi] = 0
    return picos

def test_sin_filtro():
    print("=" * 55)
    print("TEST 1: Sin filtro — señal 50 Hz + 150 Hz")
    print("=" * 55)
    muestras = []
    t0 = time.perf_counter()
    for i in range(N_SAMPLES):
        t = i / FS_NOMINAL
        muestras.append(generar_muestra(t))
    elapsed = time.perf_counter() - t0

    # Tomar los últimos BUFFER_SIZE puntos (igual que animate())
    y = np.array(muestras[-BUFFER_SIZE:])
    fs = FS_NOMINAL  # generación perfecta, sin jitter

    xf, yf = calcular_fft(y, fs)
    picos = detectar_picos(xf, yf)

    labels = ["F₀ (Fundamental)", "F₁ (1er Armónica)", "F₂ (2da Armónica)"]
    for i, (freq, amp) in enumerate(picos):
        label = labels[i] if i < len(labels) else f"F{i}"
        print(f"  {label}: {freq:.1f} Hz  |  A = {amp:.3f} V")

    # Verificar que F0 está en 50 Hz ± 10 Hz y F1 en 150 Hz ± 10 Hz
    ok = True
    if len(picos) < 2:
        print("  ERROR: se esperaban al menos 2 picos, se detectaron", len(picos))
        ok = False
    else:
        f0, a0 = picos[0]
        f1, a1 = picos[1]
        if not (40 <= f0 <= 60):
            print(f"  FALLO: F0 debería ser ~50 Hz, se obtuvo {f0:.1f} Hz")
            ok = False
        if not (140 <= f1 <= 160):
            print(f"  FALLO: F1 debería ser ~150 Hz, se obtuvo {f1:.1f} Hz")
            ok = False
        if not (5.5 <= a0 <= 7.0):
            print(f"  FALLO: A(F0) debería ser ~6.5 V, se obtuvo {a0:.3f} V")
            ok = False
        if not (0.3 <= a1 <= 0.7):
            print(f"  FALLO: A(F1) debería ser ~0.5 V, se obtuvo {a1:.3f} V")
            ok = False

    estado = "OK" if ok else "FALLO"
    print(f"\n  Resultado: {estado}")
    print()

def test_filtro_lowpass(fc=100.0):
    print("=" * 55)
    print(f"TEST 2: Filtro Lowpass  Fc={fc} Hz")
    print("  (esperar: F0 pasa, F1 atenuado/eliminado)")
    print("=" * 55)
    muestras_raw = []
    muestras_filt = []
    b, a = butter(4, fc / (0.5 * FS_NOMINAL), btype='low')
    zi = lfilter_zi(b, a) * generar_muestra(0)

    for i in range(N_SAMPLES):
        t = i / FS_NOMINAL
        val = generar_muestra(t)
        muestras_raw.append(val)
        out_arr, zi = lfilter(b, a, [val], zi=zi)
        muestras_filt.append(float(out_arr[0]))

    y_filt = np.array(muestras_filt[-BUFFER_SIZE:])
    xf, yf = calcular_fft(y_filt, FS_NOMINAL)
    picos = detectar_picos(xf, yf)

    for i, (freq, amp) in enumerate(picos):
        labels = ["F₀", "F₁", "F₂"]
        print(f"  {labels[i] if i<3 else 'F?'}: {freq:.1f} Hz  |  A = {amp:.3f} V")

    ok = True
    if picos:
        f0, a0 = picos[0]
        if not (40 <= f0 <= 60):
            print(f"  FALLO: F0 debería ser ~50 Hz, se obtuvo {f0:.1f} Hz")
            ok = False
        # F1 (150 Hz) debería estar muy atenuado con LP a 100 Hz (orden 4)
        if len(picos) > 1:
            f1, a1 = picos[1]
            if 140 <= f1 <= 160 and a1 > 0.3:
                print(f"  ADVERTENCIA: F1 ({f1:.1f} Hz, A={a1:.3f} V) debería estar más atenuado")
    estado = "OK" if ok else "FALLO"
    print(f"\n  Resultado: {estado}")
    print()

def test_filtro_highpass(fc=100.0):
    print("=" * 55)
    print(f"TEST 3: Filtro Highpass  Fc={fc} Hz")
    print("  (esperar: F0 atenuado, F1 pasa)")
    print("=" * 55)
    muestras_filt = []
    b, a = butter(4, fc / (0.5 * FS_NOMINAL), btype='high')
    zi = lfilter_zi(b, a) * generar_muestra(0)

    for i in range(N_SAMPLES):
        t = i / FS_NOMINAL
        val = generar_muestra(t)
        out_arr, zi = lfilter(b, a, [val], zi=zi)
        muestras_filt.append(float(out_arr[0]))

    y_filt = np.array(muestras_filt[-BUFFER_SIZE:])
    xf, yf = calcular_fft(y_filt, FS_NOMINAL)
    picos = detectar_picos(xf, yf)

    for i, (freq, amp) in enumerate(picos):
        labels = ["F₀", "F₁", "F₂"]
        print(f"  {labels[i] if i<3 else 'F?'}: {freq:.1f} Hz  |  A = {amp:.3f} V")

    ok = True
    if picos:
        f0, a0 = picos[0]
        if 140 <= f0 <= 160:
            print(f"  F1 correctamente como pico principal: {f0:.1f} Hz, A={a0:.3f} V")
        elif 40 <= f0 <= 60 and a0 > 3.0:
            print(f"  FALLO: F0 ({f0:.1f} Hz, A={a0:.3f} V) debería estar atenuado")
            ok = False
    estado = "OK" if ok else "FALLO"
    print(f"\n  Resultado: {estado}")
    print()

def test_filtro_bandpass(fc1=40.0, fc2=120.0):
    print("=" * 55)
    print(f"TEST 4: Filtro Bandpass  Fc1={fc1} Hz  Fc2={fc2} Hz")
    print("  (esperar: solo F0 en 50 Hz pasa)")
    print("=" * 55)
    nyq = 0.5 * FS_NOMINAL
    fc1_s = max(1.0, min(fc1, nyq - 1))
    fc2_s = max(fc1_s + 1.0, min(fc2, nyq - 1))
    b, a = butter(4, [fc1_s / nyq, fc2_s / nyq], btype='band')
    zi = lfilter_zi(b, a) * generar_muestra(0)
    muestras_filt = []

    for i in range(N_SAMPLES):
        t = i / FS_NOMINAL
        val = generar_muestra(t)
        out_arr, zi = lfilter(b, a, [val], zi=zi)
        muestras_filt.append(float(out_arr[0]))

    y_filt = np.array(muestras_filt[-BUFFER_SIZE:])
    xf, yf = calcular_fft(y_filt, FS_NOMINAL)
    picos = detectar_picos(xf, yf)

    for i, (freq, amp) in enumerate(picos):
        labels = ["F₀", "F₁", "F₂"]
        print(f"  {labels[i] if i<3 else 'F?'}: {freq:.1f} Hz  |  A = {amp:.3f} V")

    estado = "OK"
    if picos:
        f0, a0 = picos[0]
        if not (40 <= f0 <= 60):
            print(f"  FALLO: pico principal debería ser ~50 Hz, se obtuvo {f0:.1f} Hz")
            estado = "FALLO"
    print(f"\n  Resultado: {estado}")
    print()

if __name__ == "__main__":
    print()
    print("=== TEST DSP HEADLESS (sin GUI, sin Arduino) ===")
    print(f"Fs nominal: {FS_NOMINAL} Hz | Buffer FFT: {BUFFER_SIZE} puntos")
    print(f"Señal mock: 50 Hz (6.5 Vp) + 150 Hz (0.5 Vp)")
    print()
    test_sin_filtro()
    test_filtro_lowpass(fc=100.0)
    test_filtro_highpass(fc=100.0)
    test_filtro_bandpass(fc1=40.0, fc2=120.0)
    print("=== Fin de tests ===")
