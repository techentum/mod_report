from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import (
    Downtime,
    GuestOpportunity,
    HighPaw,
    Incident,
    ModMeal,
    OutletInspection,
    RoomInspection,
    Shift,
    User,
)

auth_bp = Blueprint("auth", __name__)
mod_bp = Blueprint("mod", __name__)


@auth_bp.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        return redirect(url_for("mod.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.register"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return redirect(url_for("auth.register"))
        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("mod.dashboard"))
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.", "error")
            return redirect(url_for("auth.login"))
        login_user(user)
        return redirect(url_for("mod.dashboard"))
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@mod_bp.route("/dashboard")
@login_required
def dashboard():
    open_shift = Shift.query.filter_by(mod_id=current_user.id, status="open").first()
    closed_shifts = Shift.query.filter_by(status="closed").order_by(Shift.created_at.desc()).all()
    return render_template("dashboard.html", open_shift=open_shift, closed_shifts=closed_shifts)


@mod_bp.route("/shift/new", methods=["GET", "POST"])
@login_required
def new_shift():
    existing = Shift.query.filter_by(mod_id=current_user.id, status="open").first()
    if existing:
        flash("You already have an open shift. Continue it below.", "warning")
        return redirect(url_for("mod.shift_detail", shift_id=existing.id))
    if request.method == "POST":
        date_value = request.form.get("date")
        schedule = request.form.get("schedule")
        occupancy = request.form.get("occupancy") or None
        arrivals = request.form.get("arrivals") or None
        departures = request.form.get("departures") or None
        shift = Shift(
            mod_id=current_user.id,
            date=datetime.strptime(date_value, "%Y-%m-%d").date(),
            schedule=schedule,
            occupancy=int(occupancy) if occupancy else None,
            arrivals=int(arrivals) if arrivals else None,
            departures=int(departures) if departures else None,
            gm_agm=request.form.get("gm_agm"),
            housekeeping=request.form.get("housekeeping"),
            food_beverage=request.form.get("food_beverage"),
            sales=request.form.get("sales"),
            aquatics=request.form.get("aquatics"),
            retail_attractions=request.form.get("retail_attractions"),
            kids_entertainment=request.form.get("kids_entertainment"),
            guest_services=request.form.get("guest_services"),
            hr=request.form.get("hr"),
            finance=request.form.get("finance"),
            engineering=request.form.get("engineering"),
            it=request.form.get("it"),
        )
        db.session.add(shift)
        db.session.commit()
        return redirect(url_for("mod.shift_detail", shift_id=shift.id))
    return render_template("shift_new.html")


@mod_bp.route("/shift/<int:shift_id>")
@login_required
def shift_detail(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    return render_template("shift_detail.html", shift=shift)


@mod_bp.route("/shift/<int:shift_id>/close", methods=["POST"])
@login_required
def close_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    nps_score = request.form.get("nps_score") or None
    nps_rank = request.form.get("nps_rank") or None
    shift.nps_score = int(nps_score) if nps_score else None
    shift.nps_rank = int(nps_rank) if nps_rank else None
    shift.quality_assurance = request.form.get("quality_assurance")
    shift.suggestions = request.form.get("suggestions")
    shift.shift_notes = request.form.get("shift_notes")
    pass_down_time = request.form.get("pass_down_time")
    shift.pass_down_time = (
        datetime.strptime(pass_down_time, "%H:%M").time() if pass_down_time else None
    )
    shift.pass_down_next_mod = request.form.get("pass_down_next_mod")
    shift.pass_down_notes = request.form.get("pass_down_notes")
    shift.status = "closed"
    db.session.commit()
    return redirect(url_for("mod.report", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/incident", methods=["POST"])
@login_required
def add_incident(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    incident = Incident(
        shift_id=shift.id,
        code=request.form.get("code"),
        incident_time=datetime.strptime(request.form.get("incident_time"), "%H:%M").time(),
        location=request.form.get("location"),
        notes=request.form.get("notes"),
    )
    db.session.add(incident)
    db.session.commit()
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/downtime", methods=["POST"])
@login_required
def add_downtime(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    end_time = request.form.get("end_time")
    downtime = Downtime(
        shift_id=shift.id,
        outlet=request.form.get("outlet"),
        start_time=datetime.strptime(request.form.get("start_time"), "%H:%M").time(),
        end_time=datetime.strptime(end_time, "%H:%M").time() if end_time else None,
        reason=request.form.get("reason"),
    )
    db.session.add(downtime)
    db.session.commit()
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/guest-opportunity", methods=["POST"])
@login_required
def add_guest_opportunity(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    opportunity = GuestOpportunity(
        shift_id=shift.id,
        last_name=request.form.get("last_name"),
        room=request.form.get("room"),
        description=request.form.get("description"),
        compensation=request.form.get("compensation"),
    )
    db.session.add(opportunity)
    db.session.commit()
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/room-inspection", methods=["POST"])
@login_required
def add_room_inspection(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    inspection = RoomInspection(
        shift_id=shift.id,
        room_number=request.form.get("room_number"),
        room_type=request.form.get("room_type"),
        successes=request.form.get("successes"),
        opportunities=request.form.get("opportunities"),
    )
    db.session.add(inspection)
    db.session.commit()
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/outlet-inspection", methods=["POST"])
@login_required
def add_outlet_inspection(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    inspection = OutletInspection(
        shift_id=shift.id,
        outlet=request.form.get("outlet"),
        inspection_time=datetime.strptime(request.form.get("inspection_time"), "%H:%M").time(),
        successes=request.form.get("successes"),
        opportunities=request.form.get("opportunities"),
    )
    db.session.add(inspection)
    db.session.commit()
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/high-paw", methods=["POST"])
@login_required
def add_high_paw(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    high_paw = HighPaw(
        shift_id=shift.id,
        pack_members=request.form.get("pack_members"),
        department=request.form.get("department"),
        description=request.form.get("description"),
    )
    db.session.add(high_paw)
    db.session.commit()
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/mod-meal", methods=["POST"])
@login_required
def add_mod_meal(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id:
        abort(403)
    meal = ModMeal(
        shift_id=shift.id,
        outlet=request.form.get("outlet"),
        menu_item=request.form.get("menu_item"),
        feedback=request.form.get("feedback"),
    )
    db.session.add(meal)
    db.session.commit()
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/report/<int:shift_id>")
@login_required
def report(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.status == "open" and shift.mod_id != current_user.id:
        abort(403)
    return render_template("report.html", shift=shift)
