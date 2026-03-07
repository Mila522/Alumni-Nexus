from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash,check_password_hash
from config import Config
from models import db, User


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()

    @app.route('/')
    def home():
        return "Alumni Nexus running"
    
    if __name__ == '__main__':
        app.run(debug=True)

@app.route("/register", methods=['POST']) 
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')  # 'admin', 'alumni', 'student'
   

    if not all([name, email, password, role]):
        return jsonify({"message": "Missing required fields"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 400

    hashed_password = generate_password_hash(password)
    new_user = User(
    name=name,
    email=email,
    password=hashed_password,
    role=role
      )
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"})  

@app.route("/login", methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"message": "Missing email or password"}), 400

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        return jsonify({"message": "Login successful","role": user.role})
    else:
        return jsonify({"message": "Invalid email or password"}), 401