"""JSON persistence layer for TODO Quest Terminal.

The app stores data in JSON on purpose: it keeps the project approachable while
still demonstrating basic persistence, schema normalization, and safe writes.
"""

import os
import json
from datetime import date
from pathlib import Path
from threading import RLock
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"

def load_local_env(path=ENV_FILE):
    """Load simple KEY=value settings before the app module is imported."""
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values

LOCAL_ENV = load_local_env()

def storage_config(key, default=""):
    """Read storage settings from environment variables or the local .env file."""
    return os.environ.get(key) or LOCAL_ENV.get(key, default)

DATA_FILE = Path(storage_config("DATA_FILE", "data/lists.json"))
EXAMPLE_DATA_FILE = Path("data/lists.example.json")
STORAGE_BACKEND = storage_config("STORAGE_BACKEND", "json").lower()

# Multiple browser requests can arrive at the same time. The lock and unique
# temp files prevent partial writes from corrupting lists.json.
DATA_LOCK = RLock()

def playground_enabled():
    """Return whether first-run demo data should be copied from the example file."""
    return storage_config("PLAYGROUND_MODE", "false").lower() in {"1", "true", "yes", "on"}

def supabase_enabled():
    """Return whether persistence should use Supabase instead of a JSON file."""
    return STORAGE_BACKEND == "supabase"

