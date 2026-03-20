import os
from datetime import datetime

from flask import Flask, jsonify, request, render_template, redirect, flash, url_for
from flask_login import login_required, LoginManager, login_user, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func, case

from config import Config
from email_validator import validate_email, EmailNotValidError
from models import (
    db,
    User,
    StudentProfile,
    AlumniProfile,
    Connection,
    Message,
    MentorProfile,
    MentorApplication,
    MentorshipRequest,
    Event,
    RSVP,
    Post,
    PostLike,
    PostComment,
)


app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get("SECRET_KEY", "fallback_secret_key")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}

db.init_app(app)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def create_default_admin():
    admin_email = "admin@alumninexus.com"
    admin_password = "Admin@12345"

    existing_admin = User.query.filter_by(email=admin_email).first()

    if not existing_admin:
        admin_user = User(
            name="System Admin",
            email=admin_email,
            password=generate_password_hash(admin_password),
            role="admin",
            profile_image="default-profile.png"
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin created successfully.")
    else:
        print("Default admin already exists.")


with app.app_context():
    db.create_all()
    create_default_admin()


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


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

    return "pending_received"


def are_users_connected(user1_id, user2_id):
    """Users may message each other if they are accepted connections
    or if they have an accepted mentorship relationship."""
    connection = Connection.query.filter(
        (
            ((Connection.sender_id == user1_id) & (Connection.receiver_id == user2_id)) |
            ((Connection.sender_id == user2_id) & (Connection.receiver_id == user1_id))
        ) &
        (Connection.status == "accepted")
    ).first()
    if connection:
        return True

    mentorship = MentorshipRequest.query.filter(
        (
            ((MentorshipRequest.student_id == user1_id) & (MentorshipRequest.mentor_id == user2_id)) |
            ((MentorshipRequest.student_id == user2_id) & (MentorshipRequest.mentor_id == user1_id))
        ) &
        (MentorshipRequest.status == "accepted")
    ).first()
    if mentorship:
        return True

    return False


def get_conversation_context(user1_id, user2_id):
    """Return why two users can talk: connection or mentorship."""
    mentorship = MentorshipRequest.query.filter(
        (
            ((MentorshipRequest.student_id == user1_id) & (MentorshipRequest.mentor_id == user2_id)) |
            ((MentorshipRequest.student_id == user2_id) & (MentorshipRequest.mentor_id == user1_id))
        ) &
        (MentorshipRequest.status == "accepted")
    ).first()

    if mentorship:
        if mentorship.mentor_id == user1_id:
            return {"type": "mentorship", "role": "mentor"}
        return {"type": "mentorship", "role": "mentee"}

    return {"type": "connection", "role": None}


def get_mentorship_status(student_id, mentor_id):
    req = MentorshipRequest.query.filter_by(
        student_id=student_id,
        mentor_id=mentor_id
    ).first()

    if not req:
        return "none"

    return req.status


# ────────────────────────────────────────────────
# PAGES
# ────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/mynetwork")
@login_required
def mynetwork():
    return render_template("mynetwork.html")


@app.route("/pinboard")
@login_required
def pinboard():
    return render_template("pinboard.html")


@app.route("/events")
@login_required
def events_page():
    return render_template("events.html")


@app.route("/announcements")
@login_required
def announcements_page():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))
    return render_template("announcements.html")


@app.route("/admin/new-post")
@login_required
def admin_new_post():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))
    return redirect(url_for("announcements_page"))


@app.route("/admin/new-event")
@login_required
def admin_new_event():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))
    return redirect(url_for("events_page"))


