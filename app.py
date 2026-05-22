"""HTTP entry point and command parser for TODO Quest Terminal.

The project intentionally uses Python's standard library instead of a web
framework. That keeps the app readable for beginners while still showing the
core moving parts of a web application: routing, authentication, JSON APIs,
command parsing, and HTML serving.
"""

import json
import os
import re
import secrets
import shlex
import html as html_tools
from http import cookies
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote

from daily_email import get_today_items, load_env, send_today_email, start_daily_email_scheduler
from storage import (
    DATA_FILE,
    add_item,
    add_subtask,
    clear_item_details,
    clear_subtask_details,
    create_list,
    delete_list,
    delete_item,
    delete_subtask,
    get_daily_focus,
    get_lists,
    get_order_of_the_day,
    load_data,
    normalize_data,
    save_daily_focus,
    save_data,
    toggle_item,
    toggle_subtask,
    toggle_daily_focus,
    update_item_details,
    update_subtask_details,
)

BASE_DIR = Path(__file__).parent

# Active list state is process-local. That is enough for the single-user
# personal/playground version, and it keeps the command prompt simple.
ACTIVE_LIST_ID = None

# In-memory sessions are intentionally lightweight. For a real multi-user
# product these would move to a database or signed server-side session store.
SESSIONS = set()
ENV = load_env()


HELP_TEXT = """Commands:
lists                  show all lists
+ <name>               create a list
use <list|n>           enter a list
<task>, <task>         add tasks inside the active list
x <ref>                toggle a task or subtask
- <ref|list>           delete a task/subtask, or a list outside a list
details <ref>          show or edit task/subtask details
details help           show detail fields
show                   show the active list
out                    leave the active list
clear                  clear the terminal
today                  show today's open tasks
today <ref>            add/remove a daily focus item
today - <n>            remove a Today item by its Today number
email preview          preview the daily email
email send             send the daily email now

Examples:
+ home
use home
wash dishes, take trash out
+ 1 buy soap, rinse sponge
details 1 due=2026-05-12 who=Joana
details 1.1 priority=III
today 1.1
today - 1
email preview
x 1.1
- 1.1
out
- home"""


DETAIL_HELP_TEXT = """Detail fields:
due                    date or day
who                    person responsible
location               place
repeat                 repeat interval
recurring              yes/no
description            free text
priority               0-3 or I/II/III

Autocomplete:
Tab                    insert the selected field
Left/Right             move through suggestions

Examples:
details 1.1 due=2026-05-12 who=Joana
details 1.1 priority=III
details 1.1 desc=limoeiro e anespereira
details 1.1 -repeat
details 1.1 clear"""


def get_config(key, default=""):
    """Read configuration from environment variables, falling back to .env."""
    return os.environ.get(key) or ENV.get(key, default)


def auth_enabled():
    """Return whether the single-user login screen should protect the app."""
    return get_config("AUTH_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def playground_enabled():
    """Return whether public-demo safety rules should be applied."""
    return get_config("PLAYGROUND_MODE", "false").lower() in {"1", "true", "yes", "on"}


def app_host():
    return get_config("HOST", "127.0.0.1")


def app_port():
    return int(get_config("PORT", "5000"))


def login_page(error=""):
    """Render the terminal-themed login screen used in personal mode."""
    error_html = f'<div class="error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TODO QUEST LOGIN</title>
    <link rel="stylesheet" href="static/style.css">
    <style>
        #terminal {{
            max-width: 520px;
            min-height: auto;
            margin-top: 12vh;
        }}
        form {{
            display: grid;
            gap: 12px;
            margin-top: 18px;
        }}
        label {{
            display: grid;
            gap: 6px;
        }}
        input {{
            background: transparent;
            border: 1px solid #00ff66;
            color: #00ff66;
            font: inherit;
            padding: 10px;
            outline: none;
            text-shadow: inherit;
        }}
        button {{
            background: #00ff66;
            border: 0;
            color: #001a08;
            cursor: pointer;
            font: inherit;
            padding: 10px;
            text-shadow: none;
        }}
        .error {{
            color: #ff6b6b;
            text-shadow: 0 0 6px #ff6b6b;
            margin-top: 12px;
        }}
    </style>
</head>
<body>
<div id="terminal">
    <div>TODO QUEST SYSTEM v2.0</div>
    <div>AUTH REQUIRED</div>
    {error_html}
    <form method="post" action="/login">
        <label>
            user
            <input name="username" autofocus autocomplete="username">
        </label>
        <label>
            password
            <input name="password" type="password" autocomplete="current-password">
        </label>
        <button type="submit">login</button>
    </form>
