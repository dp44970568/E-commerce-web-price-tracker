import streamlit as st
import pandas as pd
import datetime
import requests

from tracker.scrapers.flight_scraper import FlightScraper
from tracker.scrapers.ecommerce_scraper import EcommerceScraper
from tracker.storage.database import DatabaseManager
from tracker.mock_server.flight_fixtures import generate_flight_search_html

st.set_page_config(
    page_title="PriceTracker | Flights & E-Commerce",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

db = DatabaseManager()

# ----------------- SIDEBAR CONTROLS -----------------
with st.sidebar:
    st.title("⚙️ PriceTracker Hub")
    st.caption("Requests + BeautifulSoup + SQLite")

    # Metrics Summary
    tracked_f_list = db.get_tracked_flights()
    tracked_p_list = db.get_tracked_products()
    all_alerts = db.get_all_alerts()
    active_alerts = [a for a in all_alerts if a.get("active")]
    triggered_alerts = db.check_triggered_alerts()

    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Flights", len(tracked_f_list))
    col_m2.metric("Products", len(tracked_p_list))

    col_m3, col_m4 = st.columns(2)
    col_m3.metric("Alerts", len(active_alerts))
    col_m4.metric("Triggered", len(triggered_alerts), delta=len(triggered_alerts) if triggered_alerts else None, delta_color="inverse")

    st.write("---")
    st.subheader("🧪 Mock Server Testing")
    st.caption("Interact with the local mock travel & store endpoints.")
    mock_url = st.text_input("Mock Server Base URL", "http://127.0.0.1:8765")

    c1, c2 = st.columns(2)
    if c1.button("Drop Flight -$60", help="Simulate airline flash sale"):
        try:
            r = requests.get(f"{mock_url}/trigger-discount", timeout=2)
            st.success("Flight discount applied!")
        except Exception as e:
            st.error(f"Mock server not reachable: {e}")

    if c2.button("Drop Prod -$50", help="Simulate e-commerce flash sale"):
        try:
            r = requests.get(f"{mock_url}/trigger-product-discount", timeout=2)
            st.success("Product discount applied!")
        except Exception as e:
            st.error(f"Mock server not reachable: {e}")

    if st.button("Reset Mock Prices", help="Reset all prices to original levels"):
        try:
            requests.get(f"{mock_url}/reset-prices", timeout=2)
            st.info("Mock prices reset.")
        except Exception as e:
            st.error(f"Mock server not reachable: {e}")

# ----------------- MAIN INTERFACE -----------------
st.title("✈️ E-Commerce & Flight Web Price Tracker")
st.markdown("Automated price extraction, historical trend tracking, and threshold drop alerting.")

tabs = st.tabs(["🔍 Flight Tracker", "🛒 E-Commerce Tracker", "📈 Price History & Trends", "🔔 Price Drop Alerts"])

# ----------------- TAB 1: FLIGHT TRACKER -----------------
with tabs[0]:
    st.subheader("Flight Fare Extraction & Parsing")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        origin = st.selectbox("Origin Airport", ["JFK", "SFO", "DEL", "LHR", "DXB", "BOS", "ORD"], index=0)
    with col2:
        dest = st.selectbox("Destination Airport", ["LHR", "HND", "DXB", "CDG", "JFK", "MIA", "NRT"], index=0)
    with col3:
        currency = st.selectbox("Currency", ["USD", "EUR", "INR", "GBP"], index=0)

    custom_url = st.text_input(
        "Or enter a custom flight search URL to scrape (optional):",
        placeholder="e.g. http://127.0.0.1:8765/flights?from=JFK&to=LHR"
    )

    if st.button("Scrape & Track Flights", type="primary"):
        with st.spinner("Fetching page with Requests and parsing HTML with BeautifulSoup..."):
            with FlightScraper(db=db) as scraper:
                if custom_url.strip():
                    try:
                        flights = scraper.scrape_url(custom_url.strip())
                    except Exception as e:
                        st.error(f"Failed to scrape URL: {e}")
                        flights = []
                else:
                    html = generate_flight_search_html(origin, dest, currency)
                    flights = scraper.scrape_html_string(html)

            if flights:
                st.session_state["last_flights"] = flights
                st.success(f"Successfully extracted and tracked {len(flights)} flight options!")
            else:
                st.warning("No flight cards could be parsed from the provided source.")

    # Show stored or recent flight results
    flights_to_display = st.session_state.get("last_flights", [])
    if flights_to_display:
        data = [f.to_dict() for f in flights_to_display]
        df = pd.DataFrame(data)
        
        display_cols = ["airline", "flight_number", "origin", "destination", "departure_time", "arrival_time", "duration", "stops", "cabin_class", "price", "currency"]
        st.dataframe(df[display_cols], use_container_width=True)

        st.write("---")
        st.markdown("##### 🔔 Quick Flight Price Drop Alert")
        col_fa, col_fb = st.columns([2, 1])
        with col_fa:
            flight_options = [f"{f.airline} {f.flight_number} - {f.origin} to {f.destination} ({f.currency} {f.price:.2f})" for f in flights_to_display]
            alert_flight = st.selectbox("Select Flight to Track", flight_options)
        with col_fb:
            sel_idx = flight_options.index(alert_flight)
            target_flight = flights_to_display[sel_idx]
            target_p = st.number_input("Alert me when price drops below:", min_value=1.0, value=float(max(1.0, target_flight.price - 25.0)), step=5.0)

        if st.button("Save Flight Alert"):
            aid = db.create_alert(
                target_id=target_flight.flight_identifier,
                target_type="flight",
                target_name=f"{target_flight.airline} {target_flight.flight_number}",
                target_price=target_p,
                currency=target_flight.currency
            )
            st.success(f"✓ Alert #{aid} created for {target_flight.airline} {target_flight.flight_number} at {target_flight.currency} {target_p:.2f}!")

# ----------------- TAB 2: E-COMMERCE TRACKER -----------------
with tabs[1]:
    st.subheader("E-Commerce Product Price Extraction")
    
    scrape_mode = st.radio("Extraction Mode", ["Single Product Page", "Product Catalog / Search Results"], horizontal=True)

    if scrape_mode == "Single Product Page":
        col_pa, col_pb = st.columns([3, 1])
        with col_pa:
            prod_url = st.text_input(
                "Product URL:",
                value="http://127.0.0.1:8765/product/1",
                help="Supports online store pages or mock server endpoints."
            )
        with col_pb:
            store_name = st.text_input("Store Name:", "TechStore")

        # Quick preset buttons
        col_p1, col_p2 = st.columns(2)
        if col_p1.button("Use Mock TechStore Headphones"):
            prod_url = "http://127.0.0.1:8765/product/1"
            store_name = "TechStore"
        if col_p2.button("Use BooksToScrape Demo"):
            prod_url = "http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
            store_name = "BooksToScrape"

        if st.button("Extract Product Price", type="primary"):
            with st.spinner("Fetching product HTML and extracting pricing..."):
                with EcommerceScraper(db=db) as scraper:
                    try:
                        product = scraper.scrape_product(prod_url, site_name=store_name)
                        if product:
                            st.session_state["last_product"] = product
                            st.success("Product successfully parsed and tracked in database!")
                        else:
                            st.error("Could not parse product pricing information from this page.")
                    except Exception as e:
                        st.error(f"Error fetching product: {e}")

        prod = st.session_state.get("last_product", None)
        if prod:
            st.markdown(f"### {prod.title}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"{prod.currency} {prod.price:,.2f}")
            c2.metric("In Stock", "In Stock" if prod.in_stock else "Out of Stock")
            c3.metric("Rating", f"⭐ {prod.rating or 'N/A'}")
            c4.metric("Reviews", f"{prod.reviews_count or 'N/A'}")

            if prod.original_price and prod.original_price > prod.price:
                st.info(f"Was {prod.currency} {prod.original_price:,.2f} (Savings: {prod.discount_percentage}%)")

            st.write(f"**Identifier / SKU:** `{prod.product_identifier}` | **URL:** {prod.url}")

            # Quick Alert UI for Product
            st.write("---")
            st.markdown("##### 🔔 Quick Product Price Drop Alert")
            col_al1, col_al2 = st.columns([2, 1])
            with col_al1:
                st.write(f"Track: **{prod.title}**")
            with col_al2:
                default_target = float(max(1.0, prod.price - 20.0))
                prod_target_p = st.number_input("Target Price Threshold:", min_value=1.0, value=default_target, step=5.0)

            if st.button("Save Product Alert"):
                aid = db.create_alert(
                    target_id=prod.product_identifier,
                    target_type="product",
                    target_name=prod.title,
                    target_price=prod_target_p,
                    currency=prod.currency,
                )
                st.success(f"✓ Alert #{aid} created for '{prod.title}' at {prod.currency} {prod_target_p:.2f}!")

    else:
        # Catalog scraping mode
        cat_url = st.text_input("Catalog / Listing Page URL:", value="http://127.0.0.1:8765/products")
        cat_store = st.text_input("Store Name:", value="TechStore", key="cat_store")

        if st.button("Scrape Product Catalog", type="primary"):
            with st.spinner("Extracting listing items..."):
                with EcommerceScraper(db=db) as scraper:
                    try:
                        items = scraper.scrape_catalog(cat_url, site_name=cat_store)
                        if items:
                            st.session_state["last_catalog"] = items
                            st.success(f"Successfully extracted {len(items)} catalog items!")
                        else:
                            st.warning("No items found in catalog.")
                    except Exception as e:
                        st.error(f"Catalog scrape error: {e}")

        cat_items = st.session_state.get("last_catalog", [])
        if cat_items:
            df_cat = pd.DataFrame([it.to_dict() for it in cat_items])
            display_cols = ["title", "price", "currency", "in_stock", "product_identifier", "url"]
            st.dataframe(df_cat[[c for c in display_cols if c in df_cat.columns]], use_container_width=True)

# ----------------- TAB 3: PRICE HISTORY & TRENDS -----------------
with tabs[2]:
    st.subheader("Historical Price Trends & Volatility Analytics")
    
    analytics_view = st.radio("Analytics Target", ["Flights", "Products"], horizontal=True)

    if analytics_view == "Flights":
        tracked_flights = db.get_tracked_flights()
        if tracked_flights:
            df_tf = pd.DataFrame(tracked_flights)
            cols = ["airline", "flight_number", "origin", "destination", "latest_price", "lowest_price", "highest_price", "average_price", "data_points"]
            st.dataframe(df_tf[cols], use_container_width=True)

            st.write("---")
            flight_options = {f"{f['airline']} {f['flight_number']} ({f['identifier']})": f["identifier"] for f in tracked_flights}
            chosen_flight_label = st.selectbox("Select Flight to view price trend:", list(flight_options.keys()))
            chosen_fid = flight_options[chosen_flight_label]

            # Analytics KPIs
            analytics = db.get_trend_analytics(chosen_fid, target_type="flight")
            if analytics["data_points"] > 0:
                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("First Recorded", f"${analytics['first_price']:,.2f}")
                k2.metric("Latest Price", f"${analytics['latest_price']:,.2f}")
                k3.metric("Lowest Ever", f"${analytics['lowest_price']:,.2f}")
                k4.metric("Net Change", f"${analytics['price_change']:+,.2f}", f"{analytics['price_change_pct']:+.1f}%")
                k5.metric("Price Drops", analytics["drops_count"])

            hist = db.get_flight_history(chosen_fid)
            if hist:
                df_hist = pd.DataFrame(hist)
                df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])
                st.line_chart(df_hist.set_index("timestamp")["price"])

                # CSV Download
                csv_data = df_hist.to_csv(index=False).encode("utf-8")
                st.download_button("Download Price History (CSV)", csv_data, f"{chosen_fid}_history.csv", "text/csv")
        else:
            st.info("No flights recorded in database yet.")

    else:
        tracked_products = db.get_tracked_products()
        if tracked_products:
            df_tp = pd.DataFrame(tracked_products)
            cols = ["title", "latest_price", "currency", "lowest_price", "highest_price", "average_price", "data_points"]
            st.dataframe(df_tp[[c for c in cols if c in df_tp.columns]], use_container_width=True)

            st.write("---")
            prod_options = {f"{p['title']} ({p['identifier']})": p["identifier"] for p in tracked_products}
            chosen_prod_label = st.selectbox("Select Product to view price trend:", list(prod_options.keys()))
            chosen_pid = prod_options[chosen_prod_label]

            # Analytics KPIs
            analytics = db.get_trend_analytics(chosen_pid, target_type="product")
            if analytics["data_points"] > 0:
                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("First Recorded", f"${analytics['first_price']:,.2f}")
                k2.metric("Latest Price", f"${analytics['latest_price']:,.2f}")
                k3.metric("Lowest Ever", f"${analytics['lowest_price']:,.2f}")
                k4.metric("Net Change", f"${analytics['price_change']:+,.2f}", f"{analytics['price_change_pct']:+.1f}%")
                k5.metric("Price Drops", analytics["drops_count"])

            hist = db.get_product_history(chosen_pid)
            if hist:
                df_hist = pd.DataFrame(hist)
                df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])
                st.line_chart(df_hist.set_index("timestamp")["price"])

                csv_data = df_hist.to_csv(index=False).encode("utf-8")
                st.download_button("Download Product Price History (CSV)", csv_data, f"{chosen_pid}_history.csv", "text/csv")
        else:
            st.info("No products recorded in database yet.")

# ----------------- TAB 4: ALERTS MANAGEMENT -----------------
with tabs[3]:
    st.subheader("Price Drop Alerts Management")
    
    triggered = db.check_triggered_alerts()
    all_alerts = db.get_all_alerts()

    if triggered:
        st.error(f"🚨 {len(triggered)} Alert(s) Triggered!")
        for t in triggered:
            savings = max(0.0, t['target_price'] - t['latest_price'])
            st.warning(
                f"**{t['target_name']}** has dropped to **{t['currency']} {t['latest_price']:.2f}**! "
                f"(Threshold: {t['currency']} {t['target_price']:.2f} | Savings: **{t['currency']} {savings:.2f}**)"
            )
    else:
        st.success("All monitored flights and products are within expected price thresholds.")

    st.write("---")
    st.markdown("#### All Configured Alerts")
    
    if all_alerts:
        df_al = pd.DataFrame(all_alerts)
        st.dataframe(df_al[["id", "target_name", "target_type", "target_price", "currency", "active", "created_at"]], use_container_width=True)

        col_act1, col_act2 = st.columns(2)
        with col_act1:
            toggle_id = st.selectbox("Toggle Alert Active Status (by ID)", [a["id"] for a in all_alerts], key="toggle_sel")
            if st.button("Toggle Status"):
                db.toggle_alert(toggle_id)
                st.success(f"Toggled alert #{toggle_id} status.")
                st.rerun()

        with col_act2:
            del_id = st.selectbox("Delete Alert (by ID)", [a["id"] for a in all_alerts], key="del_sel")
            if st.button("Delete Alert", type="secondary"):
                db.delete_alert(del_id)
                st.success(f"Deleted alert #{del_id}.")
                st.rerun()
    else:
        st.info("No alerts configured yet. Set an alert from the Flight or E-Commerce tabs above.")