# ────────────────────────────────────────────────
# AUTH
# ────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")
        image = request.files.get("profile_image")

        try:
            validate_email(email)
        except EmailNotValidError:
            flash("Invalid email address", "error")
            return redirect(url_for("register"))

        if not all([name, email, password, role]):
            flash("All fields are required", "error")
            return redirect(url_for("register"))

        if role == "mentor":
            flash(
                "Mentors must be approved by the admin first. Please register as a student or alumni.",
                "error"
            )
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        image_filename = "default-profile.png"

        if image and image.filename != "":
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                unique_filename = f"{email}_{filename}"
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
                image.save(image_path)
                image_filename = f"uploads/{unique_filename}"
            else:
                flash("Invalid image format. Please upload png, jpg, jpeg, or gif.", "error")
                return redirect(url_for("register"))

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            role=role,
            profile_image=image_filename
        )

        db.session.add(new_user)
        db.session.commit()

        if role == "student":
            faculty = request.form.get("faculty")
            department = request.form.get("department")
            graduation_year = request.form.get("graduation_year")
            industry = request.form.get("industry")

            if not all([faculty, department, graduation_year, industry]):
                flash("Please fill in all student profile fields.", "error")
                db.session.delete(new_user)
                db.session.commit()
                return redirect(url_for("register"))

            student_profile = StudentProfile(
                user_id=new_user.user_id,
                faculty=faculty,
                department=department,
                graduation_year=int(graduation_year),
                industry=industry
            )
            db.session.add(student_profile)
            db.session.commit()

        elif role == "alumni":
            headline = request.form.get("headline")
            experience = request.form.get("experience")
            career_interest = request.form.get("career_interest")
            level_of_study = request.form.get("level_of_study")
            education = request.form.get("education")
            certifications = request.form.get("certifications")
            skills = request.form.get("skills")

            if not all([headline, experience, career_interest, level_of_study]):
                flash("Please fill in all alumni profile fields.", "error")
                db.session.delete(new_user)
                db.session.commit()
                return redirect(url_for("register"))

            alumni_profile = AlumniProfile(
                user_id=new_user.user_id,
                headline=headline,
                experience=experience,
                career_interest=career_interest,
                level_of_study=level_of_study,
                education=education,
                certifications=certifications,
                skills=skills
            )
            db.session.add(alumni_profile)
            db.session.commit()

        flash("Registration successful.", "success")
        return redirect(url_for("profile", user_id=new_user.user_id))

    return render_template("registration.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not all([email, password]):
            flash("Missing email or password", "error")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f"{user.name}, you've successfully logged in", "success")

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("profile", user_id=user.user_id))

        flash("Invalid email or password", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out", "success")
    return redirect(url_for("login"))


# ────────────────────────────────────────────────
# PROFILE
# ────────────────────────────────────────────────
@app.route("/profile/<int:user_id>")
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    status = get_connection_status(user_id)

    mentorship_status = "none"
    if (
        user.role == "mentor"
        and current_user.user_id != user.user_id
        and current_user.role in ["student", "alumni"]
    ):
        mentorship_status = get_mentorship_status(current_user.user_id, user.user_id)

    return render_template(
        "profile.html",
        user=user,
        connection_status=status,
        mentorship_status=mentorship_status
    )


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
            path = os.path.join(app.config["UPLOAD_FOLDER"], unique)
            image.save(path)
            current_user.profile_image = f"uploads/{unique}"

        if current_user.role == "student" and current_user.student_profile:
            current_user.student_profile.faculty = request.form.get(
                "faculty", current_user.student_profile.faculty
            )
            current_user.student_profile.department = request.form.get(
                "department", current_user.student_profile.department
            )
            gy = request.form.get("graduation_year")
            if gy and gy.isdigit():
                current_user.student_profile.graduation_year = int(gy)
            current_user.student_profile.industry = request.form.get(
                "industry", current_user.student_profile.industry
            )

        elif current_user.role == "alumni" and current_user.alumni_profile:
            current_user.alumni_profile.headline = request.form.get(
                "headline", current_user.alumni_profile.headline
            )
            current_user.alumni_profile.experience = request.form.get(
                "experience", current_user.alumni_profile.experience
            )
            current_user.alumni_profile.career_interest = request.form.get(
                "career_interest", current_user.alumni_profile.career_interest
            )
            current_user.alumni_profile.level_of_study = request.form.get(
                "level_of_study", current_user.alumni_profile.level_of_study
            )
            current_user.alumni_profile.education = request.form.get("education")
            current_user.alumni_profile.skills = request.form.get("skills")
            current_user.alumni_profile.certifications = request.form.get("certifications")
            current_user.alumni_profile.linkedin_url = request.form.get("linkedin_url")

        elif current_user.role == "mentor" and current_user.mentor_profile:
            current_user.mentor_profile.expertise = request.form.get(
                "expertise", current_user.mentor_profile.expertise
            )

        db.session.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for("profile", user_id=current_user.user_id))

    return render_template("edit_profile.html", user=current_user)


