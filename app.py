import os
from flask import Flask, jsonify, request, render_template, redirect, flash, url_for
from flask_login import login_required,LoginManager, login_user,current_user,logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from email_validator import validate_email, EmailNotValidError
from sqlalchemy import or_
from models import db, User, StudentProfile, AlumniProfile,Connection,Message,MentorProfile,MentorshipRequest,Event,RSVP,Post

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get("SECRET_KEY", "fallback_secret_key")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db.init_app(app)

with app.app_context():
    db.create_all()


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def home():
    return render_template("home.html")


@app.route('/mynetwork')
@login_required
def mynetwork():
    return render_template('mynetwork.html')

@app.route('/pinboard')
@login_required
def pinboard():
    return render_template('pinboard.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        image = request.files.get('profile_image')

        try:
            validate_email(email)
        except EmailNotValidError:
            flash("Invalid email address", "error")
            return redirect(url_for('register'))


        if not all([name, email, password, role]):
            flash("All fields are required", "error")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        
        image_filename = 'default-profile.png'

        
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

            login_user(user)   

            flash(f"{user.name}, you've successfully logged in", "success")

            return redirect(url_for('profile', user_id=user.user_id))

        else:
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))

    return render_template("login.html")


@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template("profile.html", user=user)

@app.route("/api/events",methods=["POST"])
@login_required
@login_required
def create_event():
    user_id = current_user.user_id
    data=request.get_json()

    event=Event(
        title=data.get("title"),
        description=data.get("description"),
        location=data.get("location"),
        event_date=data.get("event_date"),
        created_by=user_id
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({"message":"Event created successfully"})

@app.route("/api/events",methods=["GET"])
@login_required
def get_events():
    events=Event.query.all()
    results = []

    for e in events:
        results.append({
            "event_id": e.event_id,
            "title": e.title,
            "description": e.description,
            "location": e.location,
            "date": e.event_date
            })

    return jsonify(results)

@app.route("/api/events/<int:event_id>/rsvp",methods=["POST"])
@login_required
def rsvp_event(event_id):
    user_id = current_user.user_id

    rsvp=RSVP(
        user_id=user_id,
        event_id=event_id,
        status="going"
    )
    db.session.add(rsvp)
    db.session.commit()

    return jsonify({"message":"RSVP successful"})

@app.route("/api/posts",methods=["POST"])
@login_required
def create_post():
    user_id = current_user.user_id
    data=request.get_json()

    post=Post(
        user_id=user_id,
        content=data.get("content")
    )
    db.session.add(post)
    db.session.commit()
    return jsonify({"message":"Post created successfully"})

@app.route("/api/posts",methods=["GET"])
@login_required
def get_posts():
    posts=Post.query.order_by(Post.created_at.desc()).all()
    results = []

    for p in posts:
        results.append({
            "post_id": p.post_id,
            "user_id": p.user_id,
            "content": p.content,
            "created_at": p.created_at
            })

    return jsonify(results)

@app.route("/api/connect/<int:receiver_id>", methods=["POST"])
@login_required
def connect_user(receiver_id):

    sender_id = current_user.user_id

    existing = Connection.query.filter_by(
        sender_id=sender_id,
        receiver_id=receiver_id
    ).first()

    if existing:
        return jsonify({"message":"Connection request already sent"}), 400

    connection = Connection(
        sender_id=sender_id,
        receiver_id=receiver_id,
        status="pending"
    )

    db.session.add(connection)
    db.session.commit()

    return jsonify({"message":"Connection request sent successfully"})

@app.route("/api/connection-requests", methods=["GET"])
@login_required
def get_connection_requests():
    user_id = current_user.user_id
    requests = Connection.query.filter_by(receiver_id=user_id, status="pending").all()

    result = []
    for req in requests:
        sender = User.query.get(req.sender_id)
        result.append({
            "id": req.connection_id,
            "name": sender.name
        })

    return jsonify(result)

@app.route("/api/connection-requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(request_id):
    connection = Connection.query.get_or_404(request_id)
    if connection.receiver_id != current_user.user_id:
        return jsonify({"error":"Unauthorized"}), 403

    connection.status = "accepted"
    db.session.commit()
    return jsonify({"message":"Request accepted"})

@app.route("/api/connection-requests/<int:request_id>/decline", methods=["POST"])
@login_required
def decline_request(request_id):
    connection = Connection.query.get_or_404(request_id)
    if connection.receiver_id != current_user.user_id:
        return jsonify({"error":"Unauthorized"}), 403

    db.session.delete(connection)
    db.session.commit()
    return jsonify({"message":"Request declined"})

@app.route("/api/suggestions",methods=["GET"])
@login_required
def get_suggestions():

    user_id = current_user.user_id

    users = User.query.filter(User.user_id != user_id).limit(5).all()

    result = []

    for u in users:

        industry = "Unknown"

        if u.student_profile:
            industry = u.student_profile.industry

        result.append({
            "id": u.user_id,
            "name": u.name,
            "industry": industry
        })

    return jsonify(result)

@app.route("/api/network-stats",methods=["GET"])
@login_required
def get_network_stats():
    user_id = current_user.user_id
    total=Connection.query.filter_by(sender_id=user_id,status="accepted").count()
    pending=Connection.query.filter_by(receiver_id=user_id,status="pending").count()
    suggestions=User.query.count() -1
    return jsonify({
        "total_connections": total,
        "pending_requests": pending,
        "suggestions": suggestions
    })@app.route("/api/network-stats",methods=["GET"])
@login_required
def get_network_stats():

    user_id = current_user.user_id

    total = Connection.query.filter(
        ((Connection.sender_id == user_id) | (Connection.receiver_id == user_id)) &
        (Connection.status == "accepted")
    ).count()

    pending = Connection.query.filter_by(
        receiver_id=user_id,
        status="pending"
    ).count()

    suggestions = User.query.count() - 1

    return jsonify({
        "total_connections": total,
        "pending_requests": pending,
        "suggestions": suggestions
    })
@app.route("/api/search", methods=["GET"])
def search_users():

    query = request.args.get("q", "")
    role = request.args.get("role", "")
    industry = request.args.get("industry", "")
    faculty = request.args.get("faculty", "")
    graduation_year = request.args.get("year", "")

    users = db.session.query(User)\
        .outerjoin(StudentProfile)\
        .outerjoin(AlumniProfile)

    if query:
        users = users.filter(
            or_(
                User.name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        )

    if role:
        users = users.filter(User.role == role)

    if industry:
        users = users.filter(StudentProfile.industry.ilike(f"%{industry}%"))

    if faculty:
        users = users.filter(StudentProfile.faculty.ilike(f"%{faculty}%"))

    if graduation_year:
        users = users.filter(StudentProfile.graduation_year == graduation_year)

    results = []

    for user in users.all():

        industry_val = None
        faculty_val = None
        year_val = None

        if user.student_profile:
            industry_val = user.student_profile.industry
            faculty_val = user.student_profile.faculty
            year_val = user.student_profile.graduation_year

        results.append({
            "id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "industry": industry_val,
            "faculty": faculty_val,
            "graduation_year": year_val
        })

    return jsonify(results)

@app.route("/api/my-connections", methods=["GET"])
@login_required
def my_connections():
    user_id = current_user.user_id

    connections = Connection.query.filter(
        ((Connection.sender_id == user_id) | (Connection.receiver_id == user_id)) &
        (Connection.status == "accepted")
    ).all()

    result = []
    for c in connections:
        # Get the other user in the connection
        other_id = c.receiver_id if c.sender_id == user_id else c.sender_id
        other_user = User.query.get(other_id)
        result.append({
            "id": other_user.user_id,
            "name": other_user.name,
            "email": other_user.email
        })

    return jsonify(result)
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out", "success")
    return redirect(url_for('login'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))




if __name__ == "__main__":
    app.run(debug=True)
