import os
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, jsonify, request, render_template, redirect, flash, url_for
from flask_login import login_required, LoginManager, login_user, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func, case
from sqlalchemy.orm import aliased
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from email_validator import validate_email, EmailNotValidError

from config import Config
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
    MentorChannelPost,
    MentorChannelFile,
)

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get("SECRET_KEY", "fallback_secret_key")
app.config['SECURITY_PASSWORD_SALT'] = 'alumni-nexus-password-salt-2024'

# Email Configuration - FIXED (removed spaces from password)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'minenhlebhekane@gmail.com'
app.config['MAIL_PASSWORD'] = 'qgiqafzvdoconjul'  # FIXED: Removed spaces
app.config['MAIL_DEFAULT_SENDER'] = 'minenhlebhekane@gmail.com'

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}

ALLOWED_CHANNEL_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}

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

    try:
        inspector = db.inspect(db.engine)
        alumni_columns = [col["name"] for col in inspector.get_columns("alumni_profiles")]
        if "industry" not in alumni_columns:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE alumni_profiles ADD COLUMN industry VARCHAR(150)"))
                conn.commit()
            print("Added missing 'industry' column to alumni_profiles.")
    except Exception as e:
        print(f"Industry column check skipped: {e}")

    try:
        inspector = db.inspect(db.engine)
        message_columns = [col["name"] for col in inspector.get_columns("messages")]
        if "is_read" not in message_columns:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE messages ADD COLUMN is_read BOOLEAN DEFAULT 0"))
                conn.commit()
            print("Added missing 'is_read' column to messages.")
    except Exception as e:
        print(f"is_read column check skipped: {e}")

    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("UPDATE messages SET is_read = 0 WHERE is_read IS NULL"))
            conn.commit()
        print("Updated NULL message is_read values to 0.")
    except Exception as e:
        print(f"NULL is_read update skipped: {e}")

    create_default_admin()


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


