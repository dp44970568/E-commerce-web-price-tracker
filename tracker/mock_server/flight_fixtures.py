import random

SAMPLE_AIRLINES = [
    {"name": "SkyLink Airways", "code": "SL"},
    {"name": "Nordic Air", "code": "NA"},
    {"name": "AeroGlobal", "code": "AG"},
    {"name": "Pacific Jet", "code": "PJ"},
    {"name": "SilverWing", "code": "SW"},
]

ROUTES = [
    {"from": "JFK", "from_city": "New York", "to": "LHR", "to_city": "London", "base_price": 540.0, "duration": "7h 15m"},
    {"from": "SFO", "from_city": "San Francisco", "to": "HND", "to_city": "Tokyo", "base_price": 890.0, "duration": "11h 20m"},
    {"from": "DEL", "from_city": "Delhi", "to": "DXB", "to_city": "Dubai", "base_price": 310.0, "duration": "3h 45m"},
    {"from": "LHR", "from_city": "London", "to": "CDG", "to_city": "Paris", "base_price": 120.0, "duration": "1h 25m"},
]


def generate_flight_search_html(
    origin: str = "JFK",
    destination: str = "LHR",
    currency: str = "USD",
    price_variance: float = 0.0,
) -> str:
    """
    Generates realistic HTML representing flight search results from a travel booking portal.
    Simulates real-world DOM structure with flight cards, times, stops, badges, and pricing.
    """
    currency_symbol = "$" if currency == "USD" else ("€" if currency == "EUR" else "₹")

    # Match or default route
    route = next(
        (r for r in ROUTES if r["from"] == origin and r["to"] == destination),
        {"from": origin, "from_city": origin, "to": destination, "to_city": destination, "base_price": 450.0, "duration": "6h 30m"}
    )

    flight_cards_html = []
    flight_options = [
        {"time_dep": "06:30 AM", "time_arr": "06:45 PM", "stops": 0, "stop_desc": "Nonstop", "price_mult": 1.15, "cabin": "Economy"},
        {"time_dep": "09:15 AM", "time_arr": "10:30 PM", "stops": 1, "stop_desc": "1 stop (1h 10m FRA)", "price_mult": 0.88, "cabin": "Economy"},
        {"time_dep": "01:45 PM", "time_arr": "02:00 AM", "stops": 0, "stop_desc": "Nonstop", "price_mult": 1.05, "cabin": "Premium Economy"},
        {"time_dep": "05:20 PM", "time_arr": "08:15 AM", "stops": 1, "stop_desc": "1 stop (2h 05m BOS)", "price_mult": 0.82, "cabin": "Economy"},
        {"time_dep": "10:30 PM", "time_arr": "11:45 AM", "stops": 0, "stop_desc": "Nonstop", "price_mult": 1.30, "cabin": "Business"},
    ]

    for i, opt in enumerate(flight_options):
        airline = SAMPLE_AIRLINES[i % len(SAMPLE_AIRLINES)]
        flight_no = f"{airline['code']} {100 + (i * 123) % 899}"
        calculated_price = round((route["base_price"] * opt["price_mult"]) + price_variance, 2)

        card = f"""
        <article class="flight-card" data-testid="flight-card-{i}">
            <div class="flight-main-info">
                <div class="airline-container">
                    <img class="airline-logo" src="/static/logos/{airline['code'].lower()}.png" alt="{airline['name']} Logo" />
                    <span class="airline-name">{airline['name']}</span>
                    <span class="flight-number">{flight_no}</span>
                </div>
                <div class="flight-schedule">
                    <div class="dep-info">
                        <span class="departure-time">{opt['time_dep']}</span>
                        <span class="origin-code">{route['from']}</span>
                    </div>
                    <div class="flight-route-visual">
                        <span class="duration">{route['duration']}</span>
                        <div class="route-line {'has-stop' if opt['stops'] > 0 else 'direct'}"></div>
                        <span class="stops-info">{opt['stop_desc']}</span>
                    </div>
                    <div class="arr-info">
                        <span class="arrival-time">{opt['time_arr']}</span>
                        <span class="destination-code">{route['to']}</span>
                    </div>
                </div>
                <div class="cabin-badge-wrap">
                    <span class="cabin-badge">{opt['cabin']}</span>
                </div>
            </div>
            <div class="flight-pricing-action">
                <span class="fare-type">Standard Fare</span>
                <div class="flight-price" data-price="{calculated_price}">
                    <span class="currency-symbol">{currency_symbol}</span>
                    <span class="amount">{calculated_price:,.2f}</span>
                </div>
                <a class="book-button" href="/book?flight={flight_no}&from={route['from']}&to={route['to']}">Select Flight</a>
            </div>
        </article>
        """
        flight_cards_html.append(card)

    cards_joined = "\n".join(flight_cards_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Flights from {route['from']} to {route['to']} | FlyTracker</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; }}
        .search-header {{ background: #0b2545; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .flight-card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 15px; padding: 18px 24px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #134074; }}
        .airline-container {{ display: flex; flex-direction: column; min-width: 130px; }}
        .airline-name {{ font-weight: bold; color: #1d2d44; }}
        .flight-number {{ font-size: 12px; color: #748cab; }}
        .flight-schedule {{ display: flex; align-items: center; gap: 24px; }}
        .departure-time, .arrival-time {{ font-size: 20px; font-weight: 600; color: #0d1b2a; display: block; }}
        .origin-code, .destination-code {{ font-size: 13px; color: #748cab; text-align: center; }}
        .flight-route-visual {{ text-align: center; min-width: 120px; }}
        .duration {{ font-size: 12px; color: #415a77; display: block; }}
        .route-line {{ height: 2px; background: #8d99ae; margin: 4px 0; position: relative; }}
        .stops-info {{ font-size: 11px; color: #6c757d; }}
        .flight-price {{ font-size: 24px; font-weight: bold; color: #1b4965; text-align: right; }}
        .book-button {{ display: inline-block; background: #0077b6; color: white; text-decoration: none; padding: 8px 16px; border-radius: 4px; font-weight: 600; margin-top: 6px; }}
        .book-button:hover {{ background: #023e8a; }}
        .cabin-badge {{ font-size: 11px; background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 12px; }}
    </style>
</head>
<body>
    <div class="search-header">
        <h1>Flight Deals: {route['from_city']} ({route['from']}) &rarr; {route['to_city']} ({route['to']})</h1>
        <p>Real-time fares extracted and updated continuously</p>
    </div>
    <main class="flight-results-container">
        {cards_joined}
    </main>
</body>
</html>
"""
