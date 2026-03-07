from flask import Flask, request, jsonify, render_template, redirect, flash
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get("SECRET_KEY", "fallback_secret_key")


db.init_app(app)

with app.app_context():
    db.create_all()


@app.route('/')
def home():
     return render_template("home.html")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if not all([name, email, password, role]):
            flash("All fields are required", "error")
            return redirect('/register')

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return redirect('/register')

        hashed_password = generate_password_hash(password)

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            role=role
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful.", "success")
        return redirect('/login')

    return render_template("registration.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not all([email, password]):
            flash("Missing email or password", "error")
            return redirect('/login')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            flash("Login successful", "success")
            return f"Welcome {user.name}, your role is {user.role}"
        else:
            flash("Invalid email or password", "error")
            return redirect('/login')

    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True)