</div>
</body>
</html>"""


def import_page(message=""):
    """Render a private JSON import/export page for hosted deployments."""
    try:
        current_data = html_tools.escape(json.dumps(load_data(), indent=4, ensure_ascii=False))
    except (OSError, json.JSONDecodeError, RuntimeError) as error:
        current_data = ""
        message = (
            f"Could not read the configured storage. "
            f"If you use JSON, check DATA_FILE={DATA_FILE}. "
            f"If you use Supabase, check the Supabase environment variables. "
            f"Error: {error}"
        )
    message_html = f'<div class="notice">{html_tools.escape(message)}</div>' if message else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <title>TODO QUEST IMPORT</title>
    <link rel="stylesheet" href="static/style.css">
    <style>
        #terminal {{
            max-width: 900px;
            min-height: auto;
        }}
        form {{
            display: grid;
            gap: 12px;
            margin-top: 16px;
        }}
        textarea {{
            width: 100%;
            min-height: 320px;
            background: #000803;
            border: 1px solid #00ff66;
            color: #00ff66;
            font: inherit;
            padding: 12px;
            text-shadow: inherit;
        }}
        button,
        .link-button {{
            background: #00ff66;
            border: 0;
            color: #001a08;
            cursor: pointer;
            display: inline-block;
            font: inherit;
            padding: 10px 12px;
            text-decoration: none;
            text-shadow: none;
        }}
        .notice {{
            color: #9dffbf;
            margin-top: 12px;
        }}
        .actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 14px;
        }}
    </style>
</head>
<body>
<div id="terminal">
    <div>TODO QUEST SYSTEM v2.0</div>
    <div>DATA IMPORT / EXPORT</div>
    {message_html}
    <div class="actions">
        <a class="link-button" href="/">Back to app</a>
        <a class="link-button" href="/export">Download JSON</a>
    </div>
    <form method="post" action="/import">
        <label for="data-json">Paste lists.json here</label>
        <textarea id="data-json" name="data_json" spellcheck="false">{current_data}</textarea>
        <button type="submit">Import JSON</button>
    </form>
</div>
</body>
</html>"""


def normalize_id(text):
    """Create a stable id from a user-facing list name."""
    return text.strip().lower().replace(" ", "-")


def find_list(list_ref):
    """Find a list by number, id, or normalized display name."""
    todo_lists = get_lists()
    list_ref = list_ref.strip().rstrip(".")

    if list_ref.isdigit():
        index = int(list_ref) - 1
        if 0 <= index < len(todo_lists):
            return todo_lists[index]

    wanted = normalize_id(list_ref)
    for todo_list in todo_lists:
        if todo_list["id"] == wanted or normalize_id(todo_list["name"]) == wanted:
            return todo_list
    return None


def get_active_list():
    """Return the list currently selected in the terminal prompt."""
    if not ACTIVE_LIST_ID:
        return None
    return find_list(ACTIVE_LIST_ID)


def set_active_list(todo_list):
    """Update the terminal prompt context after use/out/list creation."""
    global ACTIVE_LIST_ID
    ACTIVE_LIST_ID = todo_list["id"] if todo_list else None


def get_prompt():
    """Build the prompt text shown before the command input."""
    active_list = get_active_list()
    if active_list:
        return f"[{active_list['name']}] >"
    return ">"


def find_item(lista, item_number):
    """Resolve a 1-based task number inside a list."""
    item_number = item_number.strip().rstrip(".")
    try:
        index = int(item_number) - 1
    except ValueError:
        return None

    if index < 0 or index >= len(lista["items"]):
        return None

    return lista["items"][index]


def find_subtask(item, subtask_number):
    """Resolve a 1-based subtask number inside a task."""
    subtask_number = subtask_number.strip().rstrip(".")
    try:
        index = int(subtask_number) - 1
    except ValueError:
        return None

    subtasks = item.setdefault("subtasks", [])
    if index < 0 or index >= len(subtasks):
        return None

    return subtasks[index]


def split_reference(reference):
    """Split references like 2 or 2.3 into task/subtask parts."""
    reference = reference.strip().rstrip(".")
    chunks = reference.split(".")
    if len(chunks) == 1:
        return chunks[0], None
    if len(chunks) == 2:
        return chunks[0], chunks[1]
    return None, None


