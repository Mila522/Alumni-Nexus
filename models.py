from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime


db = SQLAlchemy()


# USER TABLE
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(100), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(100), nullable=False) 

    
    profile_image = db.Column(db.String(255), default='default-profile.png')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    
    student_profile = db.relationship(
        'StudentProfile',
        backref='user',
        uselist=False,
        cascade="all, delete-orphan"
    )

    alumni_profile = db.relationship(
        'AlumniProfile',
        backref='user',
        uselist=False,
        cascade="all, delete-orphan"
    )

    mentor_profile = db.relationship(
        'MentorProfile',
        backref='user',
        uselist=False,
        cascade="all, delete-orphan"
    )

    def get_id(self):
        return str(self.user_id)


# STUDENT PROFILE
class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id'),
        unique=True,
        nullable=False
    )

    faculty = db.Column(db.String(100), nullable=False)

    department = db.Column(db.String(100), nullable=False)

    graduation_year = db.Column(db.Integer, nullable=False)

    industry = db.Column(db.String(100), nullable=False)


# ALUMNI PROFILE
class AlumniProfile(db.Model):
    __tablename__ = 'alumni_profiles'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id'),
        unique=True,
        nullable=False
    )

    headline = db.Column(db.String(150), nullable=False)

    experience = db.Column(db.Text, nullable=False)

    career_interest = db.Column(db.String(150), nullable=False)

    level_of_study = db.Column(db.String(20), nullable=False)


# CONNECTION REQUESTS
class Connection(db.Model):
    __tablename__ = "connections"

    connection_id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id')
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id')
    )

    status = db.Column(
        db.String(100),
        default='pending'
    )  # pending | accepted | rejected

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# MESSAGES
class Message(db.Model):
    __tablename__ = "messages"

    message_id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id')
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id')
    )

    message_text = db.Column(
        db.Text,
        nullable=False
    )

    sent_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# MENTOR PROFILE
class MentorProfile(db.Model):
    __tablename__ = "mentor_profiles"

    mentor_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id'),
        primary_key=True
    )

    expertise = db.Column(db.String(200))

    availability = db.Column(db.String(100))


# MENTORSHIP REQUESTS
class MentorshipRequest(db.Model):
    __tablename__ = "mentorship_requests"

    request_id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id')
    )

    mentor_id = db.Column(
        db.Integer,
        db.ForeignKey('mentor_profiles.mentor_id')
    )

    status = db.Column(
        db.String(20),
        default='pending'
    )  # pending | accepted | rejected

    request_date = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Event(db.Model):
    __tablename__ = "events"

    event_id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)

    description = db.Column(db.Text)

    event_date = db.Column(db.DateTime)

    location = db.Column(db.String(200))
    created_by= db.Column(db.Integer, db.ForeignKey('users.user_id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RSVP(db.Model):
    __tablename__ = "rsvps"

    rsvp_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id')
    )

    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.event_id')
    )


    response = db.Column(
        db.String(20),
        default='going'
    )  # going| maybe | not_going

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
 )

#CREATE POST MODEL
class Post(db.Model):
    __tablename__ = "posts"

    post_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id')
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

   