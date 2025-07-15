#include "WiFiS3.h"
#include "PubSubClient.h"
#include "arduino_secret.h" 
#include <LiquidCrystal_I2C.h> 
#include "DHT.h"
#define DHT11_PIN 13  // Define the pin used to connect the sensor
#define DHTTYPE DHT11  // Define the type of the sensor


//COMPONENTS
int door_sensor =12;
int led = 7;
int buzzer = 4;
LiquidCrystal_I2C lcd(0x27, 16, 2); // I2C address 0x27, 16 column and 2 rows
DHT dht11(DHT11_PIN, DHT11);  // Create a DHT object
int lastDoorState = -1; //IMPOSTO UNO STATO INIZIALE DELLA PORTA INDEFINITO

//VARIABILI
bool alarmActive = false;
bool alarmOutput = false;
unsigned long previousMillis = 0;
unsigned long alarmStartMillis = 0;
const long blinkInterval = 300;     // LED/Buzzer ON/OFF ogni 300ms 
unsigned long lastTempPublishMillis = 0;
const unsigned long tempPublishInterval = 300000; //mando messaggio ogni 5 minuti

//CREDENZIALI WIFI
const char* ssid = SECRET_SSID;
const char* password = SECRET_PASS;


// MQTT BROKER E CREDENZIALI
const char* mqtt_server = "34.154.46.126";
const char* mqtt_user = SECRET_USER;
const char* mqtt_pass = SECRET_MQTT_PASS;


WiFiClient wifiClient;
PubSubClient client(wifiClient);


 //--------------- CONNESSIONE WIFI ------------------------------

void setup_wifi() {
  Serial.print("Connessione a ");
  Serial.println(ssid);

  while (WiFi.begin(ssid, password) != WL_CONNECTED) {
    Serial.print(".");
    delay(1000);
  }

  Serial.println("");
  Serial.println("WiFi connesso");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
 
}


//------------CONNESSIONE AL BROKER MQTT ------------------

void reconnect() {
  
  while (!client.connected()) {
    Serial.print("Connessione al broker MQTT...");
    if (client.connect("ArduinoClient", mqtt_user, mqtt_pass)) {
      Serial.println("connesso");
      // Sottoscrizione al topic di allarme
      client.subscribe("/progettopcloud2025/monterosso/alarm");
    } else {
      Serial.print("fallito, rc=");
      Serial.print(client.state());
      Serial.println(" - Riprovo tra 5s");
      delay(5000);
    }
  }
}




  //--------------------------------- CALLBACK PER ALLARME -----------------------
  void callback(char* topic, byte* payload, unsigned int length) {
  String message;

  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.print("Messaggio MQTT ricevuto su topic ");
  Serial.print(topic);
  Serial.print(": ");
  Serial.println(message);

  if (String(topic) == "/progettopcloud2025/monterosso/alarm") {
    if (message == "ON") {
      alarmActive = true;
      alarmStartMillis = millis(); // Solo se vuoi ancora farlo lampeggiare
      Serial.println("Allarme attivato");
    } else if (message == "OFF") {
      alarmActive = false;
      digitalWrite(led, LOW);
      digitalWrite(buzzer, LOW);
      Serial.println("Allarme disattivato");
    }
  }
}




void setup(){

  Serial.begin(9600);
  delay(1000);

  setup_wifi();
  client.setServer(mqtt_server, 1883);  // Porta standard MQTT
  client.setCallback(callback);


  //-------------------------- INIZIALIZZAZIONE SENSORI -----------------------
 
  pinMode(door_sensor, INPUT_PULLUP);

  pinMode(led, OUTPUT);

  pinMode(buzzer, OUTPUT);

  dht11.begin();
  
  lcd.init();        
  lcd.clear();       
  lcd.backlight();  

}



void loop() {

  if (!client.connected()) {
    reconnect();
  }
  client.loop();


  //------------------ DATI RILEVATI DA SENSORI --------------------------------
  float tempC = dht11.readTemperature();
  int state = digitalRead(door_sensor);

  //--------- MONITORAGGIO DEI DATI SU SERIAL MONITOR E LCD -------

 if (isnan(tempC)) {
    lcd.clear();
    Serial.println("Failed to read ");
    lcd.setCursor(0, 1);   
    lcd.print("Failed");
  } else {
    lcd.setCursor(0, 0);  
    lcd.print("Temp:");
    lcd.print(tempC);     
    lcd.print((char)223); 
    lcd.print("C");

    Serial.print(" Temperature: ");
    Serial.print(tempC);
    Serial.print("°C ");
    Serial.println("   "); 


  }
  

  //------------------------------MANDA DATI PORTA -----------------
  if (state != lastDoorState) {
    lastDoorState = state;
    if (state == HIGH) {
      Serial.println("DOOR OPEN");
      lcd.setCursor(0, 1);
      lcd.print("DOOR OPEN       ");
      client.publish("/progettopcloud2025/monterosso/door", "OPEN");
    } else {
      Serial.println("DOOR CLOSED");
      lcd.setCursor(0, 1);
      lcd.print("DOOR CLOSED     ");
      client.publish("/progettopcloud2025/monterosso/door", "CLOSED");
    }
  }

  //-------------------------------------- MANDA DATI TEMPERATURA -----------------------
  unsigned long currentMillis = millis();
  static unsigned long lastCriticalTempMillis = 0;
  const unsigned long criticalTempInterval = 20000;  // 20 secondi

  if (!isnan(tempC)) {
  bool shouldSend = false;

  if (tempC > 30.0) {
    if (currentMillis - lastCriticalTempMillis >= criticalTempInterval) {
      shouldSend = true;
      Serial.println("Temperatura sopra i 30°C! Inviata immediatamente.");
      lastCriticalTempMillis = currentMillis;
    }
  } else if (currentMillis - lastTempPublishMillis >= tempPublishInterval) {
    shouldSend = true;
    lastTempPublishMillis = currentMillis;
  }

  if (shouldSend) {
    char payload[50];
    snprintf(payload, 50, "{\"Temperature\": %.2f}", tempC);
    client.publish("/progettopcloud2025/monterosso/temperature", payload);
    Serial.print("Dati MQTT pubblicati: ");
    Serial.println(payload);
  }
}
 

  //-------------------------- ALLARME ------------------------------
    if (alarmActive) {
    lcd.clear();
    lcd.print("ALARM ENGAGED");

    unsigned long currentMillis = millis();
    
    if (currentMillis - previousMillis >= blinkInterval) {
      previousMillis = currentMillis;

      alarmOutput = !alarmOutput; // Inverte stato
      digitalWrite(led, alarmOutput);
      digitalWrite(buzzer, alarmOutput);
    }
  }



 delay(1000);


  
}
