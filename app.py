"""
Bus Ticket Booking System — Flask conversion of the original PHP/MySQL app.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000

Default admin login:      admin / admin123
Default demo user login:  vinoth / password123
"""
import random
import string
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, abort)

from models import db, Admin, Register, Bus, BusTicket, Feed, Payment, Rating, Notification
from ai_recommender import recommend_seats, predict_peak_days

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///busticket.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

SEAT_COUNT = 36


# ----------------------------------------------------------------------
# Helpers / decorators
# ----------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not session.get("uname"):
            flash("Please log in first.", "warning")
            return redirect(url_for("index"))
        return f(*a, **kw)
    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not session.get("admin"):
            flash("Admin login required.", "warning")
            return redirect(url_for("index"))
        return f(*a, **kw)
    return wrapped


def gen_ticket_id():
    last = db.session.query(db.func.max(BusTicket.id)).scalar() or 0
    return f"Tic{last + 1}"


def gen_txn_id():
    return "TXN" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


def current_user():
    uname = session.get("uname")
    if not uname:
        return None
    return Register.query.filter_by(uname=uname).first()


@app.context_processor
def inject_globals():
    user = current_user()
    unread = 0
    if user:
        unread = Notification.query.filter_by(uid=user.uname, is_read=False).count()
    return dict(current_user=user, is_admin=bool(session.get("admin")), unread_count=unread)


# ----------------------------------------------------------------------
# Public pages
# ----------------------------------------------------------------------
@app.route("/")
def index():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    if session.get("uname"):
        return redirect(url_for("user_home"))
    return render_template("index.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/login", methods=["POST"])
def login():
    uname = request.form.get("uname", "").strip()
    password = request.form.get("password", "")

    admin = Admin.query.filter_by(uname=uname).first()
    if admin and admin.check_password(password):
        session.clear()
        session["admin"] = uname
        flash("Welcome back, admin.", "success")
        return redirect(url_for("admin_dashboard"))

    user = Register.query.filter_by(uname=uname).first()
    if user and user.check_password(password):
        session.clear()
        session["uname"] = user.uname
        session["uid"] = user.id
        flash(f"Welcome back, {user.name}.", "success")
        return redirect(url_for("user_home"))

    flash("Login unsuccessful. Check your username and password.", "danger")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uname = request.form.get("uname", "").strip()
        if Register.query.filter_by(uname=uname).first():
            flash("Username already taken.", "danger")
            return redirect(url_for("register"))

        user = Register(
            name=request.form.get("name", "").strip(),
            gender=request.form.get("gender", ""),
            address=request.form.get("address", "").strip(),
            pnumber=request.form.get("pnumber", "").strip(),
            email=request.form.get("email", "").strip(),
            uname=uname,
            status="",
        )
        user.set_password(request.form.get("password", ""))
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. You can log in now.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


# ----------------------------------------------------------------------
# User area
# ----------------------------------------------------------------------
@app.route("/home")
@login_required
def user_home():
    sources = [r[0] for r in db.session.query(Bus.source).distinct().order_by(Bus.source)]
    dests = [r[0] for r in db.session.query(Bus.dest).distinct().order_by(Bus.dest)]

    src = request.args.get("src", "")
    des = request.args.get("des", "")
    buses = []
    searched = bool(src or des)
    if searched:
        q = Bus.query
        if src and src != "Select":
            q = q.filter_by(source=src)
        if des and des != "Select":
            q = q.filter_by(dest=des)
        buses = q.all()

    return render_template("user/home.html", sources=sources, dests=dests,
                            buses=buses, searched=searched, src=src, des=des)


