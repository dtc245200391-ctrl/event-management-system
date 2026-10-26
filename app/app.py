import os
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from prometheus_client import make_wsgi_app

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://event_user:event_password@db:5432/event_db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

HTTP_REQUESTS = Counter("event_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
HTTP_LATENCY = Histogram("event_http_request_duration_seconds", "HTTP request duration", ["endpoint"])

class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Khác")
    venue = db.Column(db.String(160), nullable=False)
    event_date = db.Column(db.String(30), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    capacity = db.Column(db.Integer, nullable=False, default=100)
    description = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    registrations = db.relationship("Registration", backref="event", cascade="all, delete-orphan")

class Registration(db.Model):
    __tablename__ = "registrations"
    id = db.Column(db.Integer, primary_key=True)
    attendee_name = db.Column(db.String(120), nullable=False)
    attendee_email = db.Column(db.String(160), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="Đã đăng ký")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)

@app.before_request
def before_request():
    request._started_at = time.perf_counter()

@app.after_request
def after_request(response):
    started = getattr(request, "_started_at", time.perf_counter())
    endpoint = request.endpoint or "unknown"
    HTTP_REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
    HTTP_LATENCY.labels(endpoint).observe(max(0, time.perf_counter() - started))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

def seed_events():
    if Event.query.count() == 0:
        db.session.add_all([
            Event(title="Đêm nhạc E/Vent Acoustic", category="Âm nhạc", venue="Hội trường A", event_date="2026-11-20 19:00", price=150000, capacity=120, description="Đêm nhạc acoustic dành cho sinh viên và người yêu âm nhạc."),
            Event(title="Hội thảo Công nghệ xanh", category="Hội thảo", venue="Phòng hội thảo B", event_date="2026-11-25 08:30", price=50000, capacity=80, description="Chia sẻ ý tưởng công nghệ và phát triển bền vững."),
            Event(title="Ngày hội Sáng tạo trẻ", category="Cộng đồng", venue="Sân trung tâm", event_date="2026-12-05 09:00", price=0, capacity=250, description="Hoạt động giao lưu, trưng bày sản phẩm và kết nối cộng đồng.")
        ])
        db.session.commit()

@app.route("/")
def index():
    events = Event.query.order_by(Event.event_date.asc()).all()
    return render_template("index.html", events=events)

@app.route("/events/new", methods=["GET", "POST"])
def new_event():
    if request.method == "POST":
        try:
            title = request.form.get("title", "").strip()
            venue = request.form.get("venue", "").strip()
            event_date = request.form.get("event_date", "").strip()
            if not title or not venue or not event_date:
                flash("Vui lòng nhập tên sự kiện, địa điểm và thời gian.", "error")
                return redirect(url_for("new_event"))
            event = Event(
                title=title, category=request.form.get("category", "Khác").strip() or "Khác",
                venue=venue, event_date=event_date,
                price=float(request.form.get("price", 0) or 0),
                capacity=max(1, int(request.form.get("capacity", 100) or 100)),
                description=request.form.get("description", "").strip()
            )
            db.session.add(event); db.session.commit()
            app.logger.info("Created event id=%s title=%s", event.id, event.title)
            flash("Đã tạo sự kiện.", "success")
            return redirect(url_for("index"))
        except (ValueError, TypeError):
            db.session.rollback()
            flash("Giá vé hoặc sức chứa không hợp lệ.", "error")
    return render_template("event_form.html")

@app.route("/events/<int:event_id>/register", methods=["POST"])
def register(event_id):
    event = db.session.get(Event, event_id)
    if event is None:
        flash("Không tìm thấy sự kiện.", "error")
        return redirect(url_for("index"))
    try:
        name = request.form.get("attendee_name", "").strip()
        email = request.form.get("attendee_email", "").strip()
        quantity = int(request.form.get("quantity", 1))
        registered = sum(r.quantity for r in event.registrations)
        if not name or not email or quantity < 1:
            flash("Vui lòng nhập họ tên, email và số lượng vé hợp lệ.", "error")
        elif registered + quantity > event.capacity:
            flash("Sự kiện không còn đủ chỗ cho số vé yêu cầu.", "error")
        else:
            registration = Registration(
                attendee_name=name, attendee_email=email, quantity=quantity,
                total_amount=event.price * quantity, event_id=event.id
            )
            db.session.add(registration); db.session.commit()
            app.logger.info("Registration created id=%s event_id=%s", registration.id, event.id)
            flash(f"Đăng ký thành công. Mã đăng ký: EV-{registration.id:05d}", "success")
    except (ValueError, TypeError):
        db.session.rollback()
        flash("Số lượng vé không hợp lệ.", "error")
    return redirect(url_for("index"))

@app.route("/admin/registrations")
def registrations():
    rows = Registration.query.order_by(Registration.created_at.desc()).all()
    return render_template("registrations.html", registrations=rows)

@app.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="connected"), 200
    except Exception as exc:
        app.logger.exception("Health check database failure")
        return jsonify(status="error", database="unavailable"), 503

@app.route("/metrics")
def metrics():
    from flask import Response
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

with app.app_context():
    # Wait briefly for PostgreSQL readiness; Compose healthcheck also gates startup.
    for attempt in range(30):
        try:
            db.create_all()
            seed_events()
            break
        except Exception:
            db.session.rollback()
            app.logger.warning("Database not ready; retry %s/30", attempt + 1)
            time.sleep(2)
    else:
        app.logger.error("Could not initialize database after retries")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
