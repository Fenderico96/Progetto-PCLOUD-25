from flask import Flask,jsonify,redirect,url_for, request, render_template
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from flask_mqtt import Mqtt
from secret import secret_key
from mqtt_secret import mqttuser, mqttpass
from google.cloud import firestore
from datetime import datetime as dt
import json
import threading
from zoneinfo import ZoneInfo       #per gestire il fuso orario di Roma sennò app engine salva i dati in UTC e sono 2 ore indietro

now = dt.now(ZoneInfo("Europe/Rome"))


#variabili globali
door_state = "CLOSED"  # Stato iniziale della porta
open_timer = None  # Timer for door open state
temp_timer = None  # Timer for temperature alarm
alarm_sent = False  # Flag to check if alarm has been sent


# Initialize Flask app
app = Flask(__name__)

# Flask Login Configuration
app.config['SECRET_KEY'] = secret_key
login = LoginManager(app)
login.login_view = '/static/login.html'   #ho dovuto cambiare il nome da template a static per farlo funzionare 

class User(UserMixin):
    def __init__(self, username):
        super().__init__()
        self.id = username
        self.username = username

# Firestore Configuration
db = 'progetto'
db = firestore.Client(database=db)
database = db 
database_local = []    #mi serve per vedere i dati che arrivano con la route /show
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
    now = dt.now(ZoneInfo("Europe/Rome"))
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
    now = dt.now(ZoneInfo("Europe/Rome"))
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

#---------------------------------------------------------- FLASK ROUTES --------------------------------------------------------- 

@login.user_loader
def load_user(username):
    user_doc = db.collection('Login').document(username).get()
    if user_doc.exists:
        return User(username)
    return None


@app.route('/')
def root():
    if current_user.is_authenticated:
        return redirect('/main')         #messo per evitare che se l'utente è loggato vada alla pagina di login
    else:
        return redirect('/static/start.html')

@app.route('/main')
@login_required
def index():
    return redirect('/static/hub.html')


@app.route('/login', methods=['GET','POST'])   #metodo GET messo solo se in caso si volesse fare /login sulla barra degli indirizzi per evitare errore 405
def login_route():
    if current_user.is_authenticated:
        return redirect('/main')

    username = request.form.get('u')     #cambiato da .values a .form.get per evitare errori se il campo non esiste
    password = request.form.get('p')
    next_page = request.form.get('next')

    # Check credenziali
    print(f"[DEBUG] Tentativo login con username='{username}', password='{password}'")
    user_doc = db.collection('Login').document(username).get()
    print(f"[DEBUG] User trovato: {user_doc.exists}")
    if user_doc.exists:
        user_data = user_doc.to_dict()
        stored_password = user_data.get('Password')
        print(f"[DEBUG] Password dal DB: '{stored_password}'")
        if stored_password == password:
            print("[DEBUG] Login riuscito")
            login_user(User(username))
            return redirect(next_page)

    print("[DEBUG] Login fallito")
    return "Invalid username or password", 401


@app.route('/logout')
def logout():
    logout_user()
    return redirect('/static/start.html')

@app.route('/show')
def show():
    return str(database_local)


@app.route('/toggle_alarm', methods=['POST'])
def toggle_alarm():
    state = request.json.get("state")
    if state == "ON":
        mqtt.publish("/progettopcloud2025/monterosso/alarm", "ON")
    elif state == "OFF":
        mqtt.publish("/progettopcloud2025/monterosso/alarm", "OFF")
    else:
        return jsonify({"error": "Invalid state"}), 400
    return jsonify({"status": "Alarm toggled", "state": state})


@app.route('/get_temperature_data')
@login_required
def get_temperature_data():
    docs = db.collection('Sensore Temperatura').stream()
    result = []
    for doc in docs:
        day = doc.id  # es: '12-07-2025'
        entries = doc.to_dict().get("dati", [])
        for entry in entries:
            result.append({
                "date": "-".join(reversed(day.split("-"))),  # diventa '2025-07-12' perchè chart.js vuole il formato YYYY-MM-DD
                "time": entry["ora"],
                "temp": float(entry["temperatura"])
            })
    return jsonify(result)


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
                    if temp_timer is None:
                        temp_timer = threading.Timer(30.0, set_tempAlarmOFF)
                        temp_timer.start()
                   

            else:
                print("Chiave Temperature mancante")
        except json.JSONDecodeError:
            print("Errore nel parsing del JSON:", msg_payload)

    database_local.append(msg_payload)

    with app.test_request_context():
        response = mqtt_callback({"topic": message.topic, "message": msg_payload})
        print("Flask callback response:", response.get_json())

# Flask route to handle MQTT-triggered action
@app.route('/mqtt_callback', methods=['POST'])
def mqtt_callback(data=None):
    if data is None:
        data = request.json  # Get data from request if manually triggered
    #print(f"Flask received MQTT callback: {data}")
    return jsonify({"status": "success", "received_data": data})

# Subscribe to MQTT topic on startup
@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    mqtt.subscribe(app.config['MQTT_TOPIC'])


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)