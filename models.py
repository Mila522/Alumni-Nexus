from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ────────────────────────────────────────────────
# USER TABLE
# ────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # student / alumni / mentor / ...

    profile_image = db.Column(db.String(255), default='default-profile.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_profile = db.relationship(
        'StudentProfile', backref='user', uselist=False, cascade="all, delete-orphan"
    )
    alumni_profile = db.relationship(
        'AlumniProfile', backref='user', uselist=False, cascade="all, delete-orphan"
    )
    mentor_profile = db.relationship(
        'MentorProfile', backref='user', uselist=False, cascade="all, delete-orphan"
    )
    mentor_applications = db.relationship(
        'MentorApplication', backref='user', lazy=True, cascade="all, delete-orphan"
    )

    posts = db.relationship(
        'Post', backref='author', lazy=True, cascade="all, delete-orphan"
    )
    post_likes = db.relationship(
        'PostLike', backref='user', lazy=True, cascade="all, delete-orphan"
    )
    post_comments = db.relationship(
        'PostComment', backref='user', lazy=True, cascade="all, delete-orphan"
    )

    def get_id(self):
        return str(self.user_id)


# ────────────────────────────────────────────────
# STUDENT PROFILE
# ────────────────────────────────────────────────
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


# ────────────────────────────────────────────────
# ALUMNI PROFILE
# ────────────────────────────────────────────────
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
    education = db.Column(db.Text, nullable=True)
    experience = db.Column(db.Text, nullable=False)
    career_interest = db.Column(db.String(150), nullable=False)
    level_of_study = db.Column(db.String(50), nullable=False)

    skills = db.Column(db.Text, nullable=True)
    certifications = db.Column(db.Text, nullable=True)
    linkedin_url = db.Column(db.String(255), nullable=True)


# ────────────────────────────────────────────────
# MENTOR PROFILE
# ────────────────────────────────────────────────
class MentorProfile(db.Model):
    __tablename__ = 'mentor_profiles'

    mentor_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id'),
        primary_key=True
    )

    expertise = db.Column(db.String(100), nullable=True)


# ────────────────────────────────────────────────
# MENTOR APPLICATIONS
# ────────────────────────────────────────────────
class MentorApplication(db.Model):
    __tablename__ = 'mentor_applications'

    application_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    status = db.Column(db.String(20), default='pending')  # pending / approved / rejected
    expertise = db.Column(db.String(100), nullable=False)  # Information Technology / Business / Engineering
    motivation = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────
# CONNECTIONS
# ────────────────────────────────────────────────
class Connection(db.Model):
    __tablename__ = 'connections'

    connection_id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────
# MESSAGES
# ────────────────────────────────────────────────
class Message(db.Model):
    __tablename__ = 'messages'

    message_id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    message_text = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────
# MENTORSHIP REQUESTS
# ────────────────────────────────────────────────
class MentorshipRequest(db.Model):
    __tablename__ = 'mentorship_requests'

    request_id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('mentor_profiles.mentor_id'), nullable=False)

    status = db.Column(db.String(20), default='pending')
    request_date = db.Column(db.DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────
# EVENTS & RSVPs
# ────────────────────────────────────────────────
class Event(db.Model):
    __tablename__ = 'events'

    event_id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(200), nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RSVP(db.Model):
    __tablename__ = 'rsvps'

    rsvp_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.event_id'), nullable=False)

    response = db.Column(db.String(20), default='going')  # going / maybe / not_going
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'event_id', name='unique_user_event_rsvp'),
    )


# ────────────────────────────────────────────────
# POSTS (Pinboard)
# ────────────────────────────────────────────────
class Post(db.Model):
    __tablename__ = 'posts'

    post_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments = db.relationship(
        'PostComment', backref='post', lazy=True, cascade="all, delete-orphan"
    )
    likes = db.relationship(
        'PostLike', backref='post', lazy=True, cascade="all, delete-orphan"
    )


class PostLike(db.Model):
    __tablename__ = 'post_likes'

    id = db.Column(db.Integer, primary_key=True)

    post_id = db.Column(db.Integer, db.ForeignKey('posts.post_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='unique_like'),
    )


class PostComment(db.Model):
    __tablename__ = 'post_comments'

    id = db.Column(db.Integer, primary_key=True)

    post_id = db.Column(db.Integer, db.ForeignKey('posts.post_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    is_deleted = db.Column(db.Boolean, default=False)