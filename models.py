"""
SQLAlchemy models for the Bus Ticket Booking system.
Mirrors the original MySQL schema (busticket.sql + advanced_modules.sql)
but with proper types, relationships and hashed passwords.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Admin(db.Model):
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key=True)
    uname = db.Column(db.String(55), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Register(db.Model):
    """End users of the site (renamed from PHP's `register` table)."""
    __tablename__ = "register"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(55), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    address = db.Column(db.String(120), nullable=False)
    pnumber = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(55), nullable=False)
    uname = db.Column(db.String(55), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(55), default="")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Bus(db.Model):
    __tablename__ = "bus"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(55), nullable=False)       # operator/company name
    bname = db.Column(db.String(55), nullable=False)      # bus name
    address = db.Column(db.String(120), nullable=False)
    pnumber = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(55), nullable=False)
    source = db.Column(db.String(55), nullable=False)
    dest = db.Column(db.String(55), nullable=False)
    stop = db.Column(db.String(50), default="")
    seats_total = db.Column(db.Integer, default=36)
    price = db.Column(db.Integer, nullable=False)
    btype = db.Column(db.String(20), nullable=False)      # AC / Non-AC
    stime = db.Column(db.String(20), nullable=False)
    atime = db.Column(db.String(20), nullable=False)

    tickets = db.relationship("BusTicket", backref="bus", lazy="dynamic")
    ratings = db.relationship("Rating", backref="bus", lazy="dynamic")

    @property
    def avg_rating(self):
        rows = self.ratings.all()
        if not rows:
            return None
        return sum(r.stars for r in rows) / len(rows)

    def booked_seats(self):
        seats = set()
        for t in self.tickets:
            if t.status != "Cancelled":
                for s in (t.seat or "").split(","):
                    s = s.strip()
                    if s:
                        seats.add(int(s))
        return seats


class BusTicket(db.Model):
    __tablename__ = "bustick"
    id = db.Column(db.Integer, primary_key=True)
    tid = db.Column(db.String(20), unique=True, nullable=False)   # e.g. Tic12
    uid = db.Column(db.String(55), nullable=False)                # username
    bid = db.Column(db.Integer, db.ForeignKey("bus.id"), nullable=False)
    seat = db.Column(db.String(120), nullable=False)              # "1,2,3"
    price = db.Column(db.Integer, nullable=False)                 # price per seat
    ch = db.Column(db.Integer, default=0)                         # children count
    al = db.Column(db.Integer, default=0)                         # adult count
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="Booked")           # Booked/Paid/Cancelled
    date = db.Column(db.String(20), default="")                   # journey date
    stop = db.Column(db.String(50), default="")
    created_on = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship("Payment", backref="ticket_ref", lazy="dynamic")

    @property
    def seat_list(self):
        return [s.strip() for s in (self.seat or "").split(",") if s.strip()]


class Feed(db.Model):
    __tablename__ = "feed"
    id = db.Column(db.Integer, primary_key=True)
    uname = db.Column(db.String(55), nullable=False)
    feed = db.Column(db.Text, nullable=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    tid = db.Column(db.String(20), db.ForeignKey("bustick.tid"), nullable=False)
    uid = db.Column(db.String(55), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(30), nullable=False)
    txn_id = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(20), default="Success")
    paid_on = db.Column(db.DateTime, default=datetime.utcnow)


class Rating(db.Model):
    __tablename__ = "ratings"
    id = db.Column(db.Integer, primary_key=True)
    bid = db.Column(db.Integer, db.ForeignKey("bus.id"), nullable=False)
    uid = db.Column(db.String(55), nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    review = db.Column(db.String(255), nullable=False)
    rated_on = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(55), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
