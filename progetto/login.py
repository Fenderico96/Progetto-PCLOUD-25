
from flask import Flask,redirect,url_for, request, render_template
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from secret import secret_key
from google.cloud import firestore


db = 'test1'
db = firestore.Client.from_service_account_json('progetto/credentials.json', database=db)


app = Flask(__name__)
app.config['SECRET_KEY'] = secret_key


login = LoginManager(app)
login.login_view = '/static/login.html'   #ho dovuto cambiare il nome da template a static per farlo funzionare 

class User(UserMixin):
    def __init__(self, username):
        super().__init__()
        self.id = username
        self.username = username


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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

