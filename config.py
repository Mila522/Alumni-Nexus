import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "IDEA-LAB"
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'alumni.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECURITY_PASSWORD_SALT= 'your-password-salt-here-change-this-in-production'
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME= 'minenhlebhekane@gmail.com'  # Change this
    MAIL_PASSWORD = 'qgiqafzvdoconjul'     # Change this
    MAIL_DEFAULT_SENDER = 'minenhlebhekane@gmail.com'  # Change this
