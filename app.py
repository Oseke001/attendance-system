from flask import Flask, render_template, request, redirect, url_for, session, Response

from models import db, User, Class, ClassMembership, AttendanceSession, AttendanceRecord, Announcement

from werkzeug.security import generate_password_hash, check_password_hash

import secrets
import string
import math
import io
import csv
from datetime import datetime


import os
basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, "instance"), exist_ok=True)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "project-002-secret-key")
database_url = os.environ.get("DATABASE_URL")

if database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url.replace(
        "postgres://", "postgresql://", 1
    )
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        basedir, "instance", "attendance.db"
    )


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two GPS points in meters using Haversine formula."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def class_not_found_response():
    return render_template("class_not_found.html")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    error = None

    if request.method == "POST":

        name = request.form["name"].strip()
        matric_number = request.form["matric_number"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        existing_matric = User.query.filter_by(
            matric_number=matric_number
        ).first()

        if existing_matric:
            error = "Matric / Staff number is already registered. Please login instead."
            return render_template("register.html", error=error)

        existing_email = User.query.filter_by(
            email=email
        ).first()

        if existing_email:
            error = "Email address is already registered. Please login instead."
            return render_template("register.html", error=error)

        hashed_password = generate_password_hash(password)

        new_user = User(
            name=name,
            matric_number=matric_number,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(user.password, password):

            session["user_id"] = user.id

            return redirect(url_for("dashboard"))

        return "Invalid email or password."

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    owned_classes = Class.query.filter_by(
        owner_id=user.id
    ).all()

    memberships = ClassMembership.query.filter(
        ClassMembership.user_id == user.id,
        ClassMembership.role != "owner"
    ).all()

    return render_template(
        "dashboard.html",
        user=user,
        owned_classes=owned_classes,
        memberships=memberships
    )


@app.route("/create-class", methods=["GET", "POST"])
def create_class():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form["name"].strip()

        characters = string.ascii_uppercase + string.digits

        while True:

            class_code = "".join(
                secrets.choice(characters)
                for _ in range(8)
            )

            existing_class = Class.query.filter_by(
                class_code=class_code
            ).first()

            if not existing_class:
                break

        new_class = Class(
            name=name,
            class_code=class_code,
            owner_id=session["user_id"]
        )

        db.session.add(new_class)

        # Get the new class ID
        db.session.flush()

        # Make the creator the owner
        owner_membership = ClassMembership(
            user_id=session["user_id"],
            class_id=new_class.id,
            role="owner"
        )

        db.session.add(owner_membership)

        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("create_class.html")


@app.route("/join-class", methods=["GET", "POST"])
def join_class():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        class_code = request.form["class_code"].strip().upper()

        class_to_join = Class.query.filter_by(
            class_code=class_code
        ).first()

        if not class_to_join:
            return "Class not found."

        existing_membership = ClassMembership.query.filter_by(
            user_id=session["user_id"],
            class_id=class_to_join.id
        ).first()

        if existing_membership:
            return "You are already a member of this class."

        membership = ClassMembership(
            user_id=session["user_id"],
            class_id=class_to_join.id,
            role="member"
        )

        db.session.add(membership)

        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("join_class.html")


@app.route("/class/<int:class_id>")
def class_page(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    membership = ClassMembership.query.filter_by(
        user_id=user.id,
        class_id=class_id
    ).first()

    if not membership:
        return "Access denied."

    members = ClassMembership.query.filter_by(
        class_id=class_obj.id
    ).all()

    announcements = Announcement.query.filter_by(
        class_id=class_obj.id
    ).order_by(
        Announcement.timestamp.desc()
    ).all()

    latest_session = AttendanceSession.query.filter_by(
        class_id=class_id
    ).order_by(AttendanceSession.id.desc()).first()

    attendance_live = False
    attendance_ended = False

    if latest_session:
        if latest_session.active and datetime.now() <= latest_session.end_time:
            attendance_live = True
        else:
            if latest_session.active:
                latest_session.active = False
                db.session.commit()
            attendance_ended = True

    return render_template(
        "class_page.html",
        user=user,
        class_obj=class_obj,
        membership=membership,
        members=members,
        announcements=announcements,
        latest_session=latest_session,
        attendance_live=attendance_live,
        attendance_ended=attendance_ended
    )


@app.route("/class/<int:class_id>/make-admin/<int:user_id>", methods=["POST"])
def make_admin(class_id, user_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    if class_obj.owner_id != session["user_id"]:
        return "Access denied."

    membership = ClassMembership.query.filter_by(
        user_id=user_id,
        class_id=class_id
    ).first()

    if not membership:
        return "User is not a member of this class."

    if membership.role == "owner":
        return "The owner cannot be changed."

    membership.role = "admin"
    db.session.commit()

    return redirect(url_for("class_page", class_id=class_id))


@app.route("/class/<int:class_id>/demote-admin/<int:user_id>", methods=["POST"])
def demote_admin(class_id, user_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    if class_obj.owner_id != session["user_id"]:
        return "Access denied."

    membership = ClassMembership.query.filter_by(
        user_id=user_id,
        class_id=class_id
    ).first()

    if not membership:
        return "User is not a member of this class."

    if membership.role == "owner":
        return "The owner cannot be demoted."

    membership.role = "member"
    db.session.commit()

    return redirect(url_for("class_page", class_id=class_id))


@app.route("/class/<int:class_id>/post-announcement", methods=["GET", "POST"])
def post_announcement(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    membership = ClassMembership.query.filter_by(
        user_id=user.id,
        class_id=class_id
    ).first()

    if not membership or membership.role != "owner":
        return "Access denied."

    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"].strip()

        announcement = Announcement(
            class_id=class_id,
            author_id=user.id,
            title=title,
            content=content,
            timestamp=datetime.now()
        )

        db.session.add(announcement)
        db.session.commit()

        return redirect(url_for("class_page", class_id=class_id))

    return render_template(
        "post_announcement.html",
        user=user,
        class_obj=class_obj
    )


@app.route("/class/<int:class_id>/delete", methods=["POST"])
def delete_class(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    if class_obj.owner_id != session["user_id"]:
        return "Access denied."

    # Delete all records associated with this class
    AttendanceRecord.query.filter_by(class_id=class_id).delete()
    AttendanceSession.query.filter_by(class_id=class_id).delete()
    ClassMembership.query.filter_by(class_id=class_id).delete()
    Announcement.query.filter_by(class_id=class_id).delete()
    db.session.delete(class_obj)

    db.session.commit()

    return redirect(url_for("dashboard"))

@app.route(
    "/class/<int:class_id>/start-attendance",
    methods=["GET", "POST"]
)
def start_attendance(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    membership = ClassMembership.query.filter_by(
        user_id=user.id,
        class_id=class_id
    ).first()

    # Attendance sessions are started by the Owner.
    if not membership or membership.role != "owner":
        return "Access denied."

    if request.method == "POST":
        try:
            duration_hours = int(request.form.get("duration_hours", 1))
            duration_minutes = int(request.form.get("duration_minutes", 30))
        except (TypeError, ValueError):
            return render_template("start_attendance.html", user=user, class_obj=class_obj,
                                   error="Please enter a valid attendance duration.")

        if duration_hours < 0 or duration_minutes < 0 or duration_minutes > 59:
            return render_template("start_attendance.html", user=user, class_obj=class_obj,
                                   error="Please enter a valid attendance duration.")

        total_minutes = (duration_hours * 60) + duration_minutes
        if total_minutes <= 0:
            return render_template("start_attendance.html", user=user, class_obj=class_obj,
                                   error="Attendance duration must be greater than zero.")

        use_location = request.form.get("use_location") == "on"
        latitude = longitude = radius_meters = None

        if use_location:
            try:
                latitude = float(request.form.get("latitude", ""))
                longitude = float(request.form.get("longitude", ""))
                radius_meters = float(request.form.get("radius_meters", 50.0))
            except (TypeError, ValueError):
                return render_template("start_attendance.html", user=user, class_obj=class_obj,
                                       error="Please provide a valid classroom location and radius.")

            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180) or radius_meters <= 0:
                return render_template("start_attendance.html", user=user, class_obj=class_obj,
                                       error="Please provide a valid classroom location and radius.")

            # Save this as the class's default location for future sessions.
            class_obj.latitude = latitude
            class_obj.longitude = longitude
            class_obj.radius_meters = radius_meters

        characters = string.ascii_uppercase + string.digits
        code = "".join(secrets.choice(characters) for _ in range(6))

        start_time = datetime.now()
        from datetime import timedelta
        end_time = start_time + timedelta(minutes=total_minutes)

        # Only one attendance session can be live for a class at a time.
        previous_sessions = AttendanceSession.query.filter_by(
            class_id=class_id, active=True
        ).all()
        for previous in previous_sessions:
            previous.active = False

        attendance = AttendanceSession(
            class_id=class_id,
            code=code,
            start_time=start_time,
            end_time=end_time,
            active=True,
            location_enabled=use_location,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters
        )

        db.session.add(attendance)
        db.session.commit()

        return render_template(
            "attendance_started.html",
            user=user,
            class_obj=class_obj,
            attendance=attendance,
            end_time_iso=end_time.isoformat()
        )

    return render_template(
        "start_attendance.html",
        user=user,
        class_obj=class_obj,
        error=None
    )


@app.route(
    "/class/<int:class_id>/attendance",
    methods=["GET", "POST"]
)
def take_attendance(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    membership = ClassMembership.query.filter_by(
        user_id=user.id, class_id=class_id
    ).first()

    if not membership:
        return "Access denied."

    active_session = AttendanceSession.query.filter_by(
        class_id=class_id, active=True
    ).order_by(AttendanceSession.id.desc()).first()

    if active_session and datetime.now() > active_session.end_time:
        active_session.active = False
        db.session.commit()
        active_session = None

    error = None
    success = None

    if request.method == "POST":
        entered_code = request.form.get("code", "").strip().upper()
        student_lat_raw = request.form.get("latitude")
        student_lng_raw = request.form.get("longitude")

        active_session = AttendanceSession.query.filter_by(
            class_id=class_id, active=True
        ).order_by(AttendanceSession.id.desc()).first()

        if not active_session:
            return render_template(
                "take_attendance.html",
                user=user, class_obj=class_obj,
                error="No active attendance session.",
                location_required=False
            )

        if datetime.now() > active_session.end_time:
            active_session.active = False
            db.session.commit()
            return render_template(
                "take_attendance.html",
                user=user, class_obj=class_obj,
                error="Attendance session has expired.",
                location_required=False
            )

        if entered_code != active_session.code:
            return render_template(
                "take_attendance.html",
                user=user, class_obj=class_obj,
                error="Invalid attendance code.",
                location_required=active_session.location_enabled
            )

        existing_record = AttendanceRecord.query.filter_by(
            session_id=active_session.id, user_id=user.id
        ).first()

        if existing_record:
            if "Present" in existing_record.status:
                success = f"You have already submitted attendance for this session. (Status: {existing_record.status})"
            else:
                error = f"You already submitted attendance for this session. (Status: {existing_record.status})"

            return render_template(
                "take_attendance.html",
                user=user, class_obj=class_obj,
                error=error, success=success,
                location_required=active_session.location_enabled
            )

        student_lat = float(student_lat_raw) if student_lat_raw else None
        student_lng = float(student_lng_raw) if student_lng_raw else None

        if active_session.location_enabled:
            if student_lat is not None and student_lng is not None:
                dist = calculate_distance(
                    student_lat, student_lng,
                    active_session.latitude, active_session.longitude
                )
                allowed_radius = active_session.radius_meters or 50.0

                if dist <= allowed_radius:
                    status = "Present"
                    success = f"✅ Attendance Approved! You are {dist:.1f} meters away from classroom."
                else:
                    status = f"Denied - Out of Radius ({dist:.1f}m)"
                    error = f"❌ Access Denied! You are {dist:.1f} meters away from classroom (Allowed radius: {allowed_radius}m)."
            else:
                dist = None
                status = "Denied - Location Required"
                error = "❌ Access Denied! Location access is required for this attendance session."
        else:
            dist = None
            status = "Present (Location Not Required)"
            success = "✅ Attendance Approved! Location verification was not required for this session."

        record = AttendanceRecord(
            class_id=class_id,
            session_id=active_session.id,
            user_id=user.id,
            timestamp=datetime.now(),
            status=status,
            student_lat=student_lat,
            student_lng=student_lng,
            distance_meters=dist
        )

        db.session.add(record)
        db.session.commit()

        return render_template(
            "take_attendance.html",
            user=user, class_obj=class_obj,
            error=error, success=success,
            location_required=active_session.location_enabled
        )

    return render_template(
        "take_attendance.html",
        user=user, class_obj=class_obj,
        error=error, success=success,
        location_required=active_session.location_enabled if active_session else False
    )


@app.route("/class/<int:class_id>/attendance-history")
def attendance_history(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    membership = ClassMembership.query.filter_by(
        user_id=user.id, class_id=class_id
    ).first()

    if not membership:
        return "Access denied."

    # Owner can view the complete class history.
    # Members can view only their own history.
    # Admins are deliberately blocked from past history.
    if membership.role == "owner":
        total_sessions = AttendanceSession.query.filter_by(class_id=class_id).count()

        records = AttendanceRecord.query.filter_by(
            class_id=class_id
        ).order_by(AttendanceRecord.timestamp.desc()).all()

        members = ClassMembership.query.filter_by(class_id=class_id).all()

        student_analytics = []
        for m in members:
            attended_count = AttendanceRecord.query.filter(
                AttendanceRecord.class_id == class_id,
                AttendanceRecord.user_id == m.user_id,
                AttendanceRecord.status.like("%Present%")
            ).count()

            rate = (attended_count / total_sessions * 100.0) if total_sessions > 0 else 100.0
            student_analytics.append({
                "user": m.user,
                "role": m.role,
                "attended": attended_count,
                "total": total_sessions,
                "rate": round(rate, 1),
                "is_low": rate < 75.0 and total_sessions > 0
            })

    elif membership.role == "member":
        records = AttendanceRecord.query.filter_by(
            class_id=class_id,
            user_id=user.id
        ).order_by(AttendanceRecord.timestamp.desc()).all()

        members = []
        total_sessions = AttendanceSession.query.filter_by(class_id=class_id).count()
        student_analytics = []

    else:
        return "Access denied."

    return render_template(
        "attendance_history.html",
        user=user,
        class_obj=class_obj,
        membership=membership,
        records=records,
        members=members,
        total_sessions=total_sessions,
        student_analytics=student_analytics
    )


@app.route("/class/<int:class_id>/export-csv")
def export_csv(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    membership = ClassMembership.query.filter_by(
        user_id=user.id,
        class_id=class_id
    ).first()

    if not membership or membership.role != "owner":
        return "Access denied."

    records = AttendanceRecord.query.filter_by(
        class_id=class_id
    ).order_by(
        AttendanceRecord.timestamp.desc()
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV Header
    writer.writerow([
        "Student Name",
        "Matric Number",
        "Email",
        "Session ID",
        "Date & Time",
        "Status",
        "Distance (Meters)",
        "Latitude",
        "Longitude"
    ])

    # Write CSV Data Rows
    for r in records:
        writer.writerow([
            r.user.name,
            r.user.matric_number,
            r.user.email,
            r.session_id,
            r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            r.status,
            f"{r.distance_meters:.1f}" if r.distance_meters is not None else "N/A",
            r.student_lat or "N/A",
            r.student_lng or "N/A"
        ])

    csv_data = output.getvalue()
    filename = f"{class_obj.name.replace(' ', '_')}_Attendance_Report.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


@app.route("/class/<int:class_id>/manual-attendance", methods=["GET", "POST"])
def manual_attendance(class_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    class_obj = Class.query.get(class_id)

    if class_obj is None:
        return class_not_found_response()

    membership = ClassMembership.query.filter_by(
        user_id=user.id, class_id=class_id
    ).first()

    if not membership or membership.role not in ["owner", "admin"]:
        return "Access denied."

    active_session = AttendanceSession.query.filter_by(
        class_id=class_id, active=True
    ).order_by(AttendanceSession.id.desc()).first()

    if active_session and datetime.now() > active_session.end_time:
        active_session.active = False
        db.session.commit()
        active_session = None

    members = ClassMembership.query.filter_by(class_id=class_id).all()

    if request.method == "POST":
        if not active_session:
            return render_template(
                "manual_attendance.html",
                user=user, class_obj=class_obj, members=members,
                active_session=None,
                error="There is no active attendance session. Manual attendance is only available while attendance is live."
            )

        target_user_id = request.form.get("user_id")

        target_membership = ClassMembership.query.filter_by(
            user_id=target_user_id, class_id=class_id
        ).first()

        if not target_membership or target_membership.role == "owner":
            return render_template(
                "manual_attendance.html",
                user=user, class_obj=class_obj, members=members,
                active_session=active_session,
                error="Please select a valid class member."
            )

        existing_record = AttendanceRecord.query.filter_by(
            session_id=active_session.id, user_id=target_user_id
        ).first()

        if existing_record:
            return render_template(
                "manual_attendance.html",
                user=user, class_obj=class_obj, members=members,
                active_session=active_session,
                error="This student already has an attendance record for the current session."
            )

        record = AttendanceRecord(
            class_id=class_id,
            session_id=active_session.id,
            user_id=int(target_user_id),
            timestamp=datetime.now(),
            status="Present (Manual)",
            distance_meters=None
        )

        db.session.add(record)
        db.session.commit()

        return render_template(
            "manual_attendance.html",
            user=user, class_obj=class_obj, members=members,
            active_session=active_session,
            success="Student has been marked present manually."
        )

    return render_template(
        "manual_attendance.html",
        user=user, class_obj=class_obj, members=members,
        active_session=active_session, error=None, success=None
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)