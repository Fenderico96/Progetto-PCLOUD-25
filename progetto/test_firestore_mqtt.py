from flask import Flask, jsonify, request
from flask_mqtt import Mqtt
from google.cloud import firestore
from datetime import datetime as dt
import json

# Initialize Flask app
app = Flask(__name__)

# Firestore Configuration
db = 'test1'
db = firestore.Client.from_service_account_json('progetto/credentials.json',database=db)
database = db 
database_local = []    #mi serve per vedere i dati che arrivano con la route /show
collection1 = 'Sensore Temperatura'
collection2 = 'Sensore Porta'

# MQTT Configuration
app.config['MQTT_BROKER_URL'] = 'broker.emqx.io'  # Change to your broker
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_KEEPALIVE'] = 60
app.config['MQTT_TOPIC'] = '/pcloud2025reggioemilia/test/#'

mqtt = Mqtt(app)

# Function to add document to Firestore
def add_document(data):
    #ogni volta che mi arriva un dato lo salvo in Firestore con data e ora così da poterlo visualizzare in un grafico e da gestire meglio l'allarme
    now = dt.now()
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


# Flask route
@app.route('/')
def home():
    return "Flask App with Flask-MQTT Integration!"

@app.route('/show')
def show():
    return str(database_local)

# Callback for MQTT message received
@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    msg_payload = message.payload.decode()  # Decodifica da bytes a stringa
    print(f"Received MQTT message: {msg_payload} on topic {message.topic}")

    # Analizza in base al tipo di topic
    if message.topic.endswith("door"):
        add_document(msg_payload)  # Stringa "OPEN" o "CLOSED"
    elif message.topic.endswith("temperature"):
        try:
            data = json.loads(msg_payload)  # {"Temperature": 24.0}
            if "Temperature" in data:
                add_document({"temperatura": data["Temperature"]})
            else:
                print("Chiave Temperature mancante")
        except json.JSONDecodeError:
            print("Errore nel parsing del JSON:", msg_payload)
    else:
        print("Topic non riconosciuto")

    # Salva localmente
    database_local.append(msg_payload)

    # Chiama callback Flask
    with app.test_request_context():
        response = mqtt_callback({"topic": message.topic, "message": msg_payload})
        print("Flask callback response:", response.get_json())

# Flask route to handle MQTT-triggered action
@app.route('/mqtt_callback', methods=['POST'])
def mqtt_callback(data=None):
    if data is None:
        data = request.json  # Get data from request if manually triggered
    print(f"Flask received MQTT callback: {data}")
    return jsonify({"status": "success", "received_data": data})

# Subscribe to MQTT topic on startup
@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    mqtt.subscribe(app.config['MQTT_TOPIC'])


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)