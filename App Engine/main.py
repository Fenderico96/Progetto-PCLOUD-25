from flask import Flask,jsonify,redirect, request
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from flask_mqtt import Mqtt
from mqtt_secret import mqttuser, mqttpass
from secret import secret_key
from google.cloud import firestore




# Initialize Flask app
app = Flask(__name__)

# MQTT Configuration
app.config['MQTT_BROKER_URL'] = '34.154.46.126'  # Change to your broker NBBBBBBBBB: l'ho promosso a indirizzo statico su GC così se succede qualcosa rimane quello (si spera)
app.config['MQTT_USERNAME'] = mqttuser
app.config['MQTT_PASSWORD'] = mqttpass
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_KEEPALIVE'] = 60
app.config['MQTT_TOPIC'] = '/progettopcloud2025/monterosso/#'

mqtt = Mqtt(app)

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
collection1 = 'Sensore Temperatura'
collection2 = 'Sensore Porta'



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


if __name__ == "__main__":
    app.run(debug=True)
