// CÓDIGO A CARGAR EN EL ARDUINO - ENTRADA (recibe la señal del generador de ondas) + SALIDA (envia al osciloscopio la señal adaptada al rango 0,5-4,5V) + ENVIO A PC (para realizar FFT y mostrar graficos)

void setup() {
  Serial.begin(115200);
  
  // Configuramos los pines 2 al 9 como salidas para la Escalera R-2R (8 bits)
  for (int i = 2; i <= 9; i++) {
    pinMode(i, OUTPUT);
  }
}

void loop() {
  // 1. MUESTREO (Entrada - 10 bits: 0-1023)
  int sensorValue = analogRead(A0); 

  // 2. TRATAMIENTO DIGITAL (Escalado de 10 bits a 8 bits: 0-255)
  // Dividimos por 4 para que el valor entre en los 8 bits del R-2R
  byte salida8bits = sensorValue / 4; 

  // 3. REPRESENTACIÓN EN TIEMPO REAL (Salida TP2)
  // Enviamos el valor bit a bit a los pines digitales
  PORTD = (salida8bits << 2); // Truco de programación rápida para pines 2 al 7
  digitalWrite(8, bitRead(salida8bits, 6)); 
  digitalWrite(9, bitRead(salida8bits, 7));

  // 4. ENVÍO A PC (Para Python / FFT)
  Serial.println(sensorValue); 

  delayMicroseconds(1000); // Muestreo de 1kHz
}