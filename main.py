import argparse
import sys
import time
import logging
from typing import Optional

# Reconfigure stdout/stderr on Windows to handle UTF-8 cleanly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from tracker.scrapers.flight_scraper import FlightScraper
from tracker.scrapers.ecommerce_scraper import EcommerceScraper
from tracker.storage.database import DatabaseManager
from tracker.mock_server.server import MockServerThread
from tracker.mock_server.flight_fixtures import generate_flight_search_html
from tracker.monitor import PriceMonitor

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def display_flights_table(flights, title="Extracted Flight Fares"):
    if not flights:
        console.print("[yellow]No flight results found.[/yellow]")
        return

    table = Table(title=title, show_lines=True)
    table.add_column("Airline", style="cyan", no_wrap=True)
    table.add_column("Flight No", style="bold magenta")
    table.add_column("Route", style="green")
    table.add_column("Dep & Arr Time", style="blue")
    table.add_column("Duration", style="white")
    table.add_column("Stops", style="yellow")
    table.add_column("Cabin", style="dim")
    table.add_column("Price", style="bold green", justify="right")

    for f in flights:
        table.add_row(
            f.airline,
            f.flight_number,
            f"{f.origin} ✈ {f.destination}",
            f"{f.departure_time} - {f.arrival_time}",
            f.duration,
            f.stop_details,
            f.cabin_class,
            f"{f.currency} {f.price:,.2f}",
        )

    console.print(table)


def display_products_table(products, title="Tracked Products"):
    if not products:
        console.print("[yellow]No product records found.[/yellow]")
        return

    table = Table(title=title, show_lines=True)
    table.add_column("Identifier", style="dim")
    table.add_column("Product Title", style="cyan")
    table.add_column("Latest Price", style="bold green", justify="right")
    table.add_column("Orig Price", style="dim", justify="right")
    table.add_column("Discount", style="magenta")
    table.add_column("Rating", style="yellow")
    table.add_column("Stock", style="white")

    for p in products:
        orig = f"{p.get('currency', '$')} {p['original_price']:,.2f}" if p.get("original_price") else "-"
        disc = f"-{p['discount_percentage']}%" if p.get("discount_percentage") else "-"
        stock = "[green]In Stock[/green]" if p.get("in_stock", True) else "[red]Out of Stock[/red]"
        rating = f"⭐ {p['rating']}" if p.get("rating") else "-"

        table.add_row(
            p["identifier"],
            p["title"][:45] + ("..." if len(p["title"]) > 45 else ""),
            f"{p['currency']} {p['latest_price']:,.2f}",
            orig,
            disc,
            rating,
            stock,
        )

    console.print(table)


def display_alerts_table(alerts, title="Configured Price Alerts"):
    if not alerts:
        console.print("[yellow]No price alerts configured.[/yellow]")
        return

    table = Table(title=title, show_lines=True)
    table.add_column("ID", style="bold magenta", justify="right")
    table.add_column("Type", style="cyan")
    table.add_column("Target Name", style="white")
    table.add_column("Target ID", style="dim")
    table.add_column("Threshold Price", style="bold yellow", justify="right")
    table.add_column("Status", style="bold")
    table.add_column("Created At", style="dim")

    for a in alerts:
        status_str = "[green]ACTIVE[/green]" if a.get("active") else "[red]INACTIVE[/red]"
        table.add_row(
            str(a["id"]),
            a.get("target_type", "").upper(),
            a.get("target_name", ""),
            a.get("target_id", ""),
            f"{a.get('currency', '$')} {a.get('target_price', 0):,.2f}",
            status_str,
            str(a.get("created_at", ""))[:19],
        )

    console.print(table)


def run_demo():
    """Runs a complete end-to-end demo demonstrating flight & product scraping, parsing, tracking, and alerts."""
    console.print(
        Panel.fit(
            "[bold cyan]E-Commerce & Flight Web Price Tracker Demo[/bold cyan]\n"
            "[white]Tech Stack: Python + Requests + BeautifulSoup + SQLite[/white]\n"
            "[green]Demonstrating HTTP retrieval, HTML parsing, price tracking, and drop alerting.[/green]"
        )
    )

    port = 8877
    server = MockServerThread(port=port)
    server.start()
    time.sleep(0.5)

    try:
        flight_url = f"http://127.0.0.1:{port}/flights?from=JFK&to=LHR"
        console.print(f"\n[bold]Step 1: Scraping Flight Search Results from:[/bold] [underline]{flight_url}[/underline]")
        
        with FlightScraper() as scraper:
            flights = scraper.scrape_url(flight_url)
            display_flights_table(flights, title="Round 1: Initial Flight Fares (JFK -> LHR)")

            # Set an alert on the cheapest flight
            cheapest = min(flights, key=lambda x: x.price)
            alert_target = cheapest.price - 20.0
            console.print(f"\n[bold]Step 2: Setting Price Alert:[/bold]")
            console.print(f"Targeting: [cyan]{cheapest.airline} {cheapest.flight_number}[/cyan] currently at [green]${cheapest.price:.2f}[/green]")
            console.print(f"Alert threshold set at: [bold yellow]${alert_target:.2f}[/bold yellow]")
            
            scraper.db.create_alert(
                target_id=cheapest.flight_identifier,
                target_type="flight",
                target_name=f"{cheapest.airline} {cheapest.flight_number}",
                target_price=alert_target,
                currency=cheapest.currency,
            )

        # Trigger simulated price reduction on the server
        console.print("\n[bold]Step 3: Simulating Airline Flash Sale (-$60 on all fares)...[/bold]")
        import requests
        requests.get(f"http://127.0.0.1:{port}/trigger-discount")
        time.sleep(0.5)

        # Re-scrape and verify price drop and alert firing
        console.print("\n[bold]Step 4: Re-scraping Flight Search to Detect Price Drop & Alert...[/bold]")
        with FlightScraper() as scraper:
            updated_flights = scraper.scrape_url(flight_url)
            display_flights_table(updated_flights, title="Round 2: Updated Fares after Flash Sale")

        # Step 5: E-commerce Product Page Scraping
        prod_url = f"http://127.0.0.1:{port}/product/1"
        console.print(f"\n[bold]Step 5: Scraping E-Commerce Product from:[/bold] [underline]{prod_url}[/underline]")
        with EcommerceScraper() as e_scraper:
            product = e_scraper.scrape_product(prod_url, site_name="TechStore")
            if product:
                console.print(Panel(
                    f"[bold]{product.title}[/bold]\n"
                    f"Current Price: [bold green]{product.currency} {product.price:.2f}[/bold green] "
                    f"(Was: [dim]{product.currency} {product.original_price or 0:.2f}[/dim])\n"
                    f"Rating: ⭐ {product.rating} ({product.reviews_count} reviews)\n"
                    f"In Stock: {'Yes' if product.in_stock else 'No'} | SKU: {product.sku}",
                    title="Parsed Product Data"
                ))

        # Step 6: Summary History from Database
        console.print("\n[bold]Step 6: Historical Database Summary:[/bold]")
        db = DatabaseManager()
        tracked_f = db.get_tracked_flights()
        
        hist_table = Table(title="Flight Price Tracking Analytics", show_lines=True)
        hist_table.add_column("Flight", style="magenta")
        hist_table.add_column("Route", style="cyan")
        hist_table.add_column("Latest Price", style="bold green")
        hist_table.add_column("Lowest Seen", style="green")
        hist_table.add_column("Highest Seen", style="red")
        hist_table.add_column("Avg Price", style="blue")
        hist_table.add_column("Samples", style="white")

        for f in tracked_f:
            hist_table.add_row(
                f"{f['airline']} {f['flight_number']}",
                f"{f['origin']} ✈ {f['destination']}",
                f"{f['currency']} {f['latest_price']:,.2f}",
                f"{f['currency']} {f['lowest_price']:,.2f}",
                f"{f['currency']} {f['highest_price']:,.2f}",
                f"{f['currency']} {f['average_price']:,.2f}",
                str(f["data_points"]),
            )
        console.print(hist_table)
        console.print("\n[bold green]✓ Demo completed successfully![/bold green]")

    finally:
        server.stop()


