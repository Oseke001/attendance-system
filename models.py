from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    matric_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )


class Class(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    class_code = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    latitude = db.Column(
        db.Float,
        nullable=True
    )

    longitude = db.Column(
        db.Float,
        nullable=True
    )

    radius_meters = db.Column(
        db.Float,
        nullable=True,
        default=50.0
    )


class ClassMembership(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    class_id = db.Column(
        db.Integer,
        db.ForeignKey("class.id"),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="member"
    )

    user = db.relationship(
        "User",
        backref="class_memberships"
    )

    class_obj = db.relationship(
        "Class",
        backref="memberships"
    )


class AttendanceSession(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    class_id = db.Column(
        db.Integer,
        db.ForeignKey("class.id"),
        nullable=False
    )

    code = db.Column(
        db.String(20),
        nullable=False
    )

    start_time = db.Column(
        db.DateTime,
        nullable=False
    )

    end_time = db.Column(
        db.DateTime,
        nullable=False
    )

    active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    # Location settings used for this specific attendance session.
    # This allows each session to use a different location/radius
    # while still allowing location verification to be optional.
    location_enabled = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    latitude = db.Column(
        db.Float,
        nullable=True
    )

    longitude = db.Column(
        db.Float,
        nullable=True
    )

    radius_meters = db.Column(
        db.Float,
        nullable=True
    )


class AttendanceRecord(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    class_id = db.Column(
        db.Integer,
        db.ForeignKey("class.id"),
        nullable=False
    )

    session_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_session.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    timestamp = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now
    )

    status = db.Column(
        db.String(50),
        nullable=False
    )

    student_lat = db.Column(
        db.Float,
        nullable=True
    )

    student_lng = db.Column(
        db.Float,
        nullable=True
    )

    distance_meters = db.Column(
        db.Float,
        nullable=True
    )

    user = db.relationship(
        "User",
        backref="attendance_records"
    )

    class_obj = db.relationship(
        "Class",
        backref="attendance_records"
    )

    session = db.relationship(
        "AttendanceSession",
        backref="attendance_records"
    )


class Announcement(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    class_id = db.Column(
        db.Integer,
        db.ForeignKey("class.id"),
        nullable=False
    )

    author_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    timestamp = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now
    )

    author = db.relationship(
        "User",
        backref="announcements"
    )

    class_obj = db.relationship(
        "Class",
        backref="announcements"
    )