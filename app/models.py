from datetime import datetime

from flask_login import UserMixin

from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    timezone = db.Column(db.String(120), nullable=True)
    shifts = db.relationship("Shift", backref="mod", lazy=True)


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mod_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    schedule = db.Column(db.String(20), nullable=False)
    occupancy = db.Column(db.Integer, nullable=True)
    arrivals = db.Column(db.Integer, nullable=True)
    departures = db.Column(db.Integer, nullable=True)
    nps_score = db.Column(db.Integer, nullable=True)
    nps_rank = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="open", nullable=False)

    gm_agm = db.Column(db.String(120))
    housekeeping = db.Column(db.String(120))
    food_beverage = db.Column(db.String(120))
    sales = db.Column(db.String(120))
    aquatics = db.Column(db.String(120))
    retail_attractions = db.Column(db.String(120))
    kids_entertainment = db.Column(db.String(120))
    guest_services = db.Column(db.String(120))
    hr = db.Column(db.String(120))
    finance = db.Column(db.String(120))
    engineering = db.Column(db.String(120))
    it = db.Column(db.String(120))

    quality_assurance = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    shift_notes = db.Column(db.Text)

    pass_down_time = db.Column(db.Time)
    pass_down_next_mod = db.Column(db.String(120))
    pass_down_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    incidents = db.relationship("Incident", backref="shift", lazy=True, cascade="all, delete-orphan")
    downtimes = db.relationship("Downtime", backref="shift", lazy=True, cascade="all, delete-orphan")
    guest_opportunities = db.relationship(
        "GuestOpportunity", backref="shift", lazy=True, cascade="all, delete-orphan"
    )
    room_inspections = db.relationship(
        "RoomInspection", backref="shift", lazy=True, cascade="all, delete-orphan"
    )
    outlet_inspections = db.relationship(
        "OutletInspection", backref="shift", lazy=True, cascade="all, delete-orphan"
    )
    high_paws = db.relationship("HighPaw", backref="shift", lazy=True, cascade="all, delete-orphan")
    mod_meals = db.relationship("ModMeal", backref="shift", lazy=True, cascade="all, delete-orphan")


class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shift.id"), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    incident_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text, nullable=True)


class Downtime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shift.id"), nullable=False)
    outlet = db.Column(db.String(120), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time)
    reason = db.Column(db.Text, nullable=False)


class GuestOpportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shift.id"), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    room = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    compensation = db.Column(db.Text, nullable=True)


class RoomInspection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shift.id"), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    room_type = db.Column(db.String(120), nullable=False)
    successes = db.Column(db.Text, nullable=True)
    opportunities = db.Column(db.Text, nullable=True)


class OutletInspection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shift.id"), nullable=False)
    outlet = db.Column(db.String(120), nullable=False)
    inspection_time = db.Column(db.Time, nullable=False)
    successes = db.Column(db.Text, nullable=True)
    opportunities = db.Column(db.Text, nullable=True)


class HighPaw(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shift.id"), nullable=False)
    pack_members = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)


class ModMeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shift.id"), nullable=False)
    outlet = db.Column(db.String(120), nullable=False)
    menu_item = db.Column(db.String(120), nullable=False)
    feedback = db.Column(db.Text, nullable=True)