# ────────────────────────────────────────────────
# MESSAGES
# ────────────────────────────────────────────────
@app.route("/messages/<int:user_id>")
@login_required
def message_page(user_id):
    other_user = User.query.get_or_404(user_id)

    if current_user.user_id == other_user.user_id:
        flash("You cannot message yourself.", "error")
        return redirect(url_for("profile", user_id=current_user.user_id))

    if not are_users_connected(current_user.user_id, other_user.user_id):
        flash("You can only message users you are connected with or your mentor/mentee.", "error")
        return redirect(url_for("profile", user_id=other_user.user_id))

    context = get_conversation_context(current_user.user_id, other_user.user_id)
    return render_template("message.html", other_user=other_user, conversation_context=context)


@app.route("/api/messages/<int:user_id>", methods=["GET"])
@login_required
def get_conversation(user_id):
    other_user = User.query.get_or_404(user_id)

    if current_user.user_id == other_user.user_id:
        return jsonify({"error": "You cannot message yourself"}), 400

    if not are_users_connected(current_user.user_id, other_user.user_id):
        return jsonify({"error": "You can only view conversations with connected users or your mentor/mentee"}), 403

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
        return jsonify({"error": "You can only message users you are connected with or your mentor/mentee"}), 403

    data = request.get_json(silent=True) or {}
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


# ────────────────────────────────────────────────
# MENTORSHIP
# ────────────────────────────────────────────────
@app.route("/mentorship")
@login_required
def mentorship():
    selected_expertise = request.args.get("expertise", "")

    mentor_query = (
        db.session.query(User, MentorProfile)
        .join(MentorProfile, MentorProfile.mentor_id == User.user_id)
        .filter(User.role == "mentor")
    )

    if selected_expertise:
        mentor_query = mentor_query.filter(MentorProfile.expertise == selected_expertise)

    mentors = []
    for user_obj, mp in mentor_query.all():
        user_obj.expertise = mp.expertise if mp else None
        mentors.append(user_obj)

    my_requests_raw = MentorshipRequest.query.filter_by(
        student_id=current_user.user_id
    ).order_by(MentorshipRequest.request_date.desc()).all()

    my_requests = []
    for req in my_requests_raw:
        mentor_user = User.query.get(req.mentor_id)
        req.mentor_name = mentor_user.name if mentor_user else "Unknown"
        my_requests.append(req)

    accepted_mentor = None
    accepted_req = MentorshipRequest.query.filter_by(
        student_id=current_user.user_id,
        status="accepted"
    ).first()
    if accepted_req:
        accepted_mentor = User.query.get(accepted_req.mentor_id)

    latest_application = None
    if current_user.role == "alumni":
        latest_application = (
            MentorApplication.query
            .filter_by(user_id=current_user.user_id)
            .order_by(MentorApplication.application_id.desc())
            .first()
        )

    pending_requests_count = 0
    accepted_requests_count = 0
    mentees_count = 0
    incoming_requests = []

    if current_user.role == "mentor":
        pending_requests_count = MentorshipRequest.query.filter_by(
            mentor_id=current_user.user_id,
            status="pending"
        ).count()

        accepted_requests_count = MentorshipRequest.query.filter_by(
            mentor_id=current_user.user_id,
            status="accepted"
        ).count()

        mentees_count = accepted_requests_count

        incoming_raw = (
            MentorshipRequest.query
            .filter_by(mentor_id=current_user.user_id)
            .order_by(MentorshipRequest.request_date.desc())
            .all()
        )

        for req in incoming_raw:
            student = User.query.get(req.student_id)
            req.student_name = student.name if student else "Unknown"
            req.student_user = student
            incoming_requests.append(req)

    return render_template(
        "mentorship.html",
        mentors=mentors,
        my_requests=my_requests,
        accepted_mentor=accepted_mentor,
        latest_application=latest_application,
        selected_expertise=selected_expertise,
        pending_requests_count=pending_requests_count,
        accepted_requests_count=accepted_requests_count,
        mentees_count=mentees_count,
        incoming_requests=incoming_requests
    )


