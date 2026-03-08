from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    user_id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(20), nullable=False)
    email=db.Column(db.String(30), unique=True, nullable=False)
    password=db.Column(db.String(8), nullable=False)

    role=db.Column(db.String(100), nullable=False)  # 'admin'or'alumni'or'student'

    faculty=db.Column(db.String(100))
    department=db.Column(db.String(100))
    graduation_year=db.Column(db.Integer)
    industry=db.Column(db.String(100))

    created_at=db.Column(db.DateTime, default=datetime.utcnow)


#CONNECTION REQUESTS
class Connection(db.Model):
    _tablename_="connections"
    connection_id=db.Column(db.Integer, primary_key=True)
    sender_id=db.Column(db.Integer, db.ForeignKey('users.user_id'))
    receiver_id=db.Column(db.Integer, db.ForeignKey('users.user_id'))
    status=db.Column(db.String(100), default='pending')  # 'pending', 'accepted', 'rejected'
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

    #MESSAGES
class Message(db.Model):
    __tablename__="messages"
    message_id=db.Column(db.Integer, primary_key=True)
    sender_id=db.Column(db.Integer, db.ForeignKey('users.user_id'))
    receiver_id=db.Column(db.Integer, db.ForeignKey('users.user_id'))
    message_text=db.Column(db.Text, nullable=False)
    sent_at=db.Column(db.DateTime, default=datetime.utcnow)


#MENTOR PROFILE
class MentorProfile(db.Model):
    __tablename__="mentor_profiles"
    mentor_id=db.Column(db.Integer,db.ForeignKey('users.user_id'), primary_key=True)
    expertise=db.Column(db.String(200))
    availability=db.Column(db.String(100))

    #MENTORSHIP REQUESTS
class MentorshipRequest(db.Model):
    __tablename__="mentorship_requests"
    request_id=db.Column(db.Integer, primary_key=True)
    student_id=db.Column(db.Integer, db.ForeignKey('users.user_id'))
    mentor_id=db.Column(db.Integer, db.ForeignKey('mentor_profiles.mentor_id'))
    status=db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected'
    request_date=db.Column(db.DateTime, default=datetime.utcnow)



