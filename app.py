import os
from datetime import datetime

from flask import Flask, jsonify, request, render_template, redirect, flash, url_for
from flask_login import login_required, LoginManager, login_user, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from config import Config
from email_validator import validate_email, EmailNotValidError
from models import db, User, StudentProfile, AlumniProfile, Connection, Message, MentorProfile, MentorshipRequest, Event, RSVP, Post, PostLike, PostComment


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


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_connection_status(target_id):
    if current_user.user_id == target_id:
        return "self"

    conn = Connection.query.filter(
        ((Connection.sender_id == current_user.user_id) & (Connection.receiver_id == target_id)) |
        ((Connection.sender_id == target_id) & (Connection.receiver_id == current_user.user_id))
    ).first()

    if not conn:
        return "none"

    if conn.status == "accepted":
        return "connected"

    if conn.sender_id == current_user.user_id:
        return "pending_sent"
    else:
        return "pending_received"
    
def are_users_connected(user1_id, user2_id):
    connection = Connection.query.filter(
        (
            ((Connection.sender_id == user1_id) & (Connection.receiver_id == user2_id)) |
            ((Connection.sender_id == user2_id) & (Connection.receiver_id == user1_id))
        ) &
        (Connection.status == "accepted")
    ).first()

    return connection is not None

@app.route("/messages/<int:user_id>")
@login_required
def message_page(user_id):
    other_user = User.query.get_or_404(user_id)

    if current_user.user_id == other_user.user_id:
        flash("You cannot message yourself.", "error")
        return redirect(url_for("profile", user_id=current_user.user_id))

    if not are_users_connected(current_user.user_id, other_user.user_id):
        flash("You can only message users you are connected with.", "error")
        return redirect(url_for("profile", user_id=other_user.user_id))

    return render_template("message.html", other_user=other_user)

@app.route("/api/messages/<int:user_id>", methods=["GET"])
@login_required
def get_conversation(user_id):
    other_user = User.query.get_or_404(user_id)

    if current_user.user_id == other_user.user_id:
        return jsonify({"error": "You cannot message yourself"}), 400

    if not are_users_connected(current_user.user_id, other_user.user_id):
        return jsonify({"error": "You can only view conversations with connected users"}), 403

    messages = Message.query.filter(
        ((Message.sender_id == current_user.user_id) & (Message.receiver_id == other_user.user_id)) |
        ((Message.sender_id == other_user.user_id) & (Message.receiver_id == current_user.user_id))
    ).order_by(Message.sent_at.asc()).all()

    results = []
    for msg in messages:
        results.append({
            "message_id": msg.message_id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "message_text": msg.message_text,
            "sent_at": msg.sent_at.strftime("%Y-%m-%d %H:%M"),
            "is_mine": msg.sender_id == current_user.user_id
        })

    return jsonify(results)

@app.route("/api/messages/<int:user_id>", methods=["POST"])
@login_required
def send_message(user_id):
    other_user = User.query.get_or_404(user_id)

    if current_user.user_id == other_user.user_id:
        return jsonify({"error": "You cannot message yourself"}), 400

    if not are_users_connected(current_user.user_id, other_user.user_id):
        return jsonify({"error": "You can only message users you are connected with"}), 403

    data = request.get_json()
    message_text = data.get("message_text", "").strip()

    if not message_text:
        return jsonify({"error": "Message cannot be empty"}), 400

    new_message = Message(
        sender_id=current_user.user_id,
        receiver_id=other_user.user_id,
        message_text=message_text
    )

    db.session.add(new_message)
    db.session.commit()

    return jsonify({
        "message": "Message sent successfully",
        "message_id": new_message.message_id
    }), 201


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
    status = get_connection_status(user_id)
    return render_template("profile.html", user=user, connection_status=status)


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        name = request.form.get("name")
        image = request.files.get("profile_image")

        if name:
            current_user.name = name

        if image and image.filename and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            unique = f"{current_user.email}_{filename}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], unique)
            image.save(path)
            current_user.profile_image = f"uploads/{unique}"

        if current_user.role == "student" and current_user.student_profile:
            current_user.student_profile.faculty = request.form.get("faculty", current_user.student_profile.faculty)
            current_user.student_profile.department = request.form.get("department", current_user.student_profile.department)

            gy = request.form.get("graduation_year")
            if gy and gy.isdigit():
                current_user.student_profile.graduation_year = int(gy)

            current_user.student_profile.industry = request.form.get("industry", current_user.student_profile.industry)

        elif current_user.role == "alumni" and current_user.alumni_profile:
            current_user.alumni_profile.headline = request.form.get("headline", current_user.alumni_profile.headline)
            current_user.alumni_profile.experience = request.form.get("experience", current_user.alumni_profile.experience)
            current_user.alumni_profile.career_interest = request.form.get("career_interest", current_user.alumni_profile.career_interest)
            current_user.alumni_profile.level_of_study = request.form.get("level_of_study", current_user.alumni_profile.level_of_study)
            current_user.alumni_profile.education = request.form.get("education")
            current_user.alumni_profile.skills = request.form.get("skills")
            current_user.alumni_profile.certifications = request.form.get("certifications")
            current_user.alumni_profile.linkedin_url = request.form.get("linkedin_url")

        db.session.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for("profile", user_id=current_user.user_id))

    return render_template("edit_profile.html", user=current_user)


# ────────────────────────────────────────────────
# EVENTS
# ────────────────────────────────────────────────
@app.route("/api/events", methods=["POST"])
@login_required
def create_event():
    user_id = current_user.user_id
    data = request.get_json()

    event_date = None
    if data.get("event_date"):
        try:
            event_date = datetime.fromisoformat(data.get("event_date"))
        except ValueError:
            return jsonify({"error": "Invalid event date format"}), 400

    event = Event(
        title=data.get("title"),
        description=data.get("description"),
        location=data.get("location"),
        event_date=event_date,
        created_by=user_id
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({"message": "Event created successfully"})


@app.route("/api/events", methods=["GET"])
@login_required
def get_events():
    events = Event.query.all()
    results = []

    for e in events:
        results.append({
            "event_id": e.event_id,
            "title": e.title,
            "description": e.description,
            "location": e.location,
            "date": e.event_date.isoformat() if e.event_date else None
        })

    return jsonify(results)


@app.route("/api/events/<int:event_id>/rsvp", methods=["POST"])
@login_required
def rsvp_event(event_id):
    user_id = current_user.user_id

    existing_rsvp = RSVP.query.filter_by(user_id=user_id, event_id=event_id).first()
    if existing_rsvp:
        return jsonify({"message": "You have already RSVPed for this event"}), 400

    rsvp = RSVP(
        user_id=user_id,
        event_id=event_id,
        response="going"
    )
    db.session.add(rsvp)
    db.session.commit()
    return jsonify({"message": "RSVP successful"})

@app.route("/api/posts", methods=["POST"])
@login_required
def create_post():
    if current_user.role not in ["admin", "alumni"]:
        return jsonify({"error": "Only admins and alumni can create posts"}), 403

    content = request.form.get("content", "").strip()
    image = request.files.get("image")

    if not content:
        return jsonify({"error": "Content cannot be empty"}), 400

    image_filename = None

    if image and image.filename != "":
        if allowed_file(image.filename):
            filename = secure_filename(image.filename)
            unique_filename = f"post_{current_user.user_id}_{int(datetime.utcnow().timestamp())}_{filename}"
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
            image.save(image_path)
            image_filename = f"uploads/{unique_filename}"
        else:
            return jsonify({"error": "Invalid image format"}), 400

    post = Post(
        user_id=current_user.user_id,
        content=content,
        image=image_filename
    )

    db.session.add(post)
    db.session.commit()

    return jsonify({
        "message": "Post created successfully",
        "post_id": post.post_id
    }), 201


@app.route("/api/posts", methods=["GET"])
@login_required
def get_posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    results = []

    for p in posts:
        author = User.query.get(p.user_id)
        like_count = PostLike.query.filter_by(post_id=p.post_id).count()
        comment_count = PostComment.query.filter_by(post_id=p.post_id, is_deleted=False).count()
        liked_by_me = PostLike.query.filter_by(
            post_id=p.post_id,
            user_id=current_user.user_id
        ).first() is not None

        results.append({
            "post_id": p.post_id,
            "user_id": p.user_id,
            "name": author.name if author else "Deleted",
            "profile_image": author.profile_image if author else "default-profile.png",
            "content": p.content,
            "image": p.image,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M"),
            "like_count": like_count,
            "comment_count": comment_count,
            "liked_by_me": liked_by_me
        })

    return jsonify(results)


@app.route("/api/posts/<int:post_id>/like", methods=["POST"])
@login_required
def toggle_like(post_id):
    post = Post.query.get_or_404(post_id)

    like = PostLike.query.filter_by(
        post_id=post.post_id,
        user_id=current_user.user_id
    ).first()

    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({"action": "unliked"})
    else:
        new_like = PostLike(post_id=post.post_id, user_id=current_user.user_id)
        db.session.add(new_like)
        db.session.commit()
        return jsonify({"action": "liked"})


@app.route("/api/posts/<int:post_id>/comment", methods=["POST"])
@login_required
def add_comment(post_id):
    Post.query.get_or_404(post_id)

    data = request.get_json()
    content = data.get("content", "").strip()

    if not content:
        return jsonify({"error": "Comment cannot be empty"}), 400

    comment = PostComment(
        post_id=post_id,
        user_id=current_user.user_id,
        content=content
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({"message": "Comment added"})


@app.route("/api/posts/<int:post_id>/comments", methods=["GET"])
@login_required
def get_post_comments(post_id):
    Post.query.get_or_404(post_id)

    comments = PostComment.query.filter_by(
        post_id=post_id,
        is_deleted=False
    ).order_by(PostComment.created_at.asc()).all()

    results = []
    for c in comments:
        author = User.query.get(c.user_id)
        results.append({
            "comment_id": c.id,
            "user_id": c.user_id,
            "name": author.name if author else "Unknown",
            "profile_image": author.profile_image if author else "default-profile.png",
            "content": c.content,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M")
        })

    return jsonify(results)


# ────────────────────────────────────────────────
# CONNECTIONS
# ────────────────────────────────────────────────
@app.route("/api/connect/<int:receiver_id>", methods=["POST"])
@login_required
def connect_user(receiver_id):
    sender_id = current_user.user_id

    if sender_id == receiver_id:
        return jsonify({"message": "You cannot connect with yourself"}), 400

    existing = Connection.query.filter(
        ((Connection.sender_id == sender_id) & (Connection.receiver_id == receiver_id)) |
        ((Connection.sender_id == receiver_id) & (Connection.receiver_id == sender_id))
    ).first()

    if existing:
        return jsonify({"message": "Connection already exists or request already sent"}), 400

    connection = Connection(
        sender_id=sender_id,
        receiver_id=receiver_id,
        status="pending"
    )
    db.session.add(connection)
    db.session.commit()
    return jsonify({"message": "Connection request sent successfully"})


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
            "name": sender.name if sender else "Unknown"
        })
    return jsonify(result)


@app.route("/api/connection-requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(request_id):
    connection = Connection.query.get_or_404(request_id)

    if connection.receiver_id != current_user.user_id:
        return jsonify({"error": "Unauthorized"}), 403

    connection.status = "accepted"
    db.session.commit()
    return jsonify({"message": "Request accepted"})


@app.route("/api/connection-requests/<int:request_id>/decline", methods=["POST"])
@login_required
def decline_request(request_id):
    connection = Connection.query.get_or_404(request_id)

    if connection.receiver_id != current_user.user_id:
        return jsonify({"error": "Unauthorized"}), 403

    db.session.delete(connection)
    db.session.commit()
    return jsonify({"message": "Request declined"})


@app.route("/api/suggestions", methods=["GET"])
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


@app.route("/api/network-stats", methods=["GET"])
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

    suggestions = max(User.query.count() - 1, 0)

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

    users = db.session.query(User).outerjoin(StudentProfile).outerjoin(AlumniProfile)

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
        if graduation_year.isdigit():
            users = users.filter(StudentProfile.graduation_year == int(graduation_year))

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
        other_id = c.receiver_id if c.sender_id == user_id else c.sender_id
        other_user = User.query.get(other_id)

        if other_user:
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


if __name__ == "__main__":
    app.run(debug=True)