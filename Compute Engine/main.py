from flask import Flask
from flask_mqtt import Mqtt
from mqtt_secret import mqttuser, mqttpass
from google.cloud import firestore
from datetime import datetime as dt
import json
import threading
import pytz



#variabili globali
door_state = "CLOSED"  # Stato iniziale della porta
open_timer = None  # Timer for door open state
temp_timer = None  # Timer for temperature alarm
alarm_sent = False  # Flag to check if alarm has been sent


# Initialize Flask app
app = Flask(__name__)

# Firestore Configuration
db = 'progetto'
db = firestore.Client.from_service_account_json('credentials.json', database=db)
database = db 
collection1 = 'Sensore Temperatura'
collection2 = 'Sensore Porta'

# MQTT Configuration
app.config['MQTT_BROKER_URL'] = '34.154.46.126'  # Change to your broker NBBBBBBBBB: l'ho promosso a indirizzo statico su GC così se succede qualcosa rimane quello (si spera)
app.config['MQTT_USERNAME'] = mqttuser
app.config['MQTT_PASSWORD'] = mqttpass
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_KEEPALIVE'] = 60
app.config['MQTT_TOPIC'] = '/progettopcloud2025/monterosso/#'

mqtt = Mqtt(app)



#----------------------------------------------------------- FIRESTORE FUNCTIONS ---------------------------------------------------------


# Function to add document to Firestore
def add_data(data):
    #ogni volta che mi arriva un dato lo salvo in Firestore con data e ora così da poterlo visualizzare in un grafico e da gestire meglio l'allarme
    italy_tz = pytz.timezone('Europe/Rome')
    now = dt.now(italy_tz)
    day = now.strftime("%d-%m-%Y")
    hour = now.strftime("%H:%M")    
    # Determina la collezione in base al tipo di dato (Questo if determina il tipo di dato che si vuole salvare e lo smista tra le collezioni)
    if isinstance(data, str):
        collection = collection2
        doc_ref = db.collection(collection).document(day)
        new_entry = {"stato": data, "ora": hour}

    elif isinstance(data, dict) and "temperatura" in data:
        collection = collection1
        doc_ref = db.collection(collection).document(day)
        new_entry = {"temperatura": str(data["temperatura"]), "ora": hour}

    else:
        print(f"Formato dati non valido: {data} (type: {type(data)})")
        return
    
    #Controlla se il documento esiste o crea uno nuovo se non esiste
    doc = doc_ref.get()
    if doc.exists:
        existing_data = doc.to_dict().get("dati", [])
    else:
        existing_data = []

    existing_data.append(new_entry)
    doc_ref.set({"dati": existing_data})
    print(f"Dato salvato in {collection}/{day}: {new_entry}") #check per vedere se la cosa va in porto

def add_problem(tipo):
    italy_tz = pytz.timezone('Europe/Rome')
    now = dt.now(italy_tz)
    day = now.strftime("%d-%m-%Y")
    hour = now.strftime("%H:%M")    
    collection = 'Problemi'
    doc_ref = db.collection(collection).document(day)
    new_entry = {"tipo": tipo, "ora": hour}

    #Controlla se il documento esiste o crea uno nuovo se non esiste
    doc = doc_ref.get()
    if doc.exists:
        existing_data = doc.to_dict().get("dati", [])
    else:
        existing_data = []

    existing_data.append(new_entry)
    doc_ref.set({"dati": existing_data})
    print(f"Problema salvato in {collection}/{day}: {new_entry}") #check per vedere se la cosa va in porto


def send_alarm_to_arduino():
    global alarm_sent,open_timer
    if door_state != "CLOSED":
        print(" Porta ancora aperta dopo 30 secondi. Invio allarme ad Arduino.")
        mqtt.publish("/progettopcloud2025/monterosso/alarm", "ON")
        add_problem("Porta aperta troppo a lungo")
        alarm_sent = True
        open_timer = None  # Reset timer after sending alarm

def set_tempAlarmOFF(): #prima avevo messo un timer di 20 secondi(time.sleep(20)) direttamente nella route ma mi dava problemi con il publish dell'allarme
    global temp_timer
    mqtt.publish("/progettopcloud2025/monterosso/alarm", "OFF")  # Spegni l'allarme
    print("Allarme temperatura spento.")
    temp_timer = None  # Reset timer after sending alarm



#--------------------------------------------------------- MQTT ---------------------------------------------------------


# Callback for MQTT message received
@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    global door_state, open_timer, alarm_sent, temp_timer
    msg_payload = message.payload.decode()
    print(f"Received MQTT message: {msg_payload} on topic {message.topic}")

    if message.topic.endswith("door"):
        door_state = msg_payload
        if door_state == "OPEN":
            alarm_sent = False
            if open_timer is None:
                open_timer = threading.Timer(30.0, send_alarm_to_arduino)
                open_timer.daemon = True
                open_timer.start()
        elif door_state == "CLOSED":
            if open_timer is not None:
                open_timer.cancel()
                open_timer = None
            if alarm_sent:
                mqtt.publish("/progettopcloud2025/monterosso/alarm", "OFF")  # Reset alarm
                alarm_sent = False
                print("Porta richiusa dopo allarme.")

        add_data(msg_payload)

    elif message.topic.endswith("temperature"):
        try:
            data = json.loads(msg_payload)
            if "Temperature" in data:
                temp_value = data["Temperature"]
                add_data({"temperatura": temp_value})

                if temp_value > 30:
                    print(f"Temperatura alta: {temp_value}°C. Invio allarme.")
                    mqtt.publish("/progettopcloud2025/monterosso/alarm", "ON")   #qui metto un publish diretto al topic dell'allarme perchè così posso inviare il dato con il tipo "Temperatura alta", mentre la funzione di allarme mi manda l'altro tipo ovvero "Porta aperta troppo a lungo"
                    add_problem("Temperatura alta")
                    add_data({"temperatura": temp_value})
                    if temp_timer is None:
                        temp_timer = threading.Timer(30.0, set_tempAlarmOFF)
                        temp_timer.daemon = True
                        temp_timer.start()
                   

            else:
                print("Chiave Temperature mancante")
        except json.JSONDecodeError:
            print("Errore nel parsing del JSON:", msg_payload)


# Subscribe to MQTT topic on startup
@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    mqtt.subscribe(app.config['MQTT_TOPIC'])


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