def main():
    parser = argparse.ArgumentParser(
        description="E-Commerce & Flight Web Price Tracker (Requests + BeautifulSoup)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # demo
    subparsers.add_parser("demo", help="Run full end-to-end flight & product tracking demo")

    # scrape-flights
    f_parser = subparsers.add_parser("scrape-flights", help="Scrape flight data from URL or mock")
    f_parser.add_argument("--url", type=str, help="Live web URL to scrape")
    f_parser.add_argument("--origin", type=str, default="JFK", help="Origin airport code (for mock)")
    f_parser.add_argument("--dest", type=str, default="LHR", help="Destination airport code (for mock)")
    f_parser.add_argument("--currency", type=str, default="USD", help="Currency code")

    # scrape-product
    p_parser = subparsers.add_parser("scrape-product", help="Scrape single e-commerce product from URL")
    p_parser.add_argument("url", type=str, help="Product URL")
    p_parser.add_argument("--site", type=str, default="WebStore", help="Store name")

    # scrape-catalog
    c_parser = subparsers.add_parser("scrape-catalog", help="Scrape e-commerce product catalog/listing page")
    c_parser.add_argument("url", type=str, help="Catalog/listing page URL")
    c_parser.add_argument("--site", type=str, default="WebStore", help="Store name")

    # history
    subparsers.add_parser("history", help="View price history and tracking statistics")

    # analytics
    ana_parser = subparsers.add_parser("analytics", help="View trend and volatility analytics for an item")
    ana_parser.add_argument("target_id", type=str, help="Flight or Product identifier")
    ana_parser.add_argument("--type", choices=["flight", "product"], default="flight", help="Target type")

    # alerts
    subparsers.add_parser("list-alerts", help="List all configured price alerts")

    alert_parser = subparsers.add_parser("set-alert", help="Set a target price alert")
    alert_parser.add_argument("target_id", type=str, help="Flight or Product identifier")
    alert_parser.add_argument("target_type", choices=["flight", "product"], help="Type of item")
    alert_parser.add_argument("target_name", type=str, help="Display name for item")
    alert_parser.add_argument("target_price", type=float, help="Target price threshold")
    alert_parser.add_argument("--currency", type=str, default="USD", help="Currency code")

    del_alert_parser = subparsers.add_parser("delete-alert", help="Delete a price alert by ID")
    del_alert_parser.add_argument("alert_id", type=int, help="Alert ID to delete")

    tog_alert_parser = subparsers.add_parser("toggle-alert", help="Toggle price alert active state")
    tog_alert_parser.add_argument("alert_id", type=int, help="Alert ID to toggle")

    subparsers.add_parser("check-alerts", help="Check active alerts against latest prices")

    # monitor
    mon_parser = subparsers.add_parser("monitor", help="Start automated continuous price monitoring")
    mon_parser.add_argument("--interval", type=int, default=60, help="Interval in seconds between cycles (default: 60)")
    mon_parser.add_argument("--iterations", type=int, default=None, help="Number of monitoring cycles (default: infinite)")
    mon_parser.add_argument("--flight-urls", nargs="*", default=[], help="Flight search URLs to track")
    mon_parser.add_argument("--product-urls", nargs="*", default=[], help="Product URLs to track")

    # export
    exp_parser = subparsers.add_parser("export", help="Export price records to CSV file")
    exp_parser.add_argument("output_file", type=str, help="Destination CSV file path")
    exp_parser.add_argument(
        "--type",
        choices=["flights", "products", "alerts", "flight_history", "product_history"],
        default="flights",
        help="Dataset to export",
    )
    exp_parser.add_argument("--id", type=str, default=None, help="Specific flight or product ID for history export")

    # serve-mock
    serve_parser = subparsers.add_parser("serve-mock", help="Start local mock travel & store web server")
    serve_parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")

    args = parser.parse_args()

    if args.command == "demo" or args.command is None:
        if args.command is None:
            # If no command provided, print help or run demo
            console.print("[dim]No command provided, running interactive demo. Run --help to see all commands.[/dim]\n")
        run_demo()

    elif args.command == "scrape-flights":
        with FlightScraper() as scraper:
            if args.url:
                flights = scraper.scrape_url(args.url)
            else:
                html = generate_flight_search_html(args.origin, args.dest, args.currency)
                flights = scraper.scrape_html_string(html)
            display_flights_table(flights, title=f"Flights: {args.origin} -> {args.dest}")

    elif args.command == "scrape-product":
        with EcommerceScraper() as scraper:
            product = scraper.scrape_product(args.url, site_name=args.site)
            if product:
                display_products_table([product.to_dict()])
            else:
                console.print("[red]Failed to extract product details from URL.[/red]")

    elif args.command == "scrape-catalog":
        with EcommerceScraper() as scraper:
            items = scraper.scrape_catalog(args.url, site_name=args.site)
            if items:
                display_products_table([item.to_dict() for item in items], title=f"Catalog Items: {args.site}")
            else:
                console.print("[red]No product items could be extracted from catalog URL.[/red]")

    elif args.command == "history":
        db = DatabaseManager()
        flights = db.get_tracked_flights()
        products = db.get_tracked_products()

        if flights:
            f_table = Table(title="Tracked Flights Summary", show_lines=True)
            f_table.add_column("Flight ID", style="dim")
            f_table.add_column("Flight", style="magenta")
            f_table.add_column("Route", style="cyan")
            f_table.add_column("Latest", style="bold green")
            f_table.add_column("Lowest", style="green")
            f_table.add_column("Highest", style="red")
            f_table.add_column("Avg", style="blue")
            f_table.add_column("Points", style="white")
            for f in flights:
                f_table.add_row(
                    f["identifier"],
                    f"{f['airline']} {f['flight_number']}",
                    f"{f['origin']} ✈ {f['destination']}",
                    f"{f['currency']} {f['latest_price']:,.2f}",
                    f"{f['currency']} {f['lowest_price']:,.2f}",
                    f"{f['currency']} {f['highest_price']:,.2f}",
                    f"{f['currency']} {f['average_price']:,.2f}",
                    str(f["data_points"]),
                )
            console.print(f_table)

        if products:
            display_products_table(products)

    elif args.command == "analytics":
        db = DatabaseManager()
        stats = db.get_trend_analytics(args.target_id, target_type=args.type)
        if stats["data_points"] == 0:
            console.print(f"[yellow]No price history records found for {args.type} '{args.target_id}'.[/yellow]")
        else:
            table = Table(title=f"Trend Analytics: {args.target_id} ({args.type.upper()})", show_lines=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="bold green")

            table.add_row("Data Points Recorded", str(stats["data_points"]))
            table.add_row("Initial Recorded Price", f"{stats['first_price']:,.2f}")
            table.add_row("Current Latest Price", f"{stats['latest_price']:,.2f}")
            table.add_row("Lowest Recorded Price", f"{stats['lowest_price']:,.2f}")
            table.add_row("Highest Recorded Price", f"{stats['highest_price']:,.2f}")
            color = "green" if stats["price_change"] <= 0 else "red"
            table.add_row(
                "Net Price Change",
                f"[{color}]{stats['price_change']:+,.2f} ({stats['price_change_pct']:+.1f}%)[/{color}]",
            )
            table.add_row("Total Price Drop Events", str(stats["drops_count"]))
            console.print(table)

    elif args.command == "list-alerts":
        db = DatabaseManager()
        alerts = db.get_all_alerts()
        display_alerts_table(alerts)

    elif args.command == "set-alert":
        db = DatabaseManager()
        aid = db.create_alert(
            target_id=args.target_id,
            target_type=args.target_type,
            target_name=args.target_name,
            target_price=args.target_price,
            currency=args.currency,
        )
        console.print(f"[green]✓ Alert #{aid} created for '{args.target_name}' at {args.currency} {args.target_price:.2f}![/green]")

    elif args.command == "delete-alert":
        db = DatabaseManager()
        ok = db.delete_alert(args.alert_id)
        if ok:
            console.print(f"[green]✓ Alert #{args.alert_id} deleted successfully.[/green]")
        else:
            console.print(f"[red]Alert #{args.alert_id} not found.[/red]")

    elif args.command == "toggle-alert":
        db = DatabaseManager()
        ok = db.toggle_alert(args.alert_id)
        if ok:
            console.print(f"[green]✓ Alert #{args.alert_id} active status toggled.[/green]")
        else:
            console.print(f"[red]Alert #{args.alert_id} not found.[/red]")

    elif args.command == "check-alerts":
        db = DatabaseManager()
        triggered = db.check_triggered_alerts()
        if not triggered:
            console.print("[green]No alerts currently triggered (all prices above threshold).[/green]")
        else:
            console.print(f"[bold yellow]Found {len(triggered)} triggered alert(s):[/bold yellow]")
            for a in triggered:
                console.print(f"  🔔 {a['target_name']}: Current {a['currency']} {a['latest_price']:.2f} <= Target {a['currency']} {a['target_price']:.2f}")

    elif args.command == "monitor":
        monitor = PriceMonitor()
        for u in args.flight_urls:
            monitor.add_flight_url(u)
        for u in args.product_urls:
            monitor.add_product_url(u)
        monitor.load_targets_from_database()

        console.print(
            f"[bold cyan]Starting PriceMonitor daemon...[/bold cyan]\n"
            f"Interval: {args.interval}s | Flight URLs: {len(monitor.flight_urls)} | Product URLs: {len(monitor.product_urls)}"
        )

        def on_cycle(iteration, summary):
            console.print(
                f"[dim]{summary['timestamp'][:19]}[/dim] [bold]Cycle #{iteration}:[/bold] "
                f"Checked {summary['flights_scraped']} flights, {summary['products_scraped']} products. "
                f"Alerts triggered: [bold {'yellow' if summary['alerts_triggered_count'] > 0 else 'green'}]{summary['alerts_triggered_count']}[/]"
            )

        try:
            monitor.run_loop(interval_seconds=args.interval, max_iterations=args.iterations, callback=on_cycle)
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring loop stopped.[/yellow]")

    elif args.command == "export":
        db = DatabaseManager()
        try:
            path = db.export_to_csv(data_type=args.type, output_path=args.output_file, item_id=args.id)
            console.print(f"[bold green]✓ Successfully exported {args.type} to: {path}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Export failed: {e}[/bold red]")

    elif args.command == "serve-mock":
        from tracker.mock_server.server import MockTravelHandler
        import socketserver
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("127.0.0.1", args.port), MockTravelHandler) as httpd:
            console.print(f"[bold green]Serving mock travel & product portal on http://127.0.0.1:{args.port}[/bold green]")
            console.print("Endpoints available:")
            console.print("  • Flights: http://127.0.0.1:{args.port}/flights?from=JFK&to=LHR")
            console.print("  • Product: http://127.0.0.1:{args.port}/product/1")
            console.print("  • Catalog: http://127.0.0.1:{args.port}/products")
            console.print("  • Trigger Discount: http://127.0.0.1:{args.port}/trigger-discount")
            console.print("Press Ctrl+C to stop.")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                console.print("\nServer stopped.")


if __name__ == "__main__":
    main()