def resolve_reference(todo_list, reference):
    """Return the task and optional subtask matching a terminal reference."""
    item_number, subtask_number = split_reference(reference)
    if not item_number:
        return None, None

    item = find_item(todo_list, item_number)
    if not item:
        return None, None

    if subtask_number is None:
        return item, None

    subtask = find_subtask(item, subtask_number)
    if not subtask:
        return item, None

    return item, subtask


def can_resolve_item_reference(todo_list, reference):
    """Check whether a reference points to a parent task, not a subtask."""
    item_number, subtask_number = split_reference(reference)
    return bool(item_number) and subtask_number is None and find_item(todo_list, item_number)


def split_entries(text):
    """Split comma-separated user input into task/subtask entries."""
    return [entry.strip() for entry in text.split(",") if entry.strip()]


DETAIL_FIELDS = {
    "day": "due",
    "dia": "due",
    "date": "due",
    "due": "due",
    "when": "due",
    "quando": "due",
    "who": "who",
    "quem": "who",
    "owner": "who",
    "assignee": "who",
    "description": "description",
    "desc": "description",
    "descricao": "description",
    "descrição": "description",
    "where": "location",
    "place": "location",
    "location": "location",
    "local": "location",
    "repeat": "repeat",
    "repeats": "repeat",
    "repete": "repeat",
    "recurring": "recurring",
    "recorrente": "recurring",
    "p": "priority",
    "prio": "priority",
    "priority": "priority",
    "prioridade": "priority",
}


DETAIL_DISPLAY_ORDER = ["priority", "due", "who", "location", "repeat", "recurring", "description"]


def looks_like_reference(value):
    """Detect terminal references such as 1, 2.3, or 15.1."""
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", value))


def normalize_reference(reference):
    """Normalize optional trailing dots from references like 1. or 2.3."""
    return reference.strip().rstrip(".")


def parse_details(tokens):
    """Parse detail tokens such as due=tomorrow, -repeat, or desc=free text.

    The parser accepts simple key=value tokens and lets description-like values
    continue across later tokens until another key appears.
    """
    details = {}
    current_key = None
    for token in tokens:
        if token.startswith("-") and len(token) > 1:
            normalized_key = DETAIL_FIELDS.get(token[1:].strip().lower())
            if normalized_key:
                details[normalized_key] = ""
            current_key = None
            continue

        if "=" not in token:
            if current_key and details[current_key]:
                details[current_key] += f" {token.strip()}"
            continue
        key, value = token.split("=", 1)
        normalized_key = DETAIL_FIELDS.get(key.strip().lower())
        if normalized_key:
            normalized_value = normalize_detail_value(normalized_key, value.strip())
            if normalized_value is not None:
                details[normalized_key] = normalized_value
                current_key = normalized_key
            else:
                current_key = None
        else:
            current_key = None
    return details


def normalize_detail_value(key, value):
    """Validate and normalize detail values with special handling for priority."""
    if key != "priority" or value == "":
        return value

    roman_priorities = {"I", "II", "III"}
    upper_value = value.upper()
    if value in {"0", "1", "2", "3"}:
        return value
    if upper_value in roman_priorities:
        return upper_value
    return None


def format_priority_marker(details):
    """Render compact priority markers beside tasks, for example [III]."""
    priority = details.get("priority")
    if not priority:
        return ""
    return f" [{priority}]"


def format_task_details(task):
    """Format the detail view for a task or subtask."""
    details = task.get("details", {})
    lines = [f"{task['text']}"]

    if not details:
        lines.append("No details yet.")
        lines.append("Example: details 1 due=2026-05-12 who=Joana repeat=weekly place=Garden")
        return "\n".join(lines)

    for key in DETAIL_DISPLAY_ORDER:
        if details.get(key):
            lines.append(f"{key}: {details[key]}")

    return "\n".join(lines)


def format_list(todo_list):
    """Render a list as terminal text with numbered tasks and subtasks."""
    if not todo_list["items"]:
        return f"{todo_list['name']}: no tasks."

    lines = [f"{todo_list['name']}"]
    for item_index, item in enumerate(todo_list["items"], start=1):
        status = "x" if item.get("done") else " "
        details = item.get("details", {})
        priority_marker = format_priority_marker(details)
        details_marker = " {...}" if details else ""
        lines.append(f"{item_index}. [{status}] {item['text']}{priority_marker}{details_marker}")

        for sub_index, subtask in enumerate(item.get("subtasks", []), start=1):
            sub_status = "x" if subtask.get("done") else " "
            details = subtask.get("details", {})
            priority_marker = format_priority_marker(details)
            details_marker = " {...}" if details else ""
            lines.append(f"   {item_index}.{sub_index} [{sub_status}] {subtask['text']}{priority_marker}{details_marker}")

    return "\n".join(lines)