@app.route("/apply-mentor", methods=["GET", "POST"])
@login_required
def apply_mentor():
    if current_user.role != "alumni":
        flash("Only alumni can apply to become a mentor.", "error")
        return redirect(url_for("mentorship"))

    if request.method == "POST":
        expertise = request.form.get("expertise", "").strip()
        motivation = request.form.get("motivation", "").strip()

        if not expertise:
            flash("Please select an area of expertise.", "error")
            return redirect(url_for("apply_mentor"))

        existing = MentorApplication.query.filter_by(
            user_id=current_user.user_id,
            status="pending"
        ).first()

        if existing:
            flash("You already have a pending application. Please wait for a decision.", "warning")
            return redirect(url_for("mentorship"))

        application = MentorApplication(
            user_id=current_user.user_id,
            expertise=expertise,
            motivation=motivation,
            status="pending"
        )
        db.session.add(application)
        db.session.commit()

        flash("Your mentor application has been submitted and is under review.", "success")
        return redirect(url_for("mentorship"))

    return render_template("apply_mentor.html")


@app.route("/request-mentorship/<int:mentor_id>", methods=["POST"])
@login_required
def request_mentorship(mentor_id):
    if current_user.role not in ["student", "alumni"]:
        flash("Only students and alumni can request mentorship.", "error")
        return redirect(url_for("mentorship"))

    mentor = User.query.get_or_404(mentor_id)

    if mentor.role != "mentor":
        flash("This user is not a mentor.", "error")
        return redirect(url_for("mentorship"))

    if mentor_id == current_user.user_id:
        flash("You cannot request mentorship from yourself.", "error")
        return redirect(url_for("mentorship"))

    existing = MentorshipRequest.query.filter_by(
        student_id=current_user.user_id,
        mentor_id=mentor_id
    ).first()

    if existing:
        flash("You have already sent a request to this mentor.", "warning")
        return redirect(url_for("mentorship"))

    req = MentorshipRequest(
        student_id=current_user.user_id,
        mentor_id=mentor_id,
        status="pending"
    )
    db.session.add(req)
    db.session.commit()

    flash(f"Mentorship request sent to {mentor.name}.", "success")
    return redirect(url_for("mentorship"))


@app.route("/mentorship/accept/<int:request_id>", methods=["POST"])
@login_required
def accept_mentorship_request(request_id):
    req = MentorshipRequest.query.get_or_404(request_id)

    if req.mentor_id != current_user.user_id:
        flash("Unauthorized.", "error")
        return redirect(url_for("mentorship"))

    req.status = "accepted"
    db.session.commit()

    flash("Mentorship request accepted.", "success")
    return redirect(url_for("mentorship"))


@app.route("/mentorship/reject/<int:request_id>", methods=["POST"])
@login_required
def reject_mentorship_request(request_id):
    req = MentorshipRequest.query.get_or_404(request_id)

    if req.mentor_id != current_user.user_id:
        flash("Unauthorized.", "error")
        return redirect(url_for("mentorship"))

    req.status = "rejected"
    db.session.commit()

    flash("Mentorship request rejected.", "info")
    return redirect(url_for("mentorship"))


# ────────────────────────────────────────────────
# EVENTS
# ────────────────────────────────────────────────
@app.route("/api/events", methods=["POST"])
@login_required
def create_event():
    if current_user.role != "admin":
        return jsonify({"error": "Only admin can create events"}), 403

    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    location = data.get("location", "").strip()
    raw_event_date = data.get("event_date", "").strip()

    if not title or not description or not location or not raw_event_date:
        return jsonify({"error": "All fields are required"}), 400

    try:
        event_date = datetime.fromisoformat(raw_event_date)
    except Exception:
        return jsonify({"error": "Invalid event date format"}), 400

    event = Event(
        title=title,
        description=description,
        location=location,
        event_date=event_date,
        created_by=current_user.user_id
    )

    db.session.add(event)
    db.session.commit()

    return jsonify({
        "message": "Event created successfully",
        "event_id": event.event_id
    }), 201


