# TODO Quest Terminal

A terminal-style todo app for fast task capture, subtasks, details, priorities, a daily `TODAY` focus list, and optional daily email.

## Modes

### Personal Mode

Use this for your own hosted app.

- Login enabled
- Daily email can be enabled
- Data can stay in a local JSON file or move to Supabase while keeping the
  same JSON-shaped structure

Example config:

```env
AUTH_ENABLED=true
PLAYGROUND_MODE=false
APP_USER=your-username
APP_PASS=your-password
APP_URL=https://your-private-app-url.example.com/
EMAIL_ENABLED=true
STORAGE_BACKEND=json
```

For hosted personal use, `STORAGE_BACKEND=supabase` is the easiest way to keep
the same lists available across devices without needing a paid persistent disk.
See [`docs/SUPABASE.md`](docs/SUPABASE.md).

### Playground Mode

Use this for a public demo where recruiters or friends can explore the interface.

- Login disabled
- Email sending disabled
- Still uses JSON so the project remains easy to inspect and understand

Example config:

```env
AUTH_ENABLED=false
PLAYGROUND_MODE=true
EMAIL_ENABLED=false
```

## Run Locally

```bash
python3 app.py
```

Open `http://127.0.0.1:5000`.

To start from the public demo data:

```bash
cp data/lists.example.json data/lists.json
```

The real `data/lists.json` file is ignored by Git so local/private tasks stay private.

## Supabase Storage

The app can store the whole todo document in one Supabase Postgres row:

```env
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-secret-or-service-role-key
SUPABASE_TABLE=app_state
SUPABASE_STATE_ID=main
```

Keep the Supabase secret/service key only in `.env` or hosting secrets.
Never commit it or expose it in frontend JavaScript.

## Security Note

Do not commit `.env`. Use `.env.example` or `.env.playground.example` for public examples.

Do not commit `data/lists.json`. Use `data/lists.example.json` for demo content.

The current login is intentionally simple and single-user. For a production multi-user version, the next step is moving to hashed passwords, per-user data, and database-backed sessions.

## Code Tour

For a fuller explanation of how the pieces fit together, see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
