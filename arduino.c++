//Codigo real: envío de la señal a traves del COM4 para que la GUI de python lo reconstruya, luego la GUI aplica filtros y le devuelve la señal filtrada al Arduino
// con esto en el osciloscopio se debe observar la señal filtrada que se ve en la GUI (se reconstruye probablemente con menor amplitud)
// CÓDIGO A CARGAR EN EL ARDUINO - ENTRADA (recibe la señal del generador de ondas) + SALIDA (envia al osciloscopio la señal adaptada al rango 0,5-4,5V) + ENVIO A PC (para realizar FFT y mostrar graficos)
void setup() {
  Serial.begin(115200);
  
  // Configuramos los pines 2 al 9 como salidas para la Escalera R-2R (8 bits)
  for (int i = 2; i <= 9; i++) {
    pinMode(i, OUTPUT);
  }
}

void loop() {
  // Gate de timing: fuerza exactamente 1000 Hz de muestreo.
  // Sin esto el Arduino manda a ~2500 Hz, desborda el buffer serial y
  // Python lee muestras acumuladas → el eje de tiempo queda comprimido.
  // += en vez de = evita que el error se acumule si el loop tarda más de 1ms.
  static unsigned long ultimo = 0;
  if (micros() - ultimo < 1000UL) return;
  ultimo += 1000UL;

  // Muestreo: ADC 10-bit → 8-bit (0-255) para el protocolo serial
  int sensorValue = analogRead(A0) / 4;

  // Envío a PC (ASCII con newline — Python usa readline())
  Serial.println(sensorValue);

  // Recibe byte filtrado de Python y lo materializa en el DAC R-2R (pines D2-D9)
  if (Serial.available() > 0) {
    byte salida8bits = Serial.read();
    PORTD = salida8bits << 2;   // bits 0-5 → pines D2-D7
    PORTB = salida8bits >> 6;   // bits 6-7 → pines D8-D9
  }
}




// //Codigo usado para testear el envío de una señal simulada a traves del COM4 para que la GUI de python lo reconstruya
// void setup() {
//   Serial.begin(115200);
  
//   // Configuramos los pines 2 al 9 como salidas para la Escalera R-2R (8 bits)
//   for (int i = 2; i <= 9; i++) {
//     pinMode(i, OUTPUT);
//   }
// }

// void loop() {
//   // Gate de timing: fuerza exactamente 1000 Hz de muestreo.
//   // Sin esto el Arduino manda a ~2500 Hz, desborda el buffer serial y
//   // Python lee muestras acumuladas → el eje de tiempo queda comprimido.
//   // += en vez de = evita que el error se acumule si el loop tarda más de 1ms.
//   static unsigned long ultimo = 0;
//   if (micros() - ultimo < 1000UL) return;
//   ultimo += 1000UL;

//   // AUTO-TEST: cuadrada 50 Hz generada por software con millis() — sin generador de ondas.
//   // raw=25 → +4.8V | raw=230 → -4.8V (inversión del AmpOp baked-in en Python)
//   // QUITAR PARA EL LAB: descomentar analogRead y comentar las 2 líneas de auto-test.
//   unsigned long t_ms = millis();
//   int sensorValue = ((t_ms % 20) < 10) ? 25 : 230;
//   // int sensorValue = analogRead(A0) / 4;  // ← LÍNEA DEL LAB

//   Serial.println(sensorValue);
// // 1111000000 

//   // RECIBIMOS DATO FILTRADO DE LA PC (Si está disponible) y actualizamos el DAC
//   if (Serial.available() > 0) {
//     byte salida8bits = Serial.read(); // Leemos el byte que envió Python (0-255)
//     // byte salida8bits = sensorValue;
    
//     // REPRESENTACIÓN EN TIEMPO REAL PARA EL OSCILOSCOPIO
//     // Enviamos en paralelo el valor de la señal bit a bit a los pines digitales (2-9)
//     PORTD = salida8bits << 2;
//     // digitalWrite(8, bitRead(salida8bits, 6)); 
//     // digitalWrite(9, bitRead(salida8bits, 7));
//     PORTB = salida8bits >> 6;
//   }

// //   delayMicroseconds(1000); // Muestreo de 1kHz (delay de 1000 uS - 1 ms)
// }


