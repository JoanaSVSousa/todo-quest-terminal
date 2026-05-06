# TODO Quest Terminal

A terminal-style todo app for fast task capture, subtasks, details, priorities, a daily `TODAY` focus list, and optional daily email.

## Modes

### Personal Mode

Use this for your own hosted app.

- Login enabled
- Daily email can be enabled
- Data stays in JSON while the project is still learning-friendly

Example config:

```env
AUTH_ENABLED=true
PLAYGROUND_MODE=false
APP_USER=your-username
APP_PASS=your-password
EMAIL_ENABLED=true
```

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

## Security Note

Do not commit `.env`. Use `.env.example` or `.env.playground.example` for public examples.

Do not commit `data/lists.json`. Use `data/lists.example.json` for demo content.

The current login is intentionally simple and single-user. For a production multi-user version, the next step is moving to hashed passwords, per-user data, and database-backed sessions.
