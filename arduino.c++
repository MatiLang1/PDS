// CÓDIGO A CARGAR EN EL ARDUINO - ENTRADA (recibe la señal del generador de ondas) + SALIDA (envia al osciloscopio la señal adaptada al rango 0,5-4,5V) + ENVIO A PC (para realizar FFT y mostrar graficos)

void setup() {
  Serial.begin(115200);
  
  // Configuramos los pines 2 al 9 como salidas para la Escalera R-2R (8 bits)
  for (int i = 2; i <= 9; i++) {
    pinMode(i, OUTPUT);
  }
}

void loop() {

  // ENTRADA ANALOGICA
  // Entrada - Muestreo (leemos el voltaje del pin A0), el ADC es de 10 bits por lo q el A0 tendra valores de 0-1023
  int sensorValue = analogRead(A0) / 4; 

  // Comunicacion Serie (Envio de datos a PC - para Python y FFT)
  // Aca enviamos el valor original leido en el A0 (que es el valor de la señal original), es de 10 bits
  Serial.println(sensorValue);
// 1111000000 

  // RECIBIMOS DATO FILTRADO DE LA PC (Si está disponible) y actualizamos el DAC
  if (Serial.available() > 0) {
    byte salida8bits = Serial.read(); // Leemos el byte que envió Python (0-255)
    // byte salida8bits = sensorValue;
    
    // REPRESENTACIÓN EN TIEMPO REAL PARA EL OSCILOSCOPIO
    // Enviamos en paralelo el valor de la señal bit a bit a los pines digitales (2-9)
    PORTD = salida8bits << 2;
    // digitalWrite(8, bitRead(salida8bits, 6)); 
    // digitalWrite(9, bitRead(salida8bits, 7));
    PORTB = salida8bits >> 6;
  }

//   delayMicroseconds(1000); // Muestreo de 1kHz (delay de 1000 uS - 1 ms)
}