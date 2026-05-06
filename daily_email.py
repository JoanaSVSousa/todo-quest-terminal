import html
import smtplib
import sys
import threading
import time
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from storage import get_daily_focus, get_lists

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"


def load_env(path=ENV_FILE):
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


def is_enabled(config):
    return config.get("EMAIL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def get_today_items(day=None):
    selected_day = day or date.today().isoformat()
    focus_items = []

    for target in get_daily_focus(selected_day):
        for todo_list in get_lists():
            if todo_list["id"] != target["list_id"]:
                continue

            for item_index, item in enumerate(todo_list["items"], start=1):
                if item["id"] != target["item_id"]:
                    continue

                if target.get("subtask_id"):
                    for sub_index, subtask in enumerate(item.get("subtasks", []), start=1):
                        if subtask["id"] == target["subtask_id"]:
                            focus_items.append({
                                "list": todo_list["name"],
                                "ref": f"{item_index}.{sub_index}",
                                "text": subtask["text"],
                                "done": subtask.get("done", False),
                                "details": subtask.get("details", {})
                            })
                            break
                else:
                    focus_items.append({
                        "list": todo_list["name"],
                        "ref": str(item_index),
                        "text": item["text"],
                        "done": item.get("done", False),
                        "details": item.get("details", {})
                    })

    return focus_items


def build_text_email(items):
    lines = [f"TODAY {len(items)}/3", ""]
    if not items:
        lines.append("No focus items yet.")
    else:
        for index, item in enumerate(items, start=1):
            status = "x" if item["done"] else " "
            lines.append(f"{index}. [{status}] {item['list']} {item['ref']} {item['text']}")
    return "\n".join(lines)


def build_html_email(items):
    rows = []
    if not items:
        rows.append('<div class="slot" style="line-height:1.55;margin:6px 0;">1. [ ] ...</div>')
        rows.append('<div class="slot" style="line-height:1.55;margin:6px 0;">2. [ ] ...</div>')
        rows.append('<div class="slot" style="line-height:1.55;margin:6px 0;">3. [ ] ...</div>')
    else:
        for index, item in enumerate(items, start=1):
            status = "x" if item["done"] else "&nbsp;"
            details = item.get("details", {})
            detail_bits = [
                f"{html.escape(key)}={html.escape(str(value))}"
                for key, value in details.items()
                if value
            ]
            details_html = (
                f'<div class="details" style="margin-left:42px;color:#00cc55;font-size:13px;">{" | ".join(detail_bits)}</div>'
                if detail_bits else ""
            )
            rows.append(
                '<div class="slot" style="line-height:1.55;margin:6px 0;">'
                f'<span class="index">{index}.</span> '
                f'<span class="checkbox" style="color:#9dffbf;">[{status}]</span> '
                f'<span class="list" style="color:#9dffbf;">{html.escape(item["list"])}</span> '
                f'<span class="ref" style="color:#00cc55;">{html.escape(item["ref"])}</span> '
                f'<span>{html.escape(item["text"])}</span>'
                f'{details_html}'
                '</div>'
            )

        for index in range(len(items) + 1, 4):
            rows.append(f'<div class="slot" style="line-height:1.55;margin:6px 0;">{index}. [ ] ...</div>')

    return f"""<!doctype html>
<html style="margin:0;padding:0;background-color:#020402;background:#020402;">
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="dark">
  <meta name="supported-color-schemes" content="dark">
  <style>
    html {{
      margin: 0;
      padding: 0;
      background: #020402;
      background-color: #020402;
    }}
    body {{
      margin: 0;
      background: #020402;
      background-color: #020402;
      color: #00ff66;
      font-family: "Courier New", monospace;
      text-shadow: 0 0 6px #00ff66;
    }}
    .frame {{
      max-width: 720px;
      margin: 0 auto;
      padding: 28px;
      background: #000803;
      border: 1px solid #00ff66;
      box-shadow: 0 0 25px rgba(0, 255, 102, 0.25);
    }}
    .title {{
      color: #9dffbf;
      border-bottom: 1px solid rgba(0, 255, 102, 0.45);
      padding-bottom: 12px;
      margin-bottom: 16px;
    }}
    .slot {{
      line-height: 1.55;
      margin: 6px 0;
    }}
    .checkbox {{
      color: #9dffbf;
    }}
    .list {{
      color: #9dffbf;
    }}
    .ref {{
      opacity: 0.78;
    }}
    .details {{
      margin-left: 42px;
      color: rgba(0, 255, 102, 0.78);
      font-size: 13px;
    }}
  </style>
</head>
<body bgcolor="#020402" style="margin:0;padding:0;background-color:#020402;background:#020402;color:#00ff66;font-family:'Courier New',monospace;text-shadow:0 0 6px #00ff66;">
  <div style="margin:0;padding:0;background-color:#020402;background:#020402;min-height:100%;width:100%;">
    <!--[if mso]>
    <table role="presentation" width="100%" height="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#020402"><tr><td bgcolor="#020402">
    <![endif]-->
    <table role="presentation" width="100%" height="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#020402" style="width:100%;min-height:100vh;height:100%;background-color:#020402;background:#020402;margin:0;padding:24px;mso-table-lspace:0pt;mso-table-rspace:0pt;">
      <tr>
        <td align="center" valign="top" bgcolor="#020402" style="background-color:#020402;background:#020402;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#000803" style="max-width:720px;width:100%;background-color:#000803;background:#000803;border:1px solid #00ff66;box-shadow:0 0 25px rgba(0,255,102,0.25);">
          <tr>
            <td style="padding:28px;color:#00ff66;font-family:'Courier New',monospace;text-shadow:0 0 6px #00ff66;">
              <div>TODO QUEST SYSTEM v2.0</div>
              <div class="title" style="color:#9dffbf;border-bottom:1px solid #007a33;padding-bottom:12px;margin-bottom:16px;">TODAY {len(items)}/3</div>
              {"".join(rows)}
            </td>
          </tr>
        </table>
        </td>
      </tr>
    </table>
    <!--[if mso]>
    </td></tr></table>
    <![endif]-->
  </div>
</body>
</html>"""


def send_today_email(config=None):
    settings = config or load_env()
    required = ["EMAIL_HOST", "EMAIL_PORT", "EMAIL_USER", "EMAIL_PASS", "EMAIL_TO"]
    missing = [key for key in required if not settings.get(key)]
    if missing:
        raise ValueError(f"Missing email config: {', '.join(missing)}")

    items = get_today_items()
    message = EmailMessage()
    message["Subject"] = f"Today {len(items)}/3 - TODO QUEST SYSTEM"
    message["From"] = settings["EMAIL_USER"]
    message["To"] = settings["EMAIL_TO"]
    message.set_content(build_text_email(items))
    message.add_alternative(build_html_email(items), subtype="html")

    host = settings["EMAIL_HOST"]
    port = int(settings["EMAIL_PORT"])
    use_tls = settings.get("EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
    use_ssl = settings.get("EMAIL_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=30) as smtp:
        smtp.ehlo()
        if use_tls and not use_ssl:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(settings["EMAIL_USER"], settings["EMAIL_PASS"])
        smtp.send_message(message)

    return len(items)


def seconds_until_next_run(config):
    timezone = ZoneInfo(config.get("EMAIL_TIMEZONE", "Europe/Lisbon"))
    hour_text, minute_text = config.get("EMAIL_TIME", "09:00").split(":", 1)
    now = datetime.now(timezone)
    target = now.replace(hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return max(1, int((target - now).total_seconds()))


def start_daily_email_scheduler():
    config = load_env()
    if not is_enabled(config):
        return None

    def loop():
        while True:
            current_config = load_env()
            delay = seconds_until_next_run(current_config)
            time.sleep(delay)
            try:
                send_today_email(current_config)
            except Exception as error:
                print(f"Daily email failed: {error}")

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "send":
        sent_count = send_today_email(load_env())
        print(f"Sent Today email with {sent_count}/3 focus items.")
    else:
        print(build_text_email(get_today_items()))
