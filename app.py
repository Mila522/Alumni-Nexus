from flask import Flask, request, jsonify, render_template
from werkzeug.security import generate_password_hash,check_password_hash
from config import Config
from models import db, User,Connection, Message,MentorshipRequest




app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# Home Route
@app.route("/")
def home():
    return render_template("home.html")

#Register User
@app.route("/api/register", methods=['POST']) 
def register():
    data = request.get_json()
    user=User(
        name=data['Name'],
        email=data['Email'],
        role=data['Role'],
        faculty=data.get('Faculty'),
        department=data.get('Department'),
       
   )
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"})

   #Login
@app.route("/api/login", methods=['POST'])
def login():
    data = request.get_json()
    user=User.query.filter_by(email=data['Email']).first()
    if user:
        if check_password_hash(user.password, data['Password']):
            return jsonify({"message": "Login successful","role": user.role})
        else:
            return jsonify({"message": "Invalid email or password"}), 404
        
#Get all users
@app.route("/api/users", methods=['GET'])
def get_users(): 
    users=User.query.all()
    results=[]
    for user in users:
        results.append({
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "faculty": user.faculty,
            "department": user.department,
            
        })
    return jsonify(results)

    
   
#Send connection request    
@app.route("/api/connect", methods=['POST'])
def connect():
    data = request.get_json()

    connection= Connection(
        sender_id=data['sender_id'],
        receiver_id=data['receiver_id'],
        status='pending'
    )
    db.session.add(connection)
    db.session.commit()

    return jsonify({"message": "Connection request sent successfully"})

#Accept or reject connection request
@app.route("/api/connect/accept", methods=['POST'])
def accept_connection():
    data = request.get_json()
    connection=Connection.query.filter_by(connection_id=data['connection_id']).first()
    if not connection:
        return jsonify({"message": "Connection request not found"}), 404
    connection.status='accepted'
    db.session.commit()
    return jsonify({"message": "Connection request accepted successfully"})

#Send message
@app.route("/api/message", methods=['POST'])
def send_message():
    data = request.get_json()
    message=Message(
        sender_id=data['sender_id'],
        receiver_id=data['receiver_id'],
        message_text=data['message_text']
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({"message": "Message sent successfully"})

#Mentorship request
@app.route("/api/mentorship/request", methods=['POST'])
def mentorship_request():
    data = request.get_json()
    mentorship_request=MentorshipRequest(
        student_id=data['student_id'],
        mentor_id=data['mentor_id'],
        status='pending'
    )
    db.session.add(mentorship_request)
    db.session.commit()

    return jsonify({"message": "Mentorship request sent successfully"})

#Run Server
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)    