# [AI Smart Food Ordering and Diet Recommendation System for Telangana](https://web-production-d28ec.up.railway.app)


A production-oriented Flask web application that combines food delivery workflows with AI-driven diet and order-history recommendations for restaurants across Telangana.

## Features

- Session-based authentication with signup, login, logout, and SQLite persistence
- Telangana restaurant discovery with GPS-based nearest-first sorting and Leaflet/OpenStreetMap
- Swiggy-like restaurant cards, responsive filtering, and modern mobile-friendly UI
- Dynamic restaurant menus with 10+ seeded items each, calorie hints, and healthy badges
- Session cart, checkout flow, order confirmation, and test-mode Stripe-ready payment integration
- Goal-based diet planner for weight loss, muscle gain, balanced diet, and vegetarian preferences
- History-based recommendations driven by previous orders
- Dynamic food imagery via Spoonacular recipe search
- Admin panel for adding restaurants and menu items

## Stack

- Frontend: HTML, Jinja templates, CSS, JavaScript, Leaflet
- Backend: Flask, SQLAlchemy
- Database: SQLite
- Payments: Stripe test mode with demo fallback
- AI logic: Python rule-based recommendation engine

## Run locally

1. Create a virtual environment and activate it.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set keys as needed.
4. Start the app:

```bash
python run.py
```

5. Open `http://127.0.0.1:5000`.

The database is created automatically on first run and comes pre-seeded with Telangana restaurants and menus.

To refresh restaurant and menu images after adding a `SPOONACULAR_API_KEY`:

```bash
python refresh_images.py
```

## Environment variables

- `SECRET_KEY`
- `DATABASE_URL`
- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `SPOONACULAR_API_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `APP_BASE_URL`

## Deployment

### Render or Railway

- Set the start command to `gunicorn run:app`
- Add the environment variables from `.env.example`
- Use a managed database in production instead of SQLite
- For Render, a starter blueprint is included in `render.yaml`

### Render

1. Push this project to GitHub.
2. In Render, create a new Blueprint and select the repository.
3. Render will read `render.yaml` and create:
   - one Python web service
   - one managed PostgreSQL database
4. Set `APP_BASE_URL` to your Render service URL after the first deploy.
5. Optionally add `SPOONACULAR_API_KEY`, `STRIPE_SECRET_KEY`, and `STRIPE_PUBLISHABLE_KEY`.

Render’s Flask deployment docs currently recommend using Gunicorn for the start command.

### Railway

1. Push this project to GitHub.
2. In Railway, create a new project from the GitHub repo.
3. Add a PostgreSQL database service.
4. Set these variables on the web service:
   - `SECRET_KEY`
   - `DATABASE_URL`
   - `APP_BASE_URL`
   - `SPOONACULAR_API_KEY` if you want live food images
   - Stripe keys if you want live test checkout
5. Railway will detect the Python app and you can use `gunicorn run:app` as the start command.

### Netlify or Vercel

This project is currently rendered server-side with Flask. For Netlify/Vercel, either:

- deploy the Flask app as a single full-stack service, or
- split the frontend into a React/Vite client and keep this Flask backend as an API service

## Notes

- If Stripe keys are not configured, checkout falls back to a demo payment success path for evaluation.
- Food images are fetched from Spoonacular recipe search and cached locally in `app/image_cache.json`.
- If you deploy on Render or Railway, use PostgreSQL rather than SQLite because hosted filesystems are not a good primary database for production.
