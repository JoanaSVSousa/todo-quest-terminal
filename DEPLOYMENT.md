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

Render Free web services block outbound SMTP traffic on ports `25`, `465`, and
`587`. If email sending times out on Render but works locally, use a paid Render
instance, an email provider with an HTTPS API, or an SMTP provider/port that is
reachable from Render.

Required for hosted deploys:

```env
HOST=0.0.0.0
PORT=10000
DATA_FILE=/var/data/lists.json
STORAGE_BACKEND=json
```

Many hosts provide `PORT` automatically.

## Supabase Storage

Supabase is useful when the app needs to be always online and available from
multiple devices, but you still want the code to stay close to the JSON version
you already understand.

Create this table in the Supabase SQL Editor:

```sql
create table if not exists public.app_state (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.app_state enable row level security;
```

Then set these environment variables locally or in Render:

```env
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-secret-or-service-role-key
SUPABASE_TABLE=app_state
SUPABASE_STATE_ID=main
```

Use the Supabase secret/service key only on the backend. Do not put it in
GitHub, browser JavaScript, mobile code, screenshots, or public docs.

To migrate local lists, deploy with Supabase enabled, open `/import`, paste the
contents of your local `data/lists.json`, and submit. After that, local and
hosted apps can share the same Supabase data if they use the same Supabase
environment variables.

## Render

Use a Web Service with:

```bash
python3 app.py
```

Set secrets/environment variables in the Render dashboard. If you keep JSON storage, attach a persistent disk and point `DATA_FILE` to that disk, for example `/var/data/lists.json`. Otherwise, use a database such as Postgres for production.

With Supabase storage, Render does not need a persistent disk for lists.

## Fly.io

Use `fly launch`, set secrets with `fly secrets set`, and mount a volume if you keep JSON storage. For a more scalable version, move tasks and sessions to a database.

## Production Upgrade Path

The current login is a single-user session login, good for a personal hosted version. For multiple users, add:

- user table
- password hashing
- per-user lists/tasks
- database-backed sessions
- managed database storage