def find_target_labels(target):
    """Convert stored Today target ids back into display labels and refs."""
    for list_index, todo_list in enumerate(get_lists(), start=1):
        if todo_list["id"] != target["list_id"]:
            continue

        for item_index, item in enumerate(todo_list["items"], start=1):
            if item["id"] != target["item_id"]:
                continue

            if target.get("subtask_id"):
                for sub_index, subtask in enumerate(item.get("subtasks", []), start=1):
                    if subtask["id"] == target["subtask_id"]:
                        return {
                            "list": todo_list["name"],
                            "ref": f"{item_index}.{sub_index}",
                            "text": subtask["text"],
                            "done": subtask.get("done", False)
                        }
                return None

            return {
                "list": todo_list["name"],
                "ref": str(item_index),
                "text": item["text"],
                "done": item.get("done", False)
            }

    return None


def get_today_focus_items():
    """Return valid Today focus items and remove stale deleted references."""
    today = date.today().isoformat()
    focus_items = []
    valid_targets = []

    for target in get_daily_focus(today):
        label = find_target_labels(target)
        if label:
            valid_targets.append(target)
            focus_items.append(label)

    if len(valid_targets) != len(get_daily_focus(today)):
        save_daily_focus(today, valid_targets)

    return focus_items


def get_active_list_payload():
    """Return active-list refs for frontend autocomplete."""
    active_list = get_active_list()
    if not active_list:
        return {"active": None, "items": []}

    items = []
    for item_index, item in enumerate(active_list["items"], start=1):
        items.append({
            "ref": str(item_index),
            "text": item["text"],
            "done": item.get("done", False),
            "hasDetails": bool(item.get("details", {}))
        })

        for sub_index, subtask in enumerate(item.get("subtasks", []), start=1):
            items.append({
                "ref": f"{item_index}.{sub_index}",
                "text": subtask["text"],
                "done": subtask.get("done", False),
                "hasDetails": bool(subtask.get("details", {}))
            })

    return {
        "active": {
            "id": active_list["id"],
            "name": active_list["name"]
        },
        "items": items
    }


def format_today_focus():
    """Render the Today panel as terminal text."""
    focus_items = get_today_focus_items()
    lines = [f"TODAY {len(focus_items)}/3"]

    if not focus_items:
        lines.append("No focus items yet. Use: today <ref>")
        return "\n".join(lines)

    for index, item in enumerate(focus_items, start=1):
        status = "x" if item["done"] else " "
        lines.append(f"{index}. [{status}] {item['list']} {item['ref']} {item['text']}")

    for index in range(len(focus_items) + 1, 4):
        lines.append(f"{index}. [ ] ...")

    return "\n".join(lines)


def remove_today_focus_slot(slot_ref):
    """Remove a Today focus item by the number shown in the Today panel."""
    slot_ref = slot_ref.strip().rstrip(".")
    if not slot_ref.isdigit():
        return "Use: today - <n>"

    today = date.today().isoformat()
    focus_items = get_daily_focus(today)
    slot_index = int(slot_ref) - 1
    if slot_index < 0 or slot_index >= len(focus_items):
        return "Today item not found."

    del focus_items[slot_index]
    save_daily_focus(today, focus_items)
    return format_today_focus()


def format_email_preview():
    """Render the email preview in terminal text before sending."""
    items = get_today_items()
    lines = [f"EMAIL PREVIEW - TODAY {len(items)}/3"]
    if not items:
        lines.append("No focus items yet.")
        return "\n".join(lines)

    for index, item in enumerate(items, start=1):
        status = "x" if item["done"] else " "
        lines.append(f"{index}. [{status}] {item['list']} {item['ref']} {item['text']}")
        details = item.get("details", {})
        detail_text = " | ".join(f"{key}={value}" for key, value in details.items() if value)
        if detail_text:
            lines.append(f"   {{{detail_text}}}")

    return "\n".join(lines)


