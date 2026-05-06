# Architecture

TODO Quest Terminal is intentionally small and framework-free. The goal is to
show a complete web app while keeping the code understandable for someone who
is still learning Python, JSON, and browser basics.

## Request Flow

1. The browser loads `templates/index.html`.
2. The frontend sends commands to `POST /command`.
3. `app.py` parses the command and calls functions from `storage.py`.
4. `storage.py` reads/writes `data/lists.json`.
5. The backend returns terminal text and the current prompt.
6. The frontend renders the output and adds clickable controls for `[ ]` and `{...}`.

## Main Files

| File | Responsibility |
| --- | --- |
| `app.py` | HTTP routes, login, command parsing, terminal responses |
| `storage.py` | JSON persistence, schema normalization, safe writes |
| `daily_email.py` | Today email rendering, SMTP sending, daily scheduler |
| `templates/index.html` | Terminal UI, command history, autocomplete, click handlers |
| `static/style.css` | Terminal visual design |
| `data/lists.example.json` | Safe public demo data |

## Modes

### Personal Mode

Personal mode enables login and can send the daily email.

```env
AUTH_ENABLED=true
PLAYGROUND_MODE=false
EMAIL_ENABLED=true
```

### Playground Mode

Playground mode is for public demos. It removes login friction and disables
email sending so visitors can explore safely.

```env
AUTH_ENABLED=false
PLAYGROUND_MODE=true
EMAIL_ENABLED=false
```

When `PLAYGROUND_MODE=true` and `data/lists.json` does not exist, the app seeds
it from `data/lists.example.json`.

## Command Model

The app treats the terminal as the main interface. Short commands map to storage
operations:

| Command | Meaning |
| --- | --- |
| `+ <name>` | Create a list at the root prompt |
| `<task>, <task>` | Add tasks inside the active list |
| `+ <ref> <text>` | Add subtasks to a task |
| `x <ref>` | Toggle a task/subtask |
| `- <ref>` | Delete a task/subtask |
| `details <ref> key=value` | Add optional metadata |
| `today <ref>` | Add/remove a Today focus item |

## Storage Shape

The JSON file has two root keys:

```json
{
  "daily": {},
  "lists": []
}
```

`daily` stores selected Today targets by internal ids. `lists` stores the visible
lists, tasks, subtasks, completion state, and optional details.

## Why JSON First?

JSON keeps the project easy to inspect, edit, and understand. It is not meant to
be the final production storage layer for multiple users. The next step would be
SQLite or Postgres with per-user ownership.

## Production Upgrade Path

For a real multi-user product:

- replace plain `APP_PASS` with hashed passwords
- store users and tasks in a database
- associate every list/task with a user id
- use persistent server-side sessions
- add rate limiting for login attempts
- move email sending to a worker or scheduled job
