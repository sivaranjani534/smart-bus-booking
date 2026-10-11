# RoadLine — Bus Ticket Booking (Flask)

A full Python/Flask rewrite of the original PHP + MySQL "bus ticket advanced" site
(the `busticket.sql` + `advanced_modules.sql` schema and all its PHP pages).

## What's included

Everything from the original app, rebuilt:

| Original PHP page(s)                    | Flask equivalent                                   |
|-------------------------------------------|----------------------------------------------------|
| `index.php` / `register.php` (login+signup) | `/`, `/register`, `/login`                        |
| `user.php` (search buses)                 | `/home`                                             |
| `view1.php` (bus + seat booking)          | `/bus/<id>` (interactive seat map)                  |
| `veiwbook.php` (my bookings)              | `/bookings`                                         |
| `cticket.php` (cancel ticket)             | `/cancel`                                           |
| `payment_gateway.php`                     | `/payment` (simulated payment, no real gateway)     |
| `eticket.php`                             | `/eticket` (printable e-ticket)                     |
| `rate_bus.php`                            | `/rate`                                             |
| `feed.php`                                | `/feedback`                                         |
| `contact.html`             | `/contact`                                |
| `admin.php` (add bus)                     | `/admin`                                            |
| `busveiw.php` (bus list)                  | `/admin/buses`                                      |
| `uview.php` (user list)                   | `/admin/users`                                      |
| `view.php` (all bookings)                 | `/admin/bookings`                                   |
| `viewfeed.php`                            | `/admin/feedback`                                   |
| `admin_reports.php`                       | `/admin/reports` (Chart.js analytics)               |

## Improvements over the original

The original PHP built every SQL query by string-concatenating `$_POST`/`$_GET`
values directly into the query (classic SQL injection) and stored passwords in
plain text. This rewrite fixes both while keeping the same features:

- **SQLAlchemy ORM** — every query is parameterized; no string-built SQL.
- **Hashed passwords** — `werkzeug.security` (PBKDF2) for both admin and users.
- **Ownership checks** — e.g. cancelling a ticket now requires it to belong to
  the logged-in user (the original `cticket.php` didn't check this).
- **Server-side seat-conflict check** — booking now re-validates that selected
  seats aren't already taken, in addition to the client-side seat map.

## Running it in VS Code

1. **Unzip** this project and open the `busticket_flask` folder in VS Code
   (`File → Open Folder…`).
2. Install the **Python extension** (ms-python.python) if you don't have it —
   VS Code will usually prompt you automatically.
3. Open a terminal in VS Code (`` Ctrl+` `` / `` Cmd+` ``) and create a virtual
   environment:
   ```bash
   python -m venv venv
   ```
4. Activate it:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Select the interpreter: `Ctrl+Shift+P` → **Python: Select Interpreter** →
   choose the one inside `venv`.
7. Run it either way:
   - Press **F5** (uses the included `.vscode/launch.json` config), or
   - In the terminal: `python app.py`
8. Open **http://127.0.0.1:5000** in your browser.

The SQLite database (`busticket.db`) and demo data are created automatically
on first run — no manual DB setup needed.

## Running it from any terminal (no VS Code)

```bash
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**.

**Demo logins**
- Admin: `admin` / `admin123`
- User: `vinoth` / `password123` (also `sam` / `password123`, `kannan` / `password123`)

## AI features

Two lightweight, explainable AI features were added on top of the original app
(see `ai_recommender.py`):

- **Seat recommendation** — on the bus detail/seat-selection page, the app
  scores every available seat using a popularity signal learned from all past
  bookings (which seats travellers pick most often) plus a small window-seat
  comfort bonus, then highlights the top 3 seats as "AI recommended" on the
  seat map.
- **Peak demand prediction** — the admin **Reports** page (`/admin/reports`)
  now includes a 7-day demand forecast, built by aggregating historical
  bookings by day-of-week to predict which upcoming days are likely to be
  busiest, so admins can plan extra buses or staff.

Both features run entirely on data already in the database — no external AI
API or key is required.

## Project layout

```
app.py               Routes, auth, booking/payment/report logic, DB seeding
models.py             SQLAlchemy models (Admin, Register, Bus, BusTicket,
                       Feed, Payment, Rating, Notification)
ai_recommender.py     AI seat recommendation + peak demand prediction
templates/            Jinja2 templates (base.html + user/ + admin/)
static/css/style.css  Styling
requirements.txt
```

## Notes

- Payments are simulated — no real payment provider is called.
- The seat map is 36 seats per bus, matching the original `view1.php` layout.
- Swap `SQLALCHEMY_DATABASE_URI` in `app.py` for a Postgres/MySQL URL if you
  want a production database instead of SQLite.