def resolve_command_target(parts):
    """Resolve commands that may target either the active list or a named list."""
    if len(parts) == 2:
        todo_list = get_active_list()
        reference = parts[1]
    else:
        todo_list = find_list(" ".join(parts[1:-1]))
        reference = parts[-1]

    if not todo_list:
        return None, None, None

    reference = normalize_reference(reference)
    item, subtask = resolve_reference(todo_list, reference)
    if not item:
        return todo_list, None, None

    return todo_list, reference, {
        "list_id": todo_list["id"],
        "item_id": item["id"],
        "subtask_id": subtask["id"] if subtask else None
    }


def format_lists():
    """Render all lists, marking the active list with an asterisk."""
    todo_lists = get_lists()
    if not todo_lists:
        return "No lists yet. Use: + <name>"

    lines = []
    for index, todo_list in enumerate(todo_lists, start=1):
        marker = "*" if todo_list["id"] == ACTIVE_LIST_ID else " "
        lines.append(f"{marker} {index}. {todo_list['name']} ({len(todo_list['items'])} tasks)")
    return "\n".join(lines)


def handle_command(command):
    """Parse and execute one terminal command.

    This function is the core command router. It converts short terminal
    actions such as +, -, x, details, and today into storage operations.
    """
    parts = command.split()
    if not parts:
        return ""

    action = parts[0].lower()

    if action in {"help", "ajuda", "?"}:
        return HELP_TEXT

    if action in {"clear", "limpar", "cls"}:
        return "__CLEAR__"

    if action in {"lists", "listas", "ls"}:
        return format_lists()

    if action in {"use", "cd"} and len(parts) >= 2:
        todo_list = find_list(" ".join(parts[1:]))
        if not todo_list:
            return "List not found."

        set_active_list(todo_list)
        return format_list(todo_list)

    if action in {"out", "root", "back"}:
        set_active_list(None)
        return "Left the active list."

    if action in {"hoje", "today"}:
        if len(parts) == 1:
            return format_today_focus()

        if len(parts) == 2 and parts[1].lower() in {"clear", "reset"}:
            save_daily_focus(date.today().isoformat(), [])
            return format_today_focus()

        if len(parts) == 2 and not get_active_list() and parts[1].strip().rstrip(".").isdigit():
            return remove_today_focus_slot(parts[1])

        if len(parts) == 3 and parts[1].lower() in {"-", "remove", "rm"}:
            return remove_today_focus_slot(parts[2])

        todo_list, reference, target = resolve_command_target(parts)
        if not todo_list:
            return "No active list. Use: use <list|n>"
        if not target:
            return "Task not found."

        result = toggle_daily_focus(date.today().isoformat(), target)
        if result == "full":
            return "Today is full: 3/3 focus items. Remove one with: today - <n>"
        if result == "added":
            return format_today_focus()
        return format_today_focus()

    if action == "email":
        subcommand = parts[1].lower() if len(parts) >= 2 else "preview"

        if subcommand in {"preview", "show"}:
            return format_email_preview()

        if subcommand in {"send", "test"}:
            if playground_enabled():
                return "Email sending is disabled in playground mode."
            try:
                sent_count = send_today_email()
            except Exception as error:
                return f"Email failed: {error}"
            return f"Email sent with {sent_count}/3 focus items."

        return "Use: email preview | email send"

    if (
        (action in {"new", "create"} and len(parts) >= 3 and parts[1].lower() == "list")
        or (action in {"nova", "criar"} and len(parts) >= 3 and parts[1].lower() == "lista")
    ):
        name = " ".join(parts[2:]).strip()
        if create_list(name):
            return f"List created: {name}"
        return f"A list named '{name}' already exists."

    if action == "+" and len(parts) >= 2:
        active_list = get_active_list()

        if parts[1].lower() == "list" and len(parts) >= 3:
            name = " ".join(parts[2:]).strip()
            if create_list(name):
                created_list = find_list(name)
                set_active_list(created_list)
                return f"List created: {name}"
            return f"A list named '{name}' already exists."

        if active_list:
            if len(parts) >= 3 and can_resolve_item_reference(active_list, parts[1]):
                item = find_item(active_list, parts[1])
                entries = split_entries(" ".join(parts[2:]).strip())
                for entry in entries:
                    add_subtask(active_list["id"], item["id"], entry)
                return format_list(find_list(active_list["id"]))

            entries = split_entries(" ".join(parts[1:]).strip())
            for entry in entries:
                add_item(active_list["id"], entry)
            return format_list(find_list(active_list["id"]))

        todo_list = find_list(parts[1])
        if not todo_list:
            name = " ".join(parts[1:]).strip()
            if create_list(name):
                created_list = find_list(name)
                set_active_list(created_list)
                return f"List created: {name}"
            return f"A list named '{name}' already exists."

        if len(parts) < 3:
            return "Use: + <list|n> <task>"

        if len(parts) >= 4 and can_resolve_item_reference(todo_list, parts[2]):
            item = find_item(todo_list, parts[2])
            entries = split_entries(" ".join(parts[3:]).strip())
            for entry in entries:
                add_subtask(todo_list["id"], item["id"], entry)
            return format_list(find_list(todo_list["id"]))

        entries = split_entries(" ".join(parts[2:]).strip())
        for entry in entries:
            add_item(todo_list["id"], entry)
        return format_list(find_list(todo_list["id"]))

    if action == "-" and len(parts) >= 3:
        if parts[1].lower() in {"list", "lista"}:
            todo_list = find_list(" ".join(parts[2:]))
            if not todo_list:
                return "List not found."

            delete_list(todo_list["id"])
            if ACTIVE_LIST_ID == todo_list["id"]:
                set_active_list(None)
            return f"List deleted: {todo_list['name']}"

        if len(parts) != 3:
            return "Use: - <list|n> <ref>"

        todo_list = find_list(parts[1])
        if not todo_list:
            return "List not found."

        reference = normalize_reference(parts[2])
        item, subtask = resolve_reference(todo_list, reference)
        if not item:
            return "Task not found."

        if subtask:
            delete_subtask(todo_list["id"], item["id"], subtask["id"])
        elif "." in reference:
            return "Subtask not found."
        else:
            delete_item(todo_list["id"], item["id"])

        return format_list(find_list(todo_list["id"]))

    if action == "-" and len(parts) == 2:
        active_list = get_active_list()
        if not active_list:
            todo_list = find_list(parts[1])
            if not todo_list:
                return "List not found."

            delete_list(todo_list["id"])
            return f"List deleted: {todo_list['name']}"

        reference = normalize_reference(parts[1])
        item, subtask = resolve_reference(active_list, reference)
        if not item:
            return "Task not found."

        if subtask:
            delete_subtask(active_list["id"], item["id"], subtask["id"])
        elif "." in reference:
            return "Subtask not found."
        else:
            delete_item(active_list["id"], item["id"])

        return format_list(find_list(active_list["id"]))

    if action in {"mostrar", "show", "ver"}:
        todo_list = find_list(" ".join(parts[1:])) if len(parts) >= 2 else get_active_list()
        if not todo_list:
            return "List not found." if len(parts) >= 2 else "No active list. Use: use <list|n>"
        return format_list(todo_list)

    if action in {"details", "detail", "info"} and len(parts) >= 2:
        try:
            detail_parts = shlex.split(command)
        except ValueError as error:
            return f"Could not parse details: {error}"

        if len(detail_parts) < 2:
            return "Use: details <ref> key=value"

        if detail_parts[1].lower() in {"help", "fields", "?"}:
            return DETAIL_HELP_TEXT

        todo_list = get_active_list()
        reference = detail_parts[1]
        detail_tokens = detail_parts[2:]

        if not looks_like_reference(reference):
            reference_index = None
            for index in range(2, len(detail_parts)):
                if looks_like_reference(detail_parts[index]):
                    reference_index = index
                    break

            if reference_index is not None:
                todo_list = find_list(" ".join(detail_parts[1:reference_index]))
                reference = detail_parts[reference_index]
                detail_tokens = detail_parts[reference_index + 1:]

        reference = normalize_reference(reference)

        if not todo_list:
            return "No active list. Use: use <list|n>"

        item, subtask = resolve_reference(todo_list, reference)
        if not item:
            return "Task not found."
        if "." in reference and not subtask:
            parent_ref = reference.split(".", 1)[0]
            return f"Subtask {reference} not found. Create it with: + {parent_ref} <subtask>"

        target = subtask if subtask else item

        if any(token.lower() in {"clear", "reset"} for token in detail_tokens):
            if subtask:
                clear_subtask_details(todo_list["id"], item["id"], subtask["id"])
            else:
                clear_item_details(todo_list["id"], item["id"])
            item, subtask = resolve_reference(find_list(todo_list["id"]), reference)
            target = subtask if subtask else item
        else:
            details = parse_details(detail_tokens)
            if details:
                if subtask:
                    update_subtask_details(todo_list["id"], item["id"], subtask["id"], details)
                else:
                    update_item_details(todo_list["id"], item["id"], details)
                item, subtask = resolve_reference(find_list(todo_list["id"]), reference)
                target = subtask if subtask else item

        if detail_tokens and not any(token.lower() in {"clear", "reset"} for token in detail_tokens) and not parse_details(detail_tokens):
            return "No valid detail fields found. Type: details help"

        return format_task_details(target)

    if action in {"add", "adicionar"} and len(parts) >= 3:
        todo_list = find_list(parts[1])
        if not todo_list:
            return "List not found. Create it first with: + <name>"

        text = " ".join(parts[2:]).strip()
        add_item(todo_list["id"], text)
        return f"Task added to {todo_list['name']}: {text}"

    if action in {"x", "feito", "toggle", "done"} and len(parts) >= 2:
        if len(parts) == 2:
            todo_list = get_active_list()
            reference = parts[1]
        else:
            todo_list = find_list(" ".join(parts[1:-1]))
            reference = parts[-1]

        reference = normalize_reference(reference)

        if not todo_list:
            return "No active list. Use: use <list|n>" if len(parts) == 2 else "List not found."

        item, subtask = resolve_reference(todo_list, reference)
        if not item:
            return "Task not found."

        if subtask:
            toggle_subtask(todo_list["id"], item["id"], subtask["id"])
        elif "." in reference:
            return "Subtask not found."
        else:
            toggle_item(todo_list["id"], item["id"])

        return format_list(find_list(todo_list["id"]))

    if action in {"sub", "subtarefa"} and len(parts) >= 4:
        todo_list = find_list(parts[1])
        if not todo_list:
            return "List not found."

        item, subtask = resolve_reference(todo_list, parts[2])
        if not item:
            return "Task not found."
        if subtask:
            return "Use the parent task number to create a subtask. Example: + home 1 buy soap"

        text = " ".join(parts[3:]).strip()
        add_subtask(todo_list["id"], item["id"], text)
        return format_list(find_list(todo_list["id"]))

    if action in {"subfeito", "subtoggle"} and len(parts) in {3, 4}:
        todo_list = find_list(parts[1])
        if not todo_list:
            return "List not found."

        if len(parts) == 3:
            reference = parts[2] if "." in parts[2] else f"{parts[2]}.1"
        else:
            reference = f"{parts[2]}.{parts[3]}"
        item, subtask = resolve_reference(todo_list, reference)
        if not item:
            return "Task not found."
        if not subtask:
            return "Subtask not found."

        toggle_subtask(todo_list["id"], item["id"], subtask["id"])
        return format_list(find_list(todo_list["id"]))

    if action in {"apagar", "delete", "del", "rm"} and len(parts) == 3:
        if parts[1].lower() in {"list", "lista"}:
            todo_list = find_list(parts[2])
            if not todo_list:
                return "List not found."

            delete_list(todo_list["id"])
            if ACTIVE_LIST_ID == todo_list["id"]:
                set_active_list(None)
            return f"List deleted: {todo_list['name']}"

        todo_list = find_list(parts[1])
        if not todo_list:
            return "List not found."

        item, subtask = resolve_reference(todo_list, parts[2])
        if not item:
            return "Task not found."

        if subtask:
            delete_subtask(todo_list["id"], item["id"], subtask["id"])
        elif "." in parts[2]:
            return "Subtask not found."
        else:
            delete_item(todo_list["id"], item["id"])

        return format_list(find_list(todo_list["id"]))

    active_list = get_active_list()
    if active_list:
        entries = split_entries(command)
        for entry in entries:
            add_item(active_list["id"], entry)
        return format_list(find_list(active_list["id"]))

    return "Command not recognized. Type 'help'."