def allowed_channel_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_CHANNEL_EXTENSIONS


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def validate_password_strength(password):
    """Validate password strength with specific requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    
    if not re.search(r"[!@#$%^&*]", password):
        return False, "Password must contain at least one special character (!@#$%^&*)"
    
    return True, "Password is strong"


def send_reset_email(recipient_email, reset_url):
    """Send password reset email"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Password Reset Request - Alumni Nexus'
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = recipient_email
        
        # HTML email body
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #042C53 0%, #0C447C 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">Alumni Nexus</h1>
                    <p style="color: #85B7EB; margin: 10px 0 0;">Password Reset Request</p>
                </div>
                
                <div style="background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
                    <h2 style="color: #042C53; margin-top: 0;">Hello,</h2>
                    <p>We received a request to reset your password for your Alumni Nexus account.</p>
                    <p>Click the button below to create a new password:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" style="display: inline-block; padding: 12px 30px; background-color: #378ADD; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Reset Password</a>
                    </div>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; word-break: break-all; font-size: 12px; color: #378ADD;">
                        {reset_url}
                    </p>
                    
                    <p><strong>Important:</strong> This link will expire in <strong>1 hour</strong> for security reasons.</p>
                    
                    <p>If you didn't request this password reset, please ignore this email. Your password will remain unchanged.</p>
                    
                    <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
                    <p style="color: #777; font-size: 12px; text-align: center;">
                        This is an automated message from Alumni Nexus. Please do not reply to this email.<br>
                        &copy; 2024 Alumni Nexus. All rights reserved.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text = f"""
        Alumni Nexus Password Reset
        
        Hello,
        
        We received a request to reset your password for your Alumni Nexus account.
        
        Click the link below to create a new password:
        
        {reset_url}
        
        Important: This link will expire in 1 hour for security reasons.
        
        If you didn't request this password reset, please ignore this email. Your password will remain unchanged.
        
        This is an automated message from Alumni Nexus. Please do not reply to this email.
        """
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        
        print(f"Password reset email sent to: {recipient_email}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


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


def get_user_industry(user):
    if user.role == "student" and user.student_profile and user.student_profile.industry:
        return user.student_profile.industry.strip()

    if user.role == "alumni" and user.alumni_profile and user.alumni_profile.industry:
        return user.alumni_profile.industry.strip()

    return None


def get_display_industry(user):
    industry = get_user_industry(user)
    return industry if industry else "Unknown"


def get_excluded_user_ids_for_network(user_id):
    excluded_ids = {user_id}

    existing_connections = Connection.query.filter(
        (Connection.sender_id == user_id) | (Connection.receiver_id == user_id)
    ).all()

    for conn in existing_connections:
        excluded_ids.add(conn.sender_id)
        excluded_ids.add(conn.receiver_id)

    return excluded_ids


def get_unread_message_count(user_id):
    try:
        return Message.query.filter(
            Message.receiver_id == user_id,
            or_(Message.is_read == False, Message.is_read.is_(None))
        ).count()
    except Exception as e:
        print(f"Unread count error: {e}")
        return 0


def _get_mentor_of_student(student_id):
    req = MentorshipRequest.query.filter_by(
        student_id=student_id, status="accepted"
    ).first()
    if req:
        return User.query.get(req.mentor_id)
    return None


@app.context_processor
def inject_global_template_data():
    unread_message_count = 0

    if current_user.is_authenticated:
        unread_message_count = get_unread_message_count(current_user.user_id)

    return {
        "unread_message_count": unread_message_count
    }


# ==================== ROUTES ====================

@app.route("/")
def home():
    return render_template("home.html")


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

        is_valid_password, password_message = validate_password_strength(password)
        if not is_valid_password:
            flash(password_message, "error")
            return redirect(url_for("register"))

        if role == "mentor":
            flash("Mentors must be approved by the admin first. Please register as a student or alumni.", "error")
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
            industry = request.form.get("student_industry")

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
            level_of_study = request.form.get("level_of_study")
            education = request.form.get("education")
            certifications = request.form.get("certifications")
            skills = request.form.get("skills")
            industry = request.form.get("alumni_industry")

            if not all([headline, experience, industry, level_of_study]):
                flash("Please fill in all alumni profile fields.", "error")
                db.session.delete(new_user)
                db.session.commit()
                return redirect(url_for("register"))

            alumni_profile = AlumniProfile(
                user_id=new_user.user_id,
                headline=headline,
                experience=experience,
                industry=industry,
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


@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    
    if not email:
        flash('Please enter your email address.', 'error')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=email).first()
    
    if user:
        token = serializer.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])
        reset_url = url_for('reset_password', token=token, _external=True)
        
        email_sent = send_reset_email(email, reset_url)
        
        if email_sent:
            flash('Password reset instructions have been sent to your email. Please check your inbox (and spam folder).', 'success')
        else:
            flash('Unable to send email at this time. Please try again later.', 'error')
    else:
        flash('If an account exists with that email, you will receive password reset instructions.', 'info')
    
    return redirect(url_for('login'))


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt=app.config['SECURITY_PASSWORD_SALT'], max_age=3600)
    except SignatureExpired:
        flash('The password reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('login'))
    except BadSignature:
        flash('Invalid password reset link.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or not confirm_password:
            flash('Please fill in all fields.', 'error')
            return render_template('reset_password.html', token=token)
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', token=token)
        
        is_valid, msg = validate_password_strength(new_password)
        if not is_valid:
            flash(msg, 'error')
            return render_template('reset_password.html', token=token)
        
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash('Your password has been updated successfully. Please login with your new password.', 'success')
            return redirect(url_for('login'))
        else:
            flash('An error occurred while updating your password. Please try again.', 'error')
            return render_template('reset_password.html', token=token)
    
    return render_template('reset_password.html', token=token)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out", "success")
    return redirect(url_for("login"))


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
            current_user.alumni_profile.industry = request.form.get(
                "industry", current_user.alumni_profile.industry
            )
            current_user.alumni_profile.level_of_study = request.form.get(
                "level_of_study", current_user.alumni_profile.level_of_study
            )
            current_user.alumni_profile.education = request.form.get(
                "education", current_user.alumni_profile.education
            )
            current_user.alumni_profile.skills = request.form.get(
                "skills", current_user.alumni_profile.skills
            )
            current_user.alumni_profile.certifications = request.form.get(
                "certifications", current_user.alumni_profile.certifications
            )
            current_user.alumni_profile.linkedin_url = request.form.get(
                "linkedin_url", current_user.alumni_profile.linkedin_url
            )

        elif current_user.role == "mentor" and current_user.mentor_profile:
            current_user.mentor_profile.expertise = request.form.get(
                "expertise", current_user.mentor_profile.expertise
            )

        db.session.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for("profile", user_id=current_user.user_id))

    return render_template("edit_profile.html", user=current_user)


# ==================== ADDITIONAL ROUTES ====================

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


# ==================== API ROUTES ====================

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
                author.profile_image if author and author.profile_image else "default-profile.png"
            ),
            "content": p.content,
            "image": p.image,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
            "like_count": like_count,
            "comment_count": comment_count,
            "liked_by_me": liked_by_me
        })

    return jsonify(results)


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


# ==================== ADMIN ROUTES ====================

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    total_students = db.session.query(User.user_id).outerjoin(
        StudentProfile, StudentProfile.user_id == User.user_id
    ).filter(
        (func.lower(User.role) == "student") | (StudentProfile.id.isnot(None))
    ).distinct().count()

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

    student_users = User.query.filter(
        func.lower(User.role) == "student"
    ).all()

    return render_template("admin_students.html", student_users=student_users)


@app.route("/admin/mentor-applications")
@login_required
def admin_mentor_applications():
    if current_user.role != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("home"))

    applications = (
        db.session.query(MentorApplication, User)
        .join(User, MentorApplication.user_id == User.user_id)
        .order_by(MentorApplication.application_id.desc())
        .all()
    )

    return render_template(
        "admin_mentor_applications.html",
        applications=applications
    )


@app.route("/admin/mentor-applications/approve/<int:application_id>", methods=["POST"])
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
    else:
        user.mentor_profile.expertise = application.expertise

    db.session.commit()

    flash(f"{user.name} has been approved as a mentor.", "success")
    return redirect(url_for("admin_mentor_applications"))


if __name__ == "__main__":
    app.run(debug=True)