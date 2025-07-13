#include "WiFiS3.h"
#include "PubSubClient.h"
#include "arduino_secrets.h" 
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
//CREDENZIALI WIFI
const char* ssid = SECRET_SSID;
const char* password = SECRET_PASS;

// MQTT BROKER
const char* mqtt_server = "broker.emqx.io";


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
    if (client.connect("ArduinoClient")) {
      Serial.println("connesso");
    } else {
      Serial.print("fallito, rc=");
      Serial.print(client.state());
      Serial.println(" - Riprovo tra 5s");
      delay(5000);
    }
  }
}

void setup(){

  Serial.begin(9600);
  delay(1000);

  setup_wifi();
  client.setServer(mqtt_server, 1883);  // Porta standard MQTT



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
    Serial.print("°C");
    Serial.println("   "); 
  }
  

  //------------------------------MANDA DATI PORTA -----------------
  if (state != lastDoorState) {
    lastDoorState = state;

    if (state == HIGH) {
      Serial.println("DOOR OPEN");
      lcd.setCursor(0, 1);
      lcd.print("DOOR OPEN       ");
      client.publish("/pcloud2025reggioemilia/test/door", "OPEN");
    } else {
      Serial.println("DOOR CLOSED");
      lcd.setCursor(0, 1);
      lcd.print("DOOR CLOSED     ");
      client.publish("/pcloud2025reggioemilia/test/door", "CLOSED");
    }
  }

  //-------------------------------------- MANDA DATI TEMPERATURA -----------------------
  char payload[50];
  snprintf(payload, 50, "{\"Temperature\": %.2f}", tempC);

  client.publish("/pcloud2025reggioemilia/test/temperature", payload);
  Serial.print("Dati MQTT pubblicati: ");
  Serial.println(payload);








  delay(5000);
}