class TodoRequestHandler(BaseHTTPRequestHandler):
    """Small HTTP controller for pages, JSON endpoints, auth, and commands."""

    def send_text(self, status, body, content_type="text/plain; charset=utf-8"):
        """Send a UTF-8 response with an explicit content type."""
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def get_session_id(self):
        """Read the session id from the todo_session cookie."""
        header = self.headers.get("Cookie", "")
        if not header:
            return None
        cookie = cookies.SimpleCookie(header)
        if "todo_session" not in cookie:
            return None
        return cookie["todo_session"].value

    def is_authenticated(self):
        """Apply auth rules while allowing playground mode to remain public."""
        if not auth_enabled():
            return True
        return self.get_session_id() in SESSIONS

    def send_redirect(self, location):
        """Send a basic redirect response."""
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def send_auth_cookie(self, session_id):
        """Set the login cookie after a successful login."""
        cookie = cookies.SimpleCookie()
        cookie["todo_session"] = session_id
        cookie["todo_session"]["path"] = "/"
        cookie["todo_session"]["httponly"] = True
        cookie["todo_session"]["samesite"] = "Lax"
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", cookie.output(header="").strip())
        self.end_headers()

    def clear_auth_cookie(self):
        """Clear the login cookie on logout."""
        cookie = cookies.SimpleCookie()
        cookie["todo_session"] = ""
        cookie["todo_session"]["path"] = "/"
        cookie["todo_session"]["max-age"] = 0
        self.send_response(303)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", cookie.output(header="").strip())
        self.end_headers()

    def do_GET(self):
        """Route browser requests for HTML, CSS, and JSON endpoints."""
        path = unquote(self.path.split("?", 1)[0])

        if path == "/login":
            self.send_text(200, login_page(), "text/html; charset=utf-8")
            return

        if path == "/logout":
            session_id = self.get_session_id()
            if session_id:
                SESSIONS.discard(session_id)
            self.clear_auth_cookie()
            return

        if not self.is_authenticated() and path != "/static/style.css":
            self.send_redirect("/login")
            return

        if path == "/":
            html = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")
            self.send_text(200, html, "text/html; charset=utf-8")
            return

        if path == "/import":
            self.send_text(200, import_page(), "text/html; charset=utf-8")
            return

        if path == "/export":
            body = json.dumps(load_data(), indent=4, ensure_ascii=False)
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="lists.json"')
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        if path == "/static/style.css":
            css = (BASE_DIR / "static" / "style.css").read_text(encoding="utf-8")
            self.send_text(200, css, "text/css; charset=utf-8")
            return

        if path == "/lists":
            lists = [
                {
                    "index": index,
                    "id": todo_list["id"],
                    "name": todo_list["name"],
                    "count": len(todo_list["items"])
                }
                for index, todo_list in enumerate(get_lists(), start=1)
            ]
            body = json.dumps({"lists": lists}, ensure_ascii=False)
            self.send_text(200, body, "application/json; charset=utf-8")
            return

        if path == "/today":
            body = json.dumps({"items": get_today_focus_items()}, ensure_ascii=False)
            self.send_text(200, body, "application/json; charset=utf-8")
            return

        if path == "/active-list":
            body = json.dumps(get_active_list_payload(), ensure_ascii=False)
            self.send_text(200, body, "application/json; charset=utf-8")
            return

        self.send_text(404, "Not found")

    def do_POST(self):
        """Route login submissions and terminal command execution."""
        if self.path == "/login":
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            fields = parse_qs(raw_body)
            username = fields.get("username", [""])[0]
            password = fields.get("password", [""])[0]

            user_ok = secrets.compare_digest(username, get_config("APP_USER"))
            pass_ok = secrets.compare_digest(password, get_config("APP_PASS"))
            if user_ok and pass_ok:
                session_id = secrets.token_urlsafe(32)
                SESSIONS.add(session_id)
                self.send_auth_cookie(session_id)
                return

            self.send_text(401, login_page("Invalid login."), "text/html; charset=utf-8")
            return

        if self.path == "/import":
            if not self.is_authenticated():
                self.send_redirect("/login")
                return

            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            fields = parse_qs(raw_body)
            raw_json = fields.get("data_json", [""])[0]

            try:
                imported_data = normalize_data(json.loads(raw_json))
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                self.send_text(400, import_page(f"Import failed: {error}"), "text/html; charset=utf-8")
                return

            save_data(imported_data)
            self.send_text(200, import_page("Import complete."), "text/html; charset=utf-8")
            return

        if self.path != "/command":
            self.send_text(404, "Not found")
            return

        if not self.is_authenticated():
            self.send_text(401, json.dumps({"response": "Login required.", "prompt": get_prompt()}), "application/json; charset=utf-8")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")

        try:
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            payload = {}

        response = handle_command(payload.get("command", "").strip())
        body = json.dumps({"response": response, "prompt": get_prompt()}, ensure_ascii=False)
        self.send_text(200, body, "application/json; charset=utf-8")

    def log_message(self, format, *args):
        """Silence default request logging to keep the terminal readable."""
        return


if __name__ == "__main__":
    start_daily_email_scheduler()
    host = app_host()
    port = app_port()
    server = ThreadingHTTPServer((host, port), TodoRequestHandler)
    print(f"TODO terminal running at http://{host}:{port}")
    server.serve_forever()
