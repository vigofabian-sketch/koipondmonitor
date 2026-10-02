#include <OneWire.h>
#include <DallasTemperature.h>
#include <RTClib.h>

OneWire oneWire(2);
DallasTemperature temp(&oneWire);
RTC_DS1307 rtc;

void setup() {
  Serial.begin(9600);
  temp.begin();
  rtc.begin();
  rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  Serial.println("timestamp,temp_c,ph,turbidity");
}

void loop() {
  temp.requestTemperatures();
  float t = temp.getTempCByIndex(0);
  float ph = 14.0 * analogRead(A0) / 1023.0;
  float turb = 100.0 * analogRead(A1) / 1023.0;
  Serial.print(rtc.now().timestamp());
  Serial.print(",");
  Serial.print(t);
  Serial.print(",");
  Serial.print(ph);
  Serial.print(",");
  Serial.println(turb);
  delay(2000);
}