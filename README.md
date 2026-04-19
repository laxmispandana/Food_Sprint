# FoodSprint

FoodSprint is a Flask-based food ordering demo focused on Telangana restaurant discovery. The current app combines a seeded restaurant catalog, nearby search on OpenStreetMap, UPI QR checkout, diet-aware recommendations, and lightweight admin/staff operations tooling.

## Current features

- Customer signup, login, logout, and session-based cart persistence
- Seeded Telangana restaurant catalog with 11 restaurants and 110 menu items across Hyderabad, Warangal, Karimnagar, Nizamabad, and Khammam
- Location-aware nearby discovery using browser geolocation, Leaflet maps, OpenStreetMap tiles, and Overpass API results
- Hybrid nearby search that blends FoodSprint catalog entries with live OSM places
- Filtering by city, keyword, distance, rating, restaurant type, and veg/non-veg preference
- Restaurant detail pages with menu browsing, quantity controls, and customer reviews
- Cart and mini-cart flows backed by JSON endpoints for a more dynamic UI
- Checkout with admin-configured UPI ID, QR generation, manual payment confirmation, and order creation
- Order tracking with a status timeline from `PLACED` to `DELIVERED`
- Rule-based recommendations for weight loss, muscle gain, balanced diet, vegetarian goals, and repeat-order suggestions
- Single-admin dashboard for UPI settings, staff account creation, order visibility, and review monitoring
- Staff dashboard for moving orders through fulfillment stages one step at a time
- Automatic database creation and demo seeding on first run

## Tech stack

- Backend: Flask, SQLAlchemy, Flask-Migrate, Jinja2
- Frontend: HTML templates, CSS, vanilla JavaScript, Leaflet, Leaflet.markercluster
- Database: SQLite by default, PostgreSQL supported through `DATABASE_URL`
- Payments: Demo UPI QR flow with SVG QR generation via `qrcode`
- Discovery: OpenStreetMap + Overpass API
- Deployment: Gunicorn, Docker, Docker Compose, Render, Railway

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Start the app:

```bash
python run.py
```

5. Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

The app creates the database automatically on first boot and seeds demo restaurants, menu items, one admin account, and one staff account.

## Demo accounts

- Admin: `admin@foodsprint.com` / `admin123`
- Staff: `staff@foodsprint.com` / `staff123`
- Customer: create an account from the signup page

## Environment variables

The current Flask app mainly relies on these settings:

- `SECRET_KEY`
- `DATABASE_URL`
- `FOODSPRINT_UPI_ID`
- `FOODSPRINT_UPI_NAME`
- `STAFF_LIMIT`
- `FLASK_ENV`
- `DEMO_RESET_DB`

Notes:

- `DATABASE_URL` defaults to `sqlite:///food_ordering.db` for local development.
- `DEMO_RESET_DB=true` resets the local SQLite demo database on startup.
- Some repo files still contain older placeholders such as `REDIS_URL`, `SPOONACULAR_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `APP_BASE_URL`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`. Those are not required for the current checkout and discovery flow described above.

## Docker

To run the full local stack with PostgreSQL:

```bash
docker compose up --build
```

This starts:

- the Flask web app
- PostgreSQL 16
- Redis 7

## Deployment

### Render

- A starter blueprint is included in [`render.yaml`](render.yaml).
- Use the Gunicorn start command: `gunicorn --worker-class gthread --threads 4 --workers 1 run:app`
- Prefer PostgreSQL in production instead of SQLite.
- The Render manifest still includes some legacy environment variable placeholders from earlier iterations of the project.

### Railway

- Railway can run the same Gunicorn command used above.
- Attach a PostgreSQL database and set `DATABASE_URL`, `SECRET_KEY`, and your UPI configuration.

## Current app notes

- The active customer checkout path is the UPI QR flow shown in the UI.
- Payment confirmation is demo-friendly: the user scans the QR and then clicks "I have paid" to mark the payment as successful.
- The nearby discovery experience falls back to seeded catalog results if geolocation is denied or Overpass is unavailable.
- GitHub Actions is configured to compile the app, run `pytest`, and build the Docker image on CI.
