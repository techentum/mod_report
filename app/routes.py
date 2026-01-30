from datetime import datetime, timezone
import importlib.util
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
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
    ReportComment,
    Shift,
    User,
)

auth_bp = Blueprint("auth", __name__)
mod_bp = Blueprint("mod", __name__)


def _get_weasyprint():
    if importlib.util.find_spec("weasyprint") is None:
        return None
    from weasyprint import HTML

    return HTML


def _is_admin(user):
    return bool(getattr(user, "is_admin", False))


def _can_edit_shift(shift):
    if _is_admin(current_user):
        return True
    if shift.mod_id == current_user.id:
        return True
    return current_user in shift.editors


def _require_admin():
    if not _is_admin(current_user):
        abort(403)


def _available_timezones():
    return [
        "America/Los_Angeles",
        "America/Denver",
        "America/Chicago",
        "America/New_York",
        "UTC",
    ]


def _resolve_next_mod_name(next_mod_id):
    if not next_mod_id:
        return None
    try:
        user_id = int(next_mod_id)
    except (TypeError, ValueError):
        return None
    user = User.query.get(user_id)
    if not user:
        return None
    return user.name


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_datetime_for_user(value, user):
    if value is None:
        return "-"
    timezone_name = user.timezone or "UTC"
    try:
        tzinfo = ZoneInfo(timezone_name)
    except Exception:
        tzinfo = ZoneInfo("UTC")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tzinfo).strftime("%b %d, %Y %I:%M %p %Z")


