# TP Nº3 — Sistema DSP (PDS)

## Requisitos
- Python 3.10 o superior
- Arduino Uno con `arduino.c++` cargado (solo para uso con hardware real)
- El puerto serial `COM3` libre (no abierto por el Monitor Serial del IDE de Arduino)

---
## Instalación del entorno

```bash
# 1. Crear el entorno virtual
python -m venv .venv

# 2. Activarlo
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

---
## Cómo correr cada componente

### App principal (con Arduino conectado)
Requiere el Arduino corriendo en `COM3` con `arduino.c++` cargado.

```bash
python main.py
```

---
### Mock con onda cuadrada (sin Arduino)
Simula una señal cuadrada de 50 Hz con armónicas impares (50, 150, 250 Hz...). Útil para probar FFT y filtros sin hardware.

```bash
python run_mock.py
```

---
### Mock con senoidal pura (sin Arduino)
Simula una senoidal pura de 50 Hz. El espectro debería mostrar un único pico en F₀ = 50 Hz

```bash
python run_mock_senoidal.py
```

---
### Tests headless del DSP (sin GUI, sin Arduino)
Verifica que la FFT y los filtros Butterworth funcionan correctamente

```bash
python test_fft_mock.py
```
Corre 4 tests automáticos y muestra `OK` o `FALLO` por consola:
1. Sin filtro — detecta F₀ = 50 Hz y F₁ = 150 Hz
2. Filtro Lowpass (Fc = 100 Hz) — F₁ atenuada
3. Filtro Highpass (Fc = 100 Hz) — F₀ atenuada
4. Filtro Bandpass (40–120 Hz) — solo F₀ pasa

---
### Test del DAC (con Arduino conectado)
```bash
python test_dac.py
```

---
## Uso de la GUI

| Control | Función |
|---|---|
| **INICIAR / DETENER** | Arranca o para la adquisición |
| **Filtro** | Selecciona `None`, `Lowpass`, `Highpass` o `Bandpass` |
| **Fc** | Frecuencia de corte (Hz) para Lowpass y Highpass |
| **Fc2** | Frecuencia de corte superior (Hz), solo para Bandpass |

Los parámetros de filtro se aplican en caliente sin necesidad de reiniciar.

---

## Estructura del proyecto

```
main.py               # App principal (GUI + FFT + filtros + serial)
arduino.c++           # Firmware Arduino Uno
run_mock.py           # GUI con señal cuadrada simulada
run_mock_senoidal.py  # GUI con senoidal pura simulada
test_fft_mock.py      # Test
test_dac.py           # Test
requirements.txt      # Dependencias Python
```
