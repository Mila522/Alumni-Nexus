import os
from pathlib import Path
from flask import Flask, request, render_template, redirect, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, StudentProfile, AlumniProfile

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get("SECRET_KEY", "fallback_secret_key")

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db.init_app(app)

with app.app_context():
    db.create_all()

# Upload folder
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def home():
    return render_template("home.html")


@app.route('/pinboard')
def pinboard():
    return render_template('pinboard.html')


@app.route('/mynetwork')
def mynetwork():
    return render_template('mynetwork.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        image = request.files.get('profile_image')

        if not all([name, email, password, role]):
            flash("All fields are required", "error")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        # default image
        image_filename = 'default-profile.png'

        # save uploaded image
        if image and image.filename != '':
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                unique_filename = f"{email}_{filename}"
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                image.save(image_path)
                image_filename = f"uploads/{unique_filename}"
            else:
                flash("Invalid image format. Please upload png, jpg, jpeg, or gif.", "error")
                return redirect(url_for('register'))

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            role=role,
            profile_image=image_filename
        )

        db.session.add(new_user)
        db.session.commit()

        if role == 'student':
            faculty = request.form.get('faculty')
            department = request.form.get('department')
            graduation_year = request.form.get('graduation_year')
            industry = request.form.get('industry')

            if not all([faculty, department, graduation_year, industry]):
                flash("Please fill in all student profile fields.", "error")
                db.session.delete(new_user)
                db.session.commit()
                return redirect(url_for('register'))

            student_profile = StudentProfile(
                user_id=new_user.user_id,
                faculty=faculty,
                department=department,
                graduation_year=int(graduation_year),
                industry=industry
            )

            db.session.add(student_profile)
            db.session.commit()

        elif role == 'alumni':
            headline = request.form.get('headline')
            experience = request.form.get('experience')
            career_interest = request.form.get('career_interest')
            level_of_study = request.form.get('level_of_study')

            if not all([headline, experience, career_interest, level_of_study]):
                flash("Please fill in all alumni profile fields.", "error")
                db.session.delete(new_user)
                db.session.commit()
                return redirect(url_for('register'))

            alumni_profile = AlumniProfile(
                user_id=new_user.user_id,
                headline=headline,
                experience=experience,
                career_interest=career_interest,
                level_of_study=level_of_study
            )

            db.session.add(alumni_profile)
            db.session.commit()

        flash("Registration successful.", "success")
        return redirect(url_for('profile', user_id=new_user.user_id))

    return render_template("registration.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not all([email, password]):
            flash("Missing email or password", "error")
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            flash(f"{user.name}, you've successfully logged in", "success")
            return redirect(url_for('profile', user_id=user.user_id))
        else:
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))

    return render_template("login.html")


@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template("profile.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)