def supabase_config():
    """Read and validate Supabase connection settings from environment variables."""
    url = storage_config("SUPABASE_URL", "").rstrip("/")
    key = (
        storage_config("SUPABASE_SERVICE_KEY")
        or storage_config("SUPABASE_SECRET_KEY")
        or storage_config("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )
    table = storage_config("SUPABASE_TABLE", "app_state")
    state_id = storage_config("SUPABASE_STATE_ID", "main")

    missing = [
        name for name, value in {
            "SUPABASE_URL": url,
            "SUPABASE_SERVICE_KEY": key,
            "SUPABASE_TABLE": table,
            "SUPABASE_STATE_ID": state_id,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing Supabase config: "
            + ", ".join(missing)
            + ". Set them in .env or your hosting provider."
        )

    return url, key, table, state_id

def supabase_request(method, path, payload=None):
    """Send one authenticated request to Supabase's auto-generated REST API."""
    url, key, _table, _state_id = supabase_config()
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(
        f"{url}/rest/v1/{path}",
        data=body,
        method=method,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=minimal,resolution=merge-duplicates",
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else None
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Supabase: {error.reason}") from error

def normalize_item(item):
    """Normalize old/new task keys into the current storage schema."""
    subtasks = [
        {
            "id": subtask["id"],
            "text": subtask.get("text", subtask.get("texto", "")),
            "done": subtask.get("done", subtask.get("feito", False)),
            "details": subtask.get("details", {})
        }
        for subtask in item.get("subtasks", item.get("subtarefas", []))
    ]

    return {
        "id": item["id"],
        "text": item.get("text", item.get("texto", "")),
        "done": item.get("done", item.get("feito", False)),
        "date": item.get("date", item.get("data", date.today().isoformat())),
        "details": item.get("details", {}),
        "subtasks": subtasks
    }

def normalize_data(data):
    """Normalize the whole JSON document before the rest of the app uses it."""
    lists = data.get("lists", data.get("listas", []))
    return {
        "daily": data.get("daily", {}),
        "lists": [
            {
                "id": todo_list["id"],
                "name": todo_list.get("name", todo_list.get("nome", "")),
                "items": [
                    normalize_item(item)
                    for item in todo_list.get("items", todo_list.get("itens", []))
                ]
            }
            for todo_list in lists
        ]
    }

def initial_data():
    """Return the first document to store when persistence is empty."""
    if playground_enabled() and EXAMPLE_DATA_FILE.exists():
        with open(EXAMPLE_DATA_FILE) as f:
            return normalize_data(json.load(f))
    return {"daily": {}, "lists": []}

def load_file_data():
    """Load JSON data from disk, creating or normalizing the file when needed."""
    with DATA_LOCK:
        if not DATA_FILE.exists():
            DATA_FILE.parent.mkdir(exist_ok=True)
            save_file_data(initial_data())
        with open(DATA_FILE) as f:
            data = normalize_data(json.load(f))
        save_file_data(data)
        return data

def save_file_data(data):
    """Write JSON atomically so interrupted writes do not leave broken files."""
    with DATA_LOCK:
        DATA_FILE.parent.mkdir(exist_ok=True)
        temp_file = DATA_FILE.with_name(f"{DATA_FILE.name}.{uuid.uuid4().hex}.tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=4)
        temp_file.replace(DATA_FILE)

def load_supabase_data():
    """Load the app's JSON document from one Supabase row."""
    with DATA_LOCK:
        _url, _key, table, state_id = supabase_config()
        query = f"{quote(table)}?id=eq.{quote(state_id)}&select=data"
        rows = supabase_request("GET", query) or []

        if not rows:
            data = initial_data()
            save_supabase_data(data)
            return data

        data = normalize_data(rows[0].get("data", {}))
        save_supabase_data(data)
        return data

def save_supabase_data(data):
    """Upsert the app's JSON document into Supabase."""
    with DATA_LOCK:
        _url, _key, table, state_id = supabase_config()
        supabase_request(
            "POST",
            f"{quote(table)}?on_conflict=id",
            {"id": state_id, "data": normalize_data(data)},
        )

def load_data():
    """Load data from the configured storage backend."""
    if supabase_enabled():
        return load_supabase_data()
    return load_file_data()

def save_data(data):
    """Save data to the configured storage backend."""
    normalized = normalize_data(data)
    if supabase_enabled():
        save_supabase_data(normalized)
    else:
        save_file_data(normalized)

def get_lists():
    """Return all todo lists."""
    return load_data()["lists"]

def get_daily_focus(day):
    """Return Today focus targets for an ISO date."""
    return load_data().get("daily", {}).get(day, [])

def save_daily_focus(day, focus_items):
    """Replace Today focus targets for one ISO date."""
    data = load_data()
    data.setdefault("daily", {})[day] = focus_items
    save_data(data)

def toggle_daily_focus(day, target):
    """Add/remove a target from Today while enforcing the 3-item limit."""
    focus_items = get_daily_focus(day)
    normalized_target = {
        "list_id": target["list_id"],
        "item_id": target["item_id"],
        "subtask_id": target.get("subtask_id")
    }

    for index, focus_item in enumerate(focus_items):
        if focus_item == normalized_target:
            del focus_items[index]
            save_daily_focus(day, focus_items)
            return "removed"

    if len(focus_items) >= 3:
        return "full"

    focus_items.append(normalized_target)
    save_daily_focus(day, focus_items)
    return "added"

def create_list(name):
    """Create a list if its normalized id does not already exist."""
    data = load_data()
    list_id = name.lower().replace(" ", "-")

    if any(todo_list["id"] == list_id for todo_list in data["lists"]):
        return False

    data["lists"].append({
        "id": list_id,
        "name": name,
        "items": []
    })
    save_data(data)
    return True

def delete_list(list_id):
    """Delete one list by id."""
    data = load_data()
    original_count = len(data["lists"])
    data["lists"] = [
        todo_list for todo_list in data["lists"]
        if todo_list["id"] != list_id
    ]
    save_data(data)
    return len(data["lists"]) != original_count

def add_item(list_id, text):
    """Append a task to a list."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            todo_list["items"].append({
                "id": str(uuid.uuid4()),
                "text": text,
                "done": False,
                "date": date.today().isoformat(),
                "details": {},
                "subtasks": []
            })
            save_data(data)
            return True
    save_data(data)
    return False

def toggle_item(list_id, item_id):
    """Flip a task between open and done."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    item["done"] = not item["done"]
                    save_data(data)
                    return True
    save_data(data)
    return False

def add_subtask(list_id, item_id, text):
    """Append a subtask to a parent task."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    item.setdefault("subtasks", []).append({
                        "id": str(uuid.uuid4()),
                        "text": text,
                        "done": False,
                        "details": {}
                    })
                    save_data(data)
                    return True
    save_data(data)
    return False

def update_subtask_details(list_id, item_id, subtask_id, details):
    """Merge or remove optional detail fields on a subtask."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    for subtask in item.setdefault("subtasks", []):
                        if subtask["id"] == subtask_id:
                            current_details = subtask.setdefault("details", {})
                            for key, value in details.items():
                                if value == "":
                                    current_details.pop(key, None)
                                else:
                                    current_details[key] = value
                            save_data(data)
                            return True
    save_data(data)
    return False

def update_item_details(list_id, item_id, details):
    """Merge or remove optional detail fields on a task."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    current_details = item.setdefault("details", {})
                    for key, value in details.items():
                        if value == "":
                            current_details.pop(key, None)
                        else:
                            current_details[key] = value
                    save_data(data)
                    return True
    save_data(data)
    return False

def clear_subtask_details(list_id, item_id, subtask_id):
    """Remove all details from a subtask."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    for subtask in item.setdefault("subtasks", []):
                        if subtask["id"] == subtask_id:
                            subtask["details"] = {}
                            save_data(data)
                            return True
    save_data(data)
    return False

def clear_item_details(list_id, item_id):
    """Remove all details from a task."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    item["details"] = {}
                    save_data(data)
                    return True
    save_data(data)
    return False

def toggle_subtask(list_id, item_id, subtask_id):
    """Flip a subtask between open and done."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    for subtask in item.setdefault("subtasks", []):
                        if subtask["id"] == subtask_id:
                            subtask["done"] = not subtask["done"]
                            save_data(data)
                            return True
    save_data(data)
    return False

def delete_subtask(list_id, item_id, subtask_id):
    """Delete one subtask from a parent task."""
    data = load_data()
    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            for item in todo_list["items"]:
                if item["id"] == item_id:
                    subtasks = item.setdefault("subtasks", [])
                    original_count = len(subtasks)
                    item["subtasks"] = [
                        subtask for subtask in subtasks
                        if subtask["id"] != subtask_id
                    ]
                    save_data(data)
                    return len(item["subtasks"]) != original_count
    save_data(data)
    return False

def get_order_of_the_day():
    """Return incomplete tasks created today, grouped by list."""
    data = load_data()
    today = date.today().isoformat()
    result = []

    for todo_list in data["lists"]:
        tasks = [
            item for item in todo_list["items"]
            if not item["done"] and item["date"] == today
        ]
        if tasks:
            result.append({"list": todo_list["name"], "items": tasks})

    return result
def delete_item(list_id, item_id):
    """Delete one task and its subtasks."""
    data = load_data()

    for todo_list in data["lists"]:
        if todo_list["id"] == list_id:
            original_count = len(todo_list["items"])
            todo_list["items"] = [
                item for item in todo_list["items"]
                if item["id"] != item_id
            ]
            save_data(data)
            return len(todo_list["items"]) != original_count

    save_data(data)
    return False
