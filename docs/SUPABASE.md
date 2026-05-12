# Supabase Storage

This app can keep using the same JSON-shaped data model while storing it in
Supabase. The database stores one row with one `jsonb` column:

- `id`: the name of the saved app state, usually `main`
- `data`: the full TODO Quest JSON document
- `updated_at`: timestamp for when the row was created

This is intentionally simple. It lets the project stay readable while making
the private app usable from Render, Tailscale, a phone, or another computer.

## 1. Create The Table

Open Supabase, go to the SQL Editor, and run:

```sql
create table if not exists public.app_state (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.app_state enable row level security;
```

There are no public Row Level Security policies. The Python backend uses a
secret/service key from environment variables, so the browser never receives
direct database access.

## 2. Configure The App

In `.env` locally, or in Render's Environment settings, add:

```env
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-secret-or-service-role-key
SUPABASE_TABLE=app_state
SUPABASE_STATE_ID=main
```

Keep `AUTH_ENABLED=true` for the private app. Keep `PLAYGROUND_MODE=false` for
your real personal data.

## 3. Where To Find The Supabase Values

In the Supabase dashboard:

- `SUPABASE_URL`: Project Settings or Connect/Data API, project URL
- `SUPABASE_SERVICE_KEY`: Project Settings, API Keys, secret key or legacy
  service role key

The service/secret key must stay private. It belongs in `.env` or Render
secrets only, never in GitHub or frontend code.

## 4. Migrate Local Lists

Start from your local private file:

```text
data/lists.json
```

Then:

1. Deploy or run the app with `STORAGE_BACKEND=supabase`.
2. Open `/import`.
3. Paste the full contents of local `data/lists.json`.
4. Submit the import.
5. Open the app normally and run `lists`.

After import, every app instance using the same Supabase project and
`SUPABASE_STATE_ID=main` will read and write the same lists.

## 5. Local And Render Together

If local `.env` and Render use the same Supabase settings, both point to the
same online data. This means:

- changes made on your phone through Render appear locally
- changes made locally appear on Render
- you no longer depend on Render's filesystem for private data

For the public playground/demo, keep using JSON demo data instead of your
private Supabase project.
