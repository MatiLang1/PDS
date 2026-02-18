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
  int sensorValue = analogRead(A0); 

  // REDUCIMOS ENTRADA ANALOGICA A 8 BITS
  // Realizamos un tratamiento digital (escalando de 10 bits a 8 bits) para eso dividimos por 4 al valor del A0 asi tenemos el valor de 0-255 que entre en los 8 bits del R-2R
  byte salida8bits = sensorValue / 4; 


  // REPRESENTACIÓN EN TIEMPO REAL PARA EL OSCILOSCOPIO
  // Enviamos en paralelo el valor de la señal bit a bit a los pines digitales (2-9)
  // PORTD es un registro q maneja los pines 0-7
  // salida8bits << 2 desplaza los bits de "salida8bits" 2 posiciones a la izquierda (esto para q el bit 0 de "salida8bits" entre en el pin 2, el 1 vaya al pin 3 y asi sucesivamente). Los bits 6 y 7 de "salida8bits" se escriben manualmente en los pines 8 y 9 (ya q PORTD maneja hasta el 7)
  PORTD = (salida8bits << 2);
  digitalWrite(8, bitRead(salida8bits, 6)); 
  digitalWrite(9, bitRead(salida8bits, 7));

  // Comunicacion Serie (Envio de datos a PC - para Python y FFT)
  // Aca enviamos el valor original leido en el A0 (que es el valor de la señal original), es de 10 bits
  Serial.println(sensorValue); 

  delayMicroseconds(1000); // Muestreo de 1kHz (delay de 1000 uS - 1 ms)
}