@app.route("/api/events", methods=["GET"])
@login_required
def get_events():
    events = Event.query.order_by(Event.event_date.desc()).all()
    results = []

    for e in events:
        user_status = None

        if current_user.role != "admin":
            my_rsvp = RSVP.query.filter_by(
                user_id=current_user.user_id,
                event_id=e.event_id
            ).first()
            user_status = my_rsvp.response if my_rsvp else None

        rsvp_count = RSVP.query.filter_by(event_id=e.event_id).count()
        attending_count = RSVP.query.filter_by(
            event_id=e.event_id,
            response="attending"
        ).count()

        results.append({
            "event_id": e.event_id,
            "title": e.title,
            "description": e.description,
            "location": e.location,
            "date": e.event_date.isoformat() if e.event_date else None,
            "user_status": user_status,
            "rsvp_count": rsvp_count,
            "attending_count": attending_count,
            "is_admin": current_user.role == "admin"
        })

    return jsonify(results)


@app.route("/api/events/<int:event_id>/rsvp", methods=["POST"])
@login_required
def rsvp_event(event_id):
    Event.query.get_or_404(event_id)

    existing_rsvp = RSVP.query.filter_by(
        user_id=current_user.user_id,
        event_id=event_id
    ).first()

    if existing_rsvp:
        return jsonify({
            "message": "You have already RSVP'd for this event",
            "user_status": existing_rsvp.response
        }), 400

    rsvp = RSVP(
        user_id=current_user.user_id,
        event_id=event_id,
        response="rsvp"
    )

    db.session.add(rsvp)
    db.session.commit()

    return jsonify({"message": "RSVP successful"}), 201


@app.route("/api/events/<int:event_id>/attend", methods=["POST"])
@login_required
def attend_event(event_id):
    Event.query.get_or_404(event_id)

    existing_rsvp = RSVP.query.filter_by(
        user_id=current_user.user_id,
        event_id=event_id
    ).first()

    if existing_rsvp:
        existing_rsvp.response = "attending"
    else:
        existing_rsvp = RSVP(
            user_id=current_user.user_id,
            event_id=event_id,
            response="attending"
        )
        db.session.add(existing_rsvp)

    db.session.commit()
    return jsonify({"message": "Marked as attending"})


@app.route("/api/events/<int:event_id>/cancel-rsvp", methods=["POST"])
@login_required
def cancel_rsvp(event_id):
    Event.query.get_or_404(event_id)

    existing_rsvp = RSVP.query.filter_by(
        user_id=current_user.user_id,
        event_id=event_id
    ).first()

    if existing_rsvp:
        db.session.delete(existing_rsvp)
        db.session.commit()
        return jsonify({"message": "RSVP cancelled"})

    return jsonify({"message": "No RSVP found to cancel"}), 404


# ────────────────────────────────────────────────
# PINBOARD POSTS
# ────────────────────────────────────────────────
@app.route("/api/posts", methods=["POST"])
@login_required
def create_post():
    if current_user.role not in ["alumni", "admin"]:
        return jsonify({"error": "Only alumni and admin can create posts"}), 403

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
        comment_count = PostComment.query.filter_by(post_id=p.post_id).count()
        liked_by_me = PostLike.query.filter_by(
            post_id=p.post_id,
            user_id=current_user.user_id
        ).first() is not None

        results.append({
            "post_id": p.post_id,
            "user_id": p.user_id,
            "name": author.name if author else "Deleted",
            "role": author.role if author else "",
            "profile_image": (
                author.profile_image
                if author and author.profile_image
                else "default-profile.png"
            ),
            "content": p.content,
            "image": p.image,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
            "like_count": like_count,
            "comment_count": comment_count,
            "liked_by_me": liked_by_me
        })

    return jsonify(results)


@app.route("/api/posts/<int:post_id>/like", methods=["POST"])
@login_required
def toggle_like(post_id):
    Post.query.get_or_404(post_id)

    like = PostLike.query.filter_by(
        post_id=post_id,
        user_id=current_user.user_id
    ).first()

    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({"action": "unliked"})

    new_like = PostLike(post_id=post_id, user_id=current_user.user_id)
    db.session.add(new_like)
    db.session.commit()
    return jsonify({"action": "liked"})


@app.route("/api/posts/<int:post_id>/comment", methods=["POST"])
@login_required
def add_comment(post_id):
    Post.query.get_or_404(post_id)

    data = request.get_json(silent=True) or {}
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

    return jsonify({"message": "Comment added"}), 201