@app.route("/bus/<int:bus_id>", methods=["GET", "POST"])
@login_required
def bus_detail(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    booked = bus.booked_seats()

    if request.method == "POST":
        seats = request.form.get("seat", "").strip()
        adult = int(request.form.get("adult", 0) or 0)
        children = int(request.form.get("children", 0) or 0)
        journey_date = request.form.get("date", "")
        seat_list = [s for s in seats.split(",") if s]

        if not seat_list:
            flash("Please select at least one seat.", "danger")
            return redirect(url_for("bus_detail", bus_id=bus_id))
        if any(int(s) in booked for s in seat_list):
            flash("One or more selected seats are already booked. Please choose again.", "danger")
            return redirect(url_for("bus_detail", bus_id=bus_id))

        total_pax = adult + children
        total_price = total_pax * bus.price if total_pax else len(seat_list) * bus.price

        ticket = BusTicket(
            tid=gen_ticket_id(),
            uid=session["uname"],
            bid=bus.id,
            seat=seats,
            price=bus.price,
            ch=children,
            al=adult,
            total=total_price,
            status="Booked",
            date=journey_date,
            stop=bus.stop or "",
        )
        db.session.add(ticket)
        db.session.commit()
        flash(f"Ticket {ticket.tid} booked! Head to My Bookings to pay and download your e-ticket.", "success")
        return redirect(url_for("my_bookings"))

    return render_template("user/bus_detail.html", bus=bus, booked=booked, seat_count=SEAT_COUNT,
                            recommended=recommend_seats(BusTicket.query.all(), SEAT_COUNT, booked, num_seats=3))


@app.route("/bookings")
@login_required
def my_bookings():
    tickets = (BusTicket.query.filter_by(uid=session["uname"])
               .order_by(BusTicket.id.desc()).all())
    return render_template("user/bookings.html", tickets=tickets)


@app.route("/cancel", methods=["GET", "POST"])
@login_required
def cancel_ticket():
    if request.method == "POST":
        tno = request.form.get("tno", "").strip()
        ticket = BusTicket.query.filter_by(tid=tno, uid=session["uname"]).first()
        if not ticket:
            flash("Ticket not found or does not belong to you.", "danger")
        else:
            db.session.delete(ticket)
            db.session.commit()
            flash(f"Ticket {tno} cancelled.", "success")
        return redirect(url_for("cancel_ticket"))

    tickets = (BusTicket.query.filter_by(uid=session["uname"])
               .order_by(BusTicket.id.desc()).all())
    return render_template("user/cancel.html", tickets=tickets)


@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment_gateway():
    tid = request.args.get("tid", "").strip()
    ticket = None
    if tid:
        ticket = BusTicket.query.filter_by(tid=tid, uid=session["uname"]).first()

    if request.method == "POST" and ticket:
        method = request.form.get("method", "UPI")
        txn = gen_txn_id()
        amount = ticket.total

        payment = Payment(tid=ticket.tid, uid=session["uname"], amount=amount,
                           method=method, txn_id=txn, status="Success")
        db.session.add(payment)
        ticket.status = "Paid"
        db.session.add(Notification(
            uid=session["uname"],
            message=f"Payment of Rs.{amount} received for ticket {ticket.tid} ({method}). Txn: {txn}"
        ))
        db.session.commit()
        flash(f"Payment successful. Transaction ID: {txn}", "success")
        return redirect(url_for("payment_gateway", tid=ticket.tid))

    return render_template("user/payment.html", ticket=ticket, tid=tid)


@app.route("/eticket")
@login_required
def eticket():
    tid = request.args.get("tid", "").strip()
    ticket = None
    if tid:
        ticket = BusTicket.query.filter_by(tid=tid, uid=session["uname"]).first()
    return render_template("user/eticket.html", ticket=ticket, tid=tid)


@app.route("/rate", methods=["GET", "POST"])
@login_required
def rate_bus():
    if request.method == "POST":
        bid = request.form.get("bid", type=int)
        stars = request.form.get("stars", type=int)
        review = request.form.get("review", "").strip()
        if bid and stars and 1 <= stars <= 5 and review:
            db.session.add(Rating(bid=bid, uid=session["uname"], stars=stars, review=review))
            db.session.commit()
            flash("Thanks! Your review has been posted.", "success")
        else:
            flash("Please choose a bus, star rating, and write a short review.", "danger")
        return redirect(url_for("rate_bus"))

    buses = Bus.query.order_by(Bus.bname).all()
    reviews = (Rating.query.order_by(Rating.id.desc()).limit(15).all())
    return render_template("user/rate.html", buses=buses, reviews=reviews)


@app.route("/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    if request.method == "POST":
        text = request.form.get("feed", "").strip()
        if text:
            db.session.add(Feed(uname=session["uname"], feed=text))
            db.session.commit()
            flash("Thanks for your feedback!", "success")
        return redirect(url_for("feedback"))
    return render_template("user/feedback.html")


@app.route("/notifications/read")
@login_required
def mark_notifications_read():
    Notification.query.filter_by(uid=session["uname"], is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(request.referrer or url_for("user_home"))


# ----------------------------------------------------------------------
# Admin area
# ----------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    admins = Admin.query.order_by(Admin.id).all()
    return render_template("admin/dashboard.html", admins=admins)


@app.route("/admin/admins/add", methods=["POST"])
@admin_required
def admin_add_admin():
    uname = request.form.get("admin_uname", "").strip()
    password = request.form.get("admin_password", "")

    if not uname or not password:
        flash("Admin username and password are required.", "danger")
        return redirect(url_for("admin_dashboard"))

    if Admin.query.filter_by(uname=uname).first():
        flash("That admin username is already taken.", "danger")
        return redirect(url_for("admin_dashboard"))

    new_admin = Admin(uname=uname)
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()
    flash(f"Admin '{uname}' added successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/buses/add", methods=["POST"])
@admin_required
def admin_add_bus():
    bus = Bus(
        name=request.form.get("name", "").strip(),
        bname=request.form.get("bname", "").strip(),
        address=request.form.get("address", "").strip(),
        pnumber=request.form.get("pnumber", "").strip(),
        email=request.form.get("email", "").strip(),
        source=request.form.get("src", "").strip(),
        dest=request.form.get("des", "").strip(),
        stop=request.form.get("stop", "").strip(),
        price=request.form.get("price", type=int) or 0,
        btype=request.form.get("btype", "AC"),
        stime=request.form.get("stime", "").strip(),
        atime=request.form.get("atime", "").strip(),
    )
    db.session.add(bus)
    db.session.commit()
    flash("Bus added successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/buses")
@admin_required
def admin_buses():
    buses = Bus.query.order_by(Bus.id).all()
    return render_template("admin/buses.html", buses=buses)


@app.route("/admin/buses/<int:bus_id>/delete", methods=["POST"])
@admin_required
def admin_delete_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    db.session.delete(bus)
    db.session.commit()
    flash("Bus removed.", "info")
    return redirect(url_for("admin_buses"))


@app.route("/admin/users")
@admin_required
def admin_users():
    users = Register.query.order_by(Register.id).all()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = Register.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User removed.", "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    rows = (db.session.query(BusTicket, Bus, Register)
            .join(Bus, Bus.id == BusTicket.bid)
            .outerjoin(Register, Register.uname == BusTicket.uid)
            .order_by(BusTicket.id.desc()).all())
    return render_template("admin/bookings.html", rows=rows)


@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    items = Feed.query.order_by(Feed.id.desc()).all()
    return render_template("admin/feedback.html", items=items)


@app.route("/admin/reports")
@admin_required
def admin_reports():
    total_bookings = BusTicket.query.count()
    total_revenue = db.session.query(db.func.coalesce(db.func.sum(BusTicket.total), 0)).scalar()
    total_buses = Bus.query.count()
    total_users = Register.query.count()
    avg_rating = db.session.query(db.func.avg(Rating.stars)).scalar()

    routes = (db.session.query(Bus.source, Bus.dest,
                                db.func.count(BusTicket.id),
                                db.func.coalesce(db.func.sum(BusTicket.total), 0))
              .join(BusTicket, BusTicket.bid == Bus.id)
              .group_by(Bus.source, Bus.dest)
              .order_by(db.func.count(BusTicket.id).desc())
              .limit(6).all())
    route_labels = [f"{s} - {d}" for s, d, _, _ in routes]
    route_counts = [c for _, _, c, _ in routes]
    route_revenue = [r for _, _, _, r in routes]

    status_rows = (db.session.query(BusTicket.status, db.func.count(BusTicket.id))
                   .group_by(BusTicket.status).all())
    status_labels = [s or "Booked" for s, _ in status_rows]
    status_counts = [c for _, c in status_rows]

    peak_forecast = predict_peak_days(BusTicket.query.all(), days_ahead=7)

    return render_template(
        "admin/reports.html",
        total_bookings=total_bookings, total_revenue=total_revenue,
        total_buses=total_buses, total_users=total_users, avg_rating=avg_rating,
        route_labels=route_labels, route_counts=route_counts, route_revenue=route_revenue,
        status_labels=status_labels, status_counts=status_counts,
        peak_forecast=peak_forecast,
    )


# ----------------------------------------------------------------------
# DB init + seed data (mirrors the original busticket.sql sample rows)
# ----------------------------------------------------------------------
def seed_database():
    if Admin.query.first():
        return  # already seeded

    admin = Admin(uname="admin")
    admin.set_password("admin123")
    db.session.add(admin)

    demo_users = [
        ("vinoth", "Vinoth", "Male", "Trichy", "9876543210", "vinoth@example.com", "password123"),
        ("sam", "Sam", "Male", "Trichy", "9876500000", "sam@example.com", "password123"),
        ("kannan", "Kannan", "Male", "Trichy", "8124436310", "kannan@example.com", "password123"),
    ]
    for uname, name, gender, address, pnumber, email, pw in demo_users:
        u = Register(name=name, gender=gender, address=address, pnumber=pnumber,
                     email=email, uname=uname, status="")
        u.set_password(pw)
        db.session.add(u)

    buses = [
        dict(name="test", bname="Kps", address="Trichy", pnumber="9998887771",
             email="kps@example.com", source="Trichy", dest="Madurai", stop="Viralimalai",
             price=150, btype="AC", stime="10:00 AM", atime="12:00 PM"),
        dict(name="test", bname="Kpm", address="Trichy", pnumber="9998887772",
             email="kpm@example.com", source="Madurai", dest="Trichy", stop="Trichy Road",
             price=400, btype="AC", stime="10:00 AM", atime="12:00 PM"),
        dict(name="SRS", bname="SRS 01", address="Trichy", pnumber="9998887773",
             email="srs@example.com", source="Trichy", dest="Madurai", stop="",
             price=300, btype="AC", stime="09:00 AM", atime="12:00 PM"),
        dict(name="PLA Bus Service", bname="PLA Madurai", address="Trichy", pnumber="9998887774",
             email="pla@example.com", source="Trichy", dest="Madurai", stop="",
             price=160, btype="Non-AC", stime="10:00 AM", atime="12:00 PM"),
        dict(name="sala", bname="sala Express", address="Trichy", pnumber="9998887775",
             email="sala@example.com", source="Trichy", dest="Chennai", stop="",
             price=200, btype="AC", stime="04:00 AM", atime="08:00 AM"),
        dict(name="SMS Travels", bname="SMS New", address="11 New Street, Trichy", pnumber="9998887776",
             email="sms@example.com", source="Trichy", dest="Chennai", stop="",
             price=320, btype="Non-AC", stime="04:00 AM", atime="10:00 PM"),
    ]
    for b in buses:
        db.session.add(Bus(**b))

    db.session.commit()

    # sample bookings for the demo users
    trichy_madurai = Bus.query.filter_by(bname="SRS 01").first()
    pla = Bus.query.filter_by(bname="PLA Madurai").first()
    if trichy_madurai and pla:
        db.session.add(BusTicket(tid="Tic1", uid="sam", bid=trichy_madurai.id, seat="4",
                                  price=trichy_madurai.price, ch=0, al=1,
                                  total=trichy_madurai.price, status="Booked"))
        db.session.add(BusTicket(tid="Tic2", uid="kannan", bid=pla.id, seat="7",
                                  price=pla.price, ch=0, al=1,
                                  total=pla.price, status="Paid"))
        db.session.add(Feed(uname="vinoth", feed="Great service, buses were on time!"))
        db.session.commit()


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == "__main__":
    app.run(debug=True)
