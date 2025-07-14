from flask import Flask, jsonify, request
from flask_mqtt import Mqtt
from google.cloud import firestore

app = Flask(__name__)

db = 'test1'
db = firestore.Client.from_service_account_json('progetto/credentials.json', database=db)

database = []

# MQTT Configuration
app.config['MQTT_BROKER_URL'] = 'broker.emqx.io'  # Change to your broker
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_KEEPALIVE'] = 60
app.config['MQTT_TOPIC'] = '/pcloud2025reggioemilia/test/#'

mqtt = Mqtt(app)

# Flask route
@app.route('/')
def home():
    return "Flask App with Flask-MQTT Integration!"

@app.route('/show')
def show():
    return str(database)
      
# Callback for MQTT message received
@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    msg_payload = message.payload.decode()
    print(f"Received MQTT message: {msg_payload} on topic {message.topic}")
    database.append(msg_payload)  

    # Call a Flask endpoint programmatically
    with app.test_request_context():
        response = mqtt_callback({"topic": message.topic, "message": msg_payload})
        print("Flask callback response:", response.get_json())


# Subscribe to MQTT topic on startup
@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    mqtt.subscribe(app.config['MQTT_TOPIC'])

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)