@app.route("/api/posts/<int:post_id>/comments", methods=["GET"])
@login_required
def get_post_comments(post_id):
    Post.query.get_or_404(post_id)

    comments = PostComment.query.filter_by(
        post_id=post_id
    ).order_by(PostComment.created_at.asc()).all()

    results = []
    for c in comments:
        author = User.query.get(c.user_id)
        results.append({
            "comment_id": c.id,
            "user_id": c.user_id,
            "name": author.name if author else "Unknown",
            "profile_image": (
                author.profile_image
                if author and author.profile_image
                else "default-profile.png"
            ),
            "content": c.content,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
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
    return jsonify({"message": "Connection request sent successfully"}), 201


@app.route("/api/connection-requests", methods=["GET"])
@login_required
def get_connection_requests():
    user_id = current_user.user_id
    pending = Connection.query.filter_by(receiver_id=user_id, status="pending").all()

    result = []
    for req in pending:
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
            "industry": industry,
            "profile_image": u.profile_image or "default-profile.png"
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

    if graduation_year and graduation_year.isdigit():
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
            "graduation_year": year_val,
            "profile_image": user.profile_image or "default-profile.png"
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


# ────────────────────────────────────────────────
# ADMIN — DASHBOARD & VIEWS
# ────────────────────────────────────────────────
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    total_students = User.query.filter_by(role="student").count()
    total_alumni = User.query.filter_by(role="alumni").count()
    total_mentors = User.query.filter_by(role="mentor").count()
    total_events = Event.query.count()
    total_rsvps = RSVP.query.count()
    total_event_attendees = RSVP.query.filter_by(response="attending").count()

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_alumni=total_alumni,
        total_mentors=total_mentors,
        total_events=total_events,
        total_rsvps=total_rsvps,
        total_event_attendees=total_event_attendees
    )


@app.route("/admin/alumni")
@login_required
def admin_alumni():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    alumni_users = User.query.filter_by(role="alumni").all()
    return render_template("admin_alumni.html", alumni_users=alumni_users)


@app.route("/admin/students")
@login_required
def admin_students():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    student_users = User.query.filter_by(role="student").all()
    return render_template("admin_students.html", student_users=student_users)


@app.route("/admin/events")
@login_required
def admin_events():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    events = Event.query.order_by(Event.event_date.desc()).all()
    return render_template("admin_events.html", events=events)


# ────────────────────────────────────────────────
# ADMIN — MENTOR MANAGEMENT
# ────────────────────────────────────────────────
@app.route("/admin/mentors")
@login_required
def admin_mentors():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    mentor_users = User.query.filter_by(role="mentor").all()

    applications = (
        db.session.query(MentorApplication, User)
        .join(User, MentorApplication.user_id == User.user_id)
        .order_by(MentorApplication.application_id.desc())
        .all()
    )

    return render_template(
        "admin_mentors.html",
        mentor_users=mentor_users,
        applications=applications
    )


@app.route("/admin/mentors/approve/<int:application_id>", methods=["POST"])
@login_required
def approve_mentor_application(application_id):
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    application = MentorApplication.query.get_or_404(application_id)
    user = User.query.get_or_404(application.user_id)

    application.status = "approved"
    user.role = "mentor"

    if not user.mentor_profile:
        mentor_profile = MentorProfile(
            mentor_id=user.user_id,
            expertise=application.expertise
        )
        db.session.add(mentor_profile)

    db.session.commit()

    flash(f"{user.name} has been approved as a mentor.", "success")
    return redirect(url_for("admin_mentors"))


@app.route("/admin/mentors/reject/<int:application_id>", methods=["POST"])
@login_required
def reject_mentor_application(application_id):
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    application = MentorApplication.query.get_or_404(application_id)
    user = User.query.get_or_404(application.user_id)

    application.status = "rejected"
    db.session.commit()

    flash(f"{user.name}'s mentor application has been rejected.", "info")
    return redirect(url_for("admin_mentors"))


@app.route("/admin/mentors/remove/<int:user_id>", methods=["POST"])
@login_required
def remove_mentor(user_id):
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    user = User.query.get_or_404(user_id)
    user.role = "alumni"

    if user.mentor_profile:
        db.session.delete(user.mentor_profile)

    db.session.commit()

    flash(f"{user.name} has been removed as a mentor.", "success")
    return redirect(url_for("admin_mentors"))


# ────────────────────────────────────────────────
# ADMIN — EVENT ATTENDEES & RSVPs
# ────────────────────────────────────────────────
@app.route("/admin/event-attendees")
@login_required
def admin_event_attendees():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    attendees = db.session.query(RSVP, User, Event).join(
        User, RSVP.user_id == User.user_id
    ).join(
        Event, RSVP.event_id == Event.event_id
    ).filter(
        RSVP.response == "attending"
    ).all()

    return render_template("admin_event_attendees.html", attendees=attendees)


@app.route("/admin/rsvps")
@login_required
def admin_rsvps():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    rsvps = db.session.query(RSVP, User, Event).join(
        User, RSVP.user_id == User.user_id
    ).join(
        Event, RSVP.event_id == Event.event_id
    ).all()

    return render_template("admin_rsvps.html", rsvps=rsvps)


# ────────────────────────────────────────────────
# ADMIN — EVENT ANALYTICS
# ────────────────────────────────────────────────
@app.route("/admin/event-analytics")
@login_required
def admin_event_analytics():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    now = datetime.utcnow()

    total_events = Event.query.count()
    upcoming_events = Event.query.filter(Event.event_date >= now).count()
    past_events = Event.query.filter(Event.event_date < now).count()
    total_rsvps = RSVP.query.count()
    total_attendees = RSVP.query.filter_by(response="attending").count()

    event_stats = (
        db.session.query(
            Event.event_id,
            Event.title,
            Event.event_date,
            Event.location,
            func.count(RSVP.rsvp_id).label("rsvp_count"),
            func.sum(
                case(
                    (RSVP.response == "attending", 1),
                    else_=0
                )
            ).label("attending_count")
        )
        .outerjoin(RSVP, Event.event_id == RSVP.event_id)
        .group_by(Event.event_id, Event.title, Event.event_date, Event.location)
        .order_by(Event.event_date.desc())
        .all()
    )

    formatted_event_stats = []
    for event in event_stats:
        formatted_event_stats.append({
            "event_id": event.event_id,
            "title": event.title,
            "event_date": event.event_date,
            "location": event.location,
            "rsvp_count": event.rsvp_count or 0,
            "attending_count": event.attending_count or 0
        })

    most_popular_event = None
    if formatted_event_stats:
        most_popular_event = max(formatted_event_stats, key=lambda e: e["rsvp_count"])

    monthly_events_raw = (
        db.session.query(
            func.strftime("%Y-%m", Event.event_date).label("month"),
            func.count(Event.event_id).label("count")
        )
        .filter(Event.event_date.isnot(None))
        .group_by("month")
        .order_by("month")
        .all()
    )

    monthly_labels = [row.month for row in monthly_events_raw]
    monthly_counts = [row.count for row in monthly_events_raw]

    event_titles = [event["title"] for event in formatted_event_stats]
    rsvp_counts = [event["rsvp_count"] for event in formatted_event_stats]
    attending_counts = [event["attending_count"] for event in formatted_event_stats]

    attendance_rates = []
    for event in formatted_event_stats:
        if event["rsvp_count"] > 0:
            rate = round((event["attending_count"] / event["rsvp_count"]) * 100, 1)
        else:
            rate = 0
        attendance_rates.append(rate)

    status_labels = ["Upcoming", "Past"]
    status_counts = [upcoming_events, past_events]

    return render_template(
        "event_analytics.html",
        total_events=total_events,
        upcoming_events=upcoming_events,
        past_events=past_events,
        total_rsvps=total_rsvps,
        total_attendees=total_attendees,
        most_popular_event=most_popular_event,
        event_stats=formatted_event_stats,
        monthly_labels=monthly_labels,
        monthly_counts=monthly_counts,
        event_titles=event_titles,
        rsvp_counts=rsvp_counts,
        attending_counts=attending_counts,
        attendance_rates=attendance_rates,
        status_labels=status_labels,
        status_counts=status_counts,
        now=now
    )


if __name__ == "__main__":
    app.run(debug=True)