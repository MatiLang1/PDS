//CODIGO A CARGAR EN EL ARDUINO

void setup() {
  Serial.begin(115200); // Velocidad alta para no perder datos
}

void loop() {
  int sensorValue = analogRead(A0); // Lee la señal adaptada
  Serial.println(sensorValue);    // Envía el dato a la PC
  delayMicroseconds(1000);        // Muestreo aproximado de 1kHz
}