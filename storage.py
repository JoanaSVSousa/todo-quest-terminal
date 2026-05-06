import json
import os
from pathlib import Path
from datetime import date
from threading import RLock
import uuid

DATA_FILE = Path("data/lists.json")
EXAMPLE_DATA_FILE = Path("data/lists.example.json")
DATA_LOCK = RLock()

def playground_enabled():
    return os.environ.get("PLAYGROUND_MODE", "false").lower() in {"1", "true", "yes", "on"}

def normalize_item(item):
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

def load_data():
    with DATA_LOCK:
        if not DATA_FILE.exists():
            DATA_FILE.parent.mkdir(exist_ok=True)
            if playground_enabled() and EXAMPLE_DATA_FILE.exists():
                with open(EXAMPLE_DATA_FILE) as f:
                    save_data(json.load(f))
            else:
                save_data({"daily": {}, "lists": []})
        with open(DATA_FILE) as f:
            data = normalize_data(json.load(f))
        save_data(data)
        return data

def save_data(data):
    with DATA_LOCK:
        DATA_FILE.parent.mkdir(exist_ok=True)
        temp_file = DATA_FILE.with_name(f"{DATA_FILE.name}.{uuid.uuid4().hex}.tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=4)
        temp_file.replace(DATA_FILE)

def get_lists():
    return load_data()["lists"]

def get_daily_focus(day):
    return load_data().get("daily", {}).get(day, [])

def save_daily_focus(day, focus_items):
    data = load_data()
    data.setdefault("daily", {})[day] = focus_items
    save_data(data)

def toggle_daily_focus(day, target):
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
    data = load_data()
    original_count = len(data["lists"])
    data["lists"] = [
        todo_list for todo_list in data["lists"]
        if todo_list["id"] != list_id
    ]
    save_data(data)
    return len(data["lists"]) != original_count

def add_item(list_id, text):
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