@auth_bp.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        return redirect(url_for("mod.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        job_title = request.form.get("job_title", "").strip() or None
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
            job_title=job_title,
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
    admin_open_shifts = []
    if _is_admin(current_user):
        admin_open_shifts = (
            Shift.query.filter_by(status="open")
            .order_by(Shift.created_at.desc())
            .all()
        )
    closed_shifts = Shift.query.filter_by(status="closed").order_by(Shift.created_at.desc()).all()
    created_at_display = (
        _format_datetime_for_user(open_shift.created_at, current_user)
        if open_shift
        else None
    )
    return render_template(
        "dashboard.html",
        open_shift=open_shift,
        admin_open_shifts=admin_open_shifts,
        closed_shifts=closed_shifts,
        created_at_display=created_at_display,
    )


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
    if not _can_edit_shift(shift):
        abort(403)
    created_at_display = _format_datetime_for_user(shift.created_at, current_user)
    users = User.query.order_by(User.name.asc()).all()
    return render_template(
        "shift_detail.html",
        shift=shift,
        created_at_display=created_at_display,
        users=users,
    )


@mod_bp.route("/shift/<int:shift_id>/save-progress", methods=["POST"])
@login_required
def save_shift_progress(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if not _can_edit_shift(shift):
        abort(403)

    def update_if_present(field_name, transformer=None):
        if field_name not in request.form:
            return
        raw_value = request.form.get(field_name)
        if raw_value == "":
            setattr(shift, field_name, None)
            return
        if transformer:
            setattr(shift, field_name, transformer(raw_value))
            return
        setattr(shift, field_name, raw_value)

    update_if_present("gm_agm")
    update_if_present("housekeeping")
    update_if_present("food_beverage")
    update_if_present("sales")
    update_if_present("aquatics")
    update_if_present("retail_attractions")
    update_if_present("kids_entertainment")
    update_if_present("guest_services")
    update_if_present("hr")
    update_if_present("finance")
    update_if_present("engineering")
    update_if_present("it")

    update_if_present("nps_score", lambda value: int(value))
    update_if_present("nps_rank", lambda value: int(value))
    update_if_present("quality_assurance")
    update_if_present("suggestions")
    update_if_present("shift_notes")
    update_if_present(
        "pass_down_time", lambda value: datetime.strptime(value, "%H:%M").time()
    )
    if "pass_down_next_mod" in request.form:
        shift.pass_down_next_mod = _resolve_next_mod_name(
            request.form.get("pass_down_next_mod")
        )
    update_if_present("pass_down_notes")

    db.session.commit()

    if request.headers.get("X-Requested-With") == "fetch":
        return ("", 204)

    flash("Draft saved.", "success")
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/close", methods=["POST"])
@login_required
def close_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id and not _is_admin(current_user):
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
    shift.pass_down_next_mod = _resolve_next_mod_name(
        request.form.get("pass_down_next_mod")
    )
    shift.pass_down_notes = request.form.get("pass_down_notes")
    shift.status = "closed"
    db.session.commit()
    return redirect(url_for("mod.report", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/delete", methods=["POST"])
@login_required
def delete_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id and not _is_admin(current_user):
        abort(403)
    db.session.delete(shift)
    db.session.commit()
    flash("Shift deleted.", "success")
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/shift/<int:shift_id>/incident", methods=["POST"])
@login_required
def add_incident(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if not _can_edit_shift(shift):
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
    if not _can_edit_shift(shift):
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
    if not _can_edit_shift(shift):
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
    if not _can_edit_shift(shift):
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
    if not _can_edit_shift(shift):
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
    if not _can_edit_shift(shift):
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
    if not _can_edit_shift(shift):
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
    if shift.status == "open" and not _can_edit_shift(shift):
        abort(403)
    created_at_display = _format_datetime_for_user(shift.created_at, current_user)
    comments = [
        {
            "comment": comment,
            "created_at_display": _format_datetime_for_user(comment.created_at, current_user),
        }
        for comment in shift.comments
    ]
    return render_template(
        "report.html",
        shift=shift,
        created_at_display=created_at_display,
        comments=comments,
    )


@mod_bp.route("/report/<int:shift_id>/pdf")
@login_required
def report_pdf(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.status == "open" and not _can_edit_shift(shift):
        abort(403)
    html_renderer = _get_weasyprint()
    if html_renderer is None:
        flash(
            "PDF generation is unavailable because WeasyPrint is not installed on the server.",
            "error",
        )
        return redirect(url_for("mod.report", shift_id=shift.id))
    created_at_display = _format_datetime_for_user(shift.created_at, current_user)
    rendered_html = render_template(
        "report.html",
        shift=shift,
        created_at_display=created_at_display,
        comments=[],
        pdf_mode=True,
    )
    pdf_bytes = html_renderer(string=rendered_html, base_url=current_app.root_path).write_pdf()
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=mod-report-{shift.date.isoformat()}.pdf"
    )
    return response


@mod_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    timezones = _available_timezones()
    if request.method == "POST":
        timezone = request.form.get("timezone") or None
        job_title = request.form.get("job_title", "").strip() or None
        current_user.timezone = timezone
        current_user.job_title = job_title
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("mod.settings"))
    return render_template("settings.html", timezones=timezones)


@mod_bp.route("/report/<int:shift_id>/comment", methods=["POST"])
@login_required
def add_report_comment(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.status != "closed":
        abort(400)
    body = request.form.get("comment", "").strip()
    if not body:
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("mod.report", shift_id=shift.id))
    comment = ReportComment(shift_id=shift.id, author_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for("mod.report", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/editors", methods=["POST"])
@login_required
def update_shift_editors(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if shift.mod_id != current_user.id and not _is_admin(current_user):
        abort(403)
    editor_ids = request.form.getlist("editor_ids")
    editors = []
    if editor_ids:
        editors = User.query.filter(User.id.in_(editor_ids)).all()
    shift.editors = editors
    db.session.commit()
    flash("Additional editors updated.", "success")
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/shift/<int:shift_id>/reassign", methods=["POST"])
@login_required
def reassign_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    _require_admin()
    if shift.status != "open":
        flash("Only open shifts can be reassigned.", "error")
        return redirect(url_for("mod.shift_detail", shift_id=shift.id))
    new_mod_id = _parse_int(request.form.get("mod_id"))
    new_mod = User.query.get(new_mod_id) if new_mod_id else None
    if not new_mod:
        flash("Select a valid MOD to reassign this shift.", "error")
        return redirect(url_for("mod.shift_detail", shift_id=shift.id))
    shift.mod_id = new_mod.id
    db.session.commit()
    flash(f"Shift reassigned to {new_mod.name}.", "success")
    return redirect(url_for("mod.shift_detail", shift_id=shift.id))


@mod_bp.route("/admin/users")
@login_required
def admin_users():
    _require_admin()
    users = User.query.order_by(User.name.asc()).all()
    return render_template("admin_users.html", users=users)


@mod_bp.route("/admin/users/new", methods=["GET", "POST"])
@login_required
def admin_user_new():
    _require_admin()
    timezones = _available_timezones()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        job_title = request.form.get("job_title", "").strip() or None
        timezone = request.form.get("timezone") or None
        is_admin = bool(request.form.get("is_admin"))
        if not name or not email or not password:
            flash("Name, email, and password are required.", "error")
            return redirect(url_for("mod.admin_user_new"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return redirect(url_for("mod.admin_user_new"))
        user = User(
            name=name,
            email=email,
            job_title=job_title,
            timezone=timezone,
            is_admin=is_admin,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        flash("User created.", "success")
        return redirect(url_for("mod.admin_users"))
    return render_template("admin_user_form.html", timezones=timezones, user=None)


@mod_bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def admin_user_edit(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    timezones = _available_timezones()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        job_title = request.form.get("job_title", "").strip() or None
        timezone = request.form.get("timezone") or None
        is_admin = bool(request.form.get("is_admin"))
        if not name or not email:
            flash("Name and email are required.", "error")
            return redirect(url_for("mod.admin_user_edit", user_id=user.id))
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash("Email already registered.", "error")
            return redirect(url_for("mod.admin_user_edit", user_id=user.id))
        user.name = name
        user.email = email
        user.job_title = job_title
        user.timezone = timezone
        user.is_admin = is_admin
        password = request.form.get("password", "")
        if password:
            user.password_hash = generate_password_hash(password)
        db.session.commit()
        flash("User updated.", "success")
        return redirect(url_for("mod.admin_users"))
    return render_template("admin_user_form.html", timezones=timezones, user=user)


@mod_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
def admin_user_delete(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("mod.admin_users"))
    if user.shifts or user.comments:
        flash("Reassign or delete the user's shifts and comments before removing them.", "error")
        return redirect(url_for("mod.admin_users"))
    for shift in user.edited_shifts.all():
        shift.editors.remove(user)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "success")
    return redirect(url_for("mod.admin_users"))


@mod_bp.route("/search/reports")
@login_required
def search_reports():
    users = User.query.order_by(User.name.asc()).all()
    query = Shift.query.join(User)
    if not _is_admin(current_user):
        query = query.filter(Shift.status == "closed")
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    mod_id = _parse_int(request.args.get("mod_id", "").strip())
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if status:
        query = query.filter(Shift.status == status)
    if mod_id:
        query = query.filter(Shift.mod_id == mod_id)
    if start_date:
        query = query.filter(Shift.date >= start_date)
    if end_date:
        query = query.filter(Shift.date <= end_date)
    if q:
        query = query.filter(
            or_(
                Shift.schedule.ilike(f"%{q}%"),
                Shift.shift_notes.ilike(f"%{q}%"),
                Shift.quality_assurance.ilike(f"%{q}%"),
                Shift.suggestions.ilike(f"%{q}%"),
                User.name.ilike(f"%{q}%"),
            )
        )
    results = query.order_by(Shift.date.desc()).all()
    return render_template(
        "search_reports.html",
        results=results,
        users=users,
        selected_mod_id=mod_id,
        query_params=request.args,
    )


@mod_bp.route("/search/incidents")
@login_required
def search_incidents():
    users = User.query.order_by(User.name.asc()).all()
    query = Incident.query.join(Shift).join(User)
    if not _is_admin(current_user):
        query = query.filter(Shift.status == "closed")
    q = request.args.get("q", "").strip()
    mod_id = _parse_int(request.args.get("mod_id", "").strip())
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if mod_id:
        query = query.filter(Shift.mod_id == mod_id)
    if start_date:
        query = query.filter(Shift.date >= start_date)
    if end_date:
        query = query.filter(Shift.date <= end_date)
    if q:
        query = query.filter(
            or_(
                Incident.code.ilike(f"%{q}%"),
                Incident.location.ilike(f"%{q}%"),
                Incident.notes.ilike(f"%{q}%"),
                User.name.ilike(f"%{q}%"),
            )
        )
    results = query.order_by(Shift.date.desc(), Incident.incident_time.desc()).all()
    return render_template(
        "search_incidents.html",
        results=results,
        users=users,
        selected_mod_id=mod_id,
        query_params=request.args,
    )


@mod_bp.route("/search/downtime")
@login_required
def search_downtime():
    users = User.query.order_by(User.name.asc()).all()
    query = Downtime.query.join(Shift).join(User)
    if not _is_admin(current_user):
        query = query.filter(Shift.status == "closed")
    q = request.args.get("q", "").strip()
    mod_id = _parse_int(request.args.get("mod_id", "").strip())
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if mod_id:
        query = query.filter(Shift.mod_id == mod_id)
    if start_date:
        query = query.filter(Shift.date >= start_date)
    if end_date:
        query = query.filter(Shift.date <= end_date)
    if q:
        query = query.filter(
            or_(
                Downtime.outlet.ilike(f"%{q}%"),
                Downtime.reason.ilike(f"%{q}%"),
                User.name.ilike(f"%{q}%"),
            )
        )
    results = query.order_by(Shift.date.desc(), Downtime.start_time.desc()).all()
    return render_template(
        "search_downtime.html",
        results=results,
        users=users,
        selected_mod_id=mod_id,
        query_params=request.args,
    )


@mod_bp.route("/search/guest-opportunities")
@login_required
def search_guest_opportunities():
    users = User.query.order_by(User.name.asc()).all()
    query = GuestOpportunity.query.join(Shift).join(User)
    if not _is_admin(current_user):
        query = query.filter(Shift.status == "closed")
    q = request.args.get("q", "").strip()
    mod_id = _parse_int(request.args.get("mod_id", "").strip())
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if mod_id:
        query = query.filter(Shift.mod_id == mod_id)
    if start_date:
        query = query.filter(Shift.date >= start_date)
    if end_date:
        query = query.filter(Shift.date <= end_date)
    if q:
        query = query.filter(
            or_(
                GuestOpportunity.last_name.ilike(f"%{q}%"),
                GuestOpportunity.room.ilike(f"%{q}%"),
                GuestOpportunity.description.ilike(f"%{q}%"),
                GuestOpportunity.compensation.ilike(f"%{q}%"),
                User.name.ilike(f"%{q}%"),
            )
        )
    results = query.order_by(Shift.date.desc(), GuestOpportunity.last_name.asc()).all()
    return render_template(
        "search_guest_opportunities.html",
        results=results,
        users=users,
        selected_mod_id=mod_id,
        query_params=request.args,
    )
