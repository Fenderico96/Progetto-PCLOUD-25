from google.cloud import firestore
from datetime import datetime as dt

db = 'test1'
db = firestore.Client.from_service_account_json('progetto/credentials.json',database=db)
collection1 = 'Sensore Temperatura'
collection2 = 'Sensore Porta'

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
        print("Formato dati non valido.")
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


add_document("OPEN")
add_document("CLOSED")
add_document({"temperatura": 24})
