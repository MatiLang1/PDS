import serial
import time

SERIAL_PORT = 'COM3'
BAUD_RATE = 115200

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
time.sleep(2)  # Esperar a que el Arduino se reinicie tras la conexión

print("Modo Espejo (Pass-through): Leyendo A0 (0-1023) y mandando al DAC (0-255)...")

while True:
    if ser.in_waiting > 0:
        try:
            line = ser.readline().decode().strip()
            if line.isdigit():
                val = int(line)
                # Escalar señal de 10 bits a 8 bits
                val_8bit = max(0, min(255, val))
                # Enviar de vuelta al Arduino
                ser.write(bytes([val_8bit]))
        except Exception:
            pass
