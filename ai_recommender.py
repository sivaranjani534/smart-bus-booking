"""
Lightweight AI helpers for the Bus Ticket Booking System.

Two features, both built from historical booking data already stored in
the database (no external services or API keys required):

1. Seat recommendation
   Scores every available seat using a popularity signal learned from past
   bookings (seats travellers pick most often) plus a small "window seat"
   comfort bonus, then returns the top-N seats. This is a simple, explainable
   recommender — the kind of rule + frequency scoring model that's a natural
   first AI feature to add to a booking app.

2. Peak demand prediction
   Aggregates historical bookings by day-of-week to forecast which of the
   next few calendar days are likely to see the highest booking demand,
   which the admin dashboard uses to plan extra buses/staff.
"""
from collections import Counter
from datetime import datetime, timedelta


def recommend_seats(all_tickets, seat_count, booked_seats, num_seats=3):
    """
    Recommend the best available seats on a bus.

    all_tickets   : iterable of ticket objects with a `.seat` string ("1,2,3")
                    — pulled from every past booking, across all buses, so the
                    model learns general seat preference patterns.
    seat_count    : total seats on this bus
    booked_seats  : set of seat numbers already booked/unavailable
    num_seats     : how many recommendations to return

    Returns a list of seat numbers, best first.
    """
    popularity = Counter()
    for t in all_tickets:
        for s in (t.seat or "").split(","):
            s = s.strip()
            if s.isdigit():
                popularity[int(s)] += 1

    available = [s for s in range(1, seat_count + 1) if s not in booked_seats]
    if not available:
        return []

    def score(seat):
        pop_score = popularity.get(seat, 0)
        # Seats at the start/end of a 4-seat row are treated as window seats
        # and get a small comfort bonus.
        window_bonus = 1 if seat % 4 in (1, 0) else 0
        return (pop_score * 2) + window_bonus

    ranked = sorted(available, key=score, reverse=True)
    return ranked[:num_seats]


def predict_peak_days(all_tickets, days_ahead=7):
    """
    Predict which of the next `days_ahead` calendar days are likely to see
    the highest booking demand, based on historical weekday booking frequency.

    all_tickets : iterable of ticket objects with a `.date` string ("YYYY-MM-DD")
    days_ahead  : how many upcoming days to forecast

    Returns a list of dicts, sorted by predicted demand (highest first):
        {"date": "2026-07-25", "weekday": "Saturday", "demand_score": 32.4}
    """
    weekday_counts = Counter()
    for t in all_tickets:
        if not t.date:
            continue
        try:
            d = datetime.strptime(t.date, "%Y-%m-%d")
        except ValueError:
            continue
        weekday_counts[d.weekday()] += 1

    total = sum(weekday_counts.values()) or 1
    today = datetime.utcnow().date()
    forecast = []
    for i in range(days_ahead):
        day = today + timedelta(days=i + 1)
        wd = day.weekday()
        score = round((weekday_counts.get(wd, 0) / total) * 100, 1)
        forecast.append({
            "date": day.strftime("%Y-%m-%d"),
            "weekday": day.strftime("%A"),
            "demand_score": score,
        })
    forecast.sort(key=lambda x: x["demand_score"], reverse=True)
    return forecast
