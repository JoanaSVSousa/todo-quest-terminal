# Deployment Notes

## Local

```bash
python3 app.py
```

Open `http://127.0.0.1:5000`.

## Environment

Keep real values in `.env` locally and in your hosting provider's secret/environment settings.
Do not commit `.env`.

Required for login:

```env
AUTH_ENABLED=true
APP_USER=your-username
APP_PASS=your-password
APP_URL=https://your-private-app-url.example.com/
```

For a public demo/playground:

```env
AUTH_ENABLED=false
PLAYGROUND_MODE=true
EMAIL_ENABLED=false
```

Use `data/lists.example.json` as public demo data. Do not deploy personal `data/lists.json`.

Required for daily email:

```env
EMAIL_ENABLED=true
EMAIL_TIME=09:00
EMAIL_TIMEZONE=Europe/Lisbon
EMAIL_HOST=mail.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_USER=you@example.com
EMAIL_PASS=your-email-password
EMAIL_TO=recipient@example.com
APP_URL=https://your-private-app-url.example.com/
```

Required for hosted deploys:

```env
HOST=0.0.0.0
PORT=10000
```

Many hosts provide `PORT` automatically.

## Render

Use a Web Service with:

```bash
python3 app.py
```

Set secrets/environment variables in the Render dashboard. If you keep JSON storage, attach a persistent disk mounted to the app's `data` directory. Otherwise, use a database such as Postgres for production.

## Fly.io

Use `fly launch`, set secrets with `fly secrets set`, and mount a volume if you keep JSON storage. For a more scalable version, move tasks and sessions to a database.

## Production Upgrade Path

The current login is a single-user session login, good for a personal hosted version. For multiple users, add:

- user table
- password hashing
- per-user lists/tasks
- database-backed sessions
- managed database storage
