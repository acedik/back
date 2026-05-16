from __future__ import annotations

import os
import secrets
import sqlite3
import uuid
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads" / "clients"
DB_PATH = DATA_DIR / "amous.sqlite3"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
CATEGORIES = ["Manufacturing", "Enterprises", "Logistics & Trade", "Tech & Services"]


SEED_CLIENTS = {
    "Manufacturing": ["Apu Packaging Pvt Ltd", "Aakrishi Pvt Ltd", "Vapi Industries Ltd"],
    "Enterprises": ["Regent Enterprises", "Dipali Enterprises", "Supreme Enterprises"],
    "Logistics & Trade": ["Global Logistics", "Supreme Infra Ltd", "Coastal Traders Co."],
    "Tech & Services": ["Tech Solutions Inc", "Vapi Group Industries", "Gujarat Services Ltd"],
}


def load_env_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


SUPABASE_BUCKET = os.environ.get("SUPABASE_CLIENT_BUCKET", "client-logos")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


app = Flask(__name__, static_folder=None)
app.config.update(
    SECRET_KEY=os.environ.get("AMOUS_SECRET_KEY", secrets.token_hex(32)),
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@app.after_request
def add_cors_headers(response):
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Accept")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    return response

supabase_http = requests.Session()
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase_http.headers.update(
        {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        }
    )


def using_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def supabase_request(method: str, path: str, **kwargs):
    response = supabase_http.request(method, f"{SUPABASE_URL}{path}", timeout=30, **kwargs)
    response.raise_for_status()
    if response.content:
        return response.json()
    return None


def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db() -> None:
    if using_supabase():
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return

    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                image_filename TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        total = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        if total == 0:
            order = 0
            for category, names in SEED_CLIENTS.items():
                for name in names:
                    db.execute(
                        "INSERT INTO clients (category, name, sort_order) VALUES (?, ?, ?)",
                        (category, name, order),
                    )
                    order += 1


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def looks_like_image(file_storage) -> bool:
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    return (
        header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith(b"\xff\xd8\xff")
        or header.startswith(b"GIF87a")
        or header.startswith(b"GIF89a")
        or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
    )


def save_client_image(file_storage) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename) or not looks_like_image(file_storage):
        raise ValueError("Use a real PNG, JPG, JPEG, WEBP, or GIF image.")
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower()
    image_filename = f"{uuid.uuid4().hex}.{ext}"

    if using_supabase():
        image_path = f"clients/{image_filename}"
        image_bytes = file_storage.read()
        file_storage.stream.seek(0)
        encoded_path = quote(image_path, safe="/")
        supabase_request(
            "POST",
            f"/storage/v1/object/{SUPABASE_BUCKET}/{encoded_path}",
            data=image_bytes,
            headers={
                "Content-Type": file_storage.mimetype or f"image/{ext}",
                "x-upsert": "false",
            },
        )
        return image_path

    file_storage.save(UPLOAD_DIR / image_filename)
    return image_filename


def image_public_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    if using_supabase():
        return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{quote(image_path, safe='/')}"
    return url_for("uploaded_client_image", filename=image_path)


def remove_client_image(image_path: str | None) -> None:
    if not image_path:
        return
    if using_supabase():
        supabase_request(
            "DELETE",
            f"/storage/v1/object/{SUPABASE_BUCKET}",
            json={"prefixes": [image_path]},
        )
        return
    (UPLOAD_DIR / image_path).unlink(missing_ok=True)


def normalize_client(row: Any) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        image_path = row["image_filename"]
        return {
            "id": row["id"],
            "category": row["category"],
            "name": row["name"],
            "image_path": image_path,
            "image_url": image_public_url(image_path),
            "created_at": row["created_at"] if "created_at" in row.keys() else None,
        }

    image_path = row.get("image_path")
    return {
        "id": row.get("id"),
        "category": row.get("category"),
        "name": row.get("name"),
        "image_path": image_path,
        "image_url": image_public_url(image_path),
        "created_at": row.get("created_at"),
    }


def list_clients() -> list[dict[str, Any]]:
    if using_supabase():
        rows = supabase_request(
            "GET",
            "/rest/v1/clients?select=id,category,name,image_path,sort_order,created_at"
            "&order=category.asc,sort_order.asc,id.asc",
        )
        return [normalize_client(row) for row in rows]

    with get_db() as db:
        rows = db.execute(
            """
            SELECT id, category, name, image_filename, created_at
            FROM clients
            ORDER BY category, sort_order, id
            """
        ).fetchall()
    return [normalize_client(row) for row in rows]


def next_sort_order() -> int:
    if using_supabase():
        rows = supabase_request("GET", "/rest/v1/clients?select=sort_order")
        orders = [row.get("sort_order", 0) for row in rows]
        return (max(orders) if orders else 0) + 1

    with get_db() as db:
        return db.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM clients").fetchone()[0]


def create_client_record(category: str, name: str, image_path: str | None) -> None:
    payload = {
        "category": category,
        "name": name,
        "image_path": image_path,
        "sort_order": next_sort_order(),
    }
    if using_supabase():
        supabase_request(
            "POST",
            "/rest/v1/clients",
            json=payload,
            headers={"Prefer": "return=minimal"},
        )
        return

    with get_db() as db:
        db.execute(
            "INSERT INTO clients (category, name, image_filename, sort_order) VALUES (?, ?, ?, ?)",
            (category, name, image_path, payload["sort_order"]),
        )


def get_client_image_path(client_id: int) -> str | None:
    if using_supabase():
        rows = supabase_request(
            "GET",
            f"/rest/v1/clients?select=image_path&id=eq.{client_id}&limit=1",
        )
        return rows[0]["image_path"] if rows else None

    with get_db() as db:
        row = db.execute("SELECT image_filename FROM clients WHERE id = ?", (client_id,)).fetchone()
    return row["image_filename"] if row else None


def update_client_image_path(client_id: int, image_path: str) -> bool:
    if using_supabase():
        rows = supabase_request(
            "PATCH",
            f"/rest/v1/clients?id=eq.{client_id}",
            json={"image_path": image_path},
            headers={"Prefer": "return=representation"},
        )
        return bool(rows)

    with get_db() as db:
        row = db.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not row:
            return False
        db.execute("UPDATE clients SET image_filename = ? WHERE id = ?", (image_path, client_id))
    return True


def delete_client_record(client_id: int) -> str | None:
    image_path = get_client_image_path(client_id)
    if using_supabase():
        supabase_request(
            "DELETE",
            f"/rest/v1/clients?id=eq.{client_id}",
            headers={"Prefer": "return=minimal"},
        )
        return image_path

    with get_db() as db:
        row = db.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not row:
            return None
        db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    return image_path


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_csrf() -> None:
    if request.form.get("csrf_token") != session.get("csrf_token"):
        abort(400, "Invalid security token")


def admin_password_is_valid(password: str) -> bool:
    password_hash = os.environ.get("AMOUS_ADMIN_PASSWORD_HASH")
    plain_password = os.environ.get("AMOUS_ADMIN_PASSWORD")
    if password_hash:
        return check_password_hash(password_hash, password)
    if plain_password:
        return secrets.compare_digest(plain_password, password)
    return False


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_security_helpers():
    return {"csrf_token": csrf_token}


@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/about.html")
def about():
    return send_from_directory(FRONTEND_DIR, "about.html")


@app.route("/style.css")
def style():
    return send_from_directory(FRONTEND_DIR, "style.css")


@app.route("/Script.js")
def script_file():
    return send_from_directory(FRONTEND_DIR, "Script.js")


@app.route("/main/<path:filename>")
def main_file(filename: str):
    return send_from_directory(FRONTEND_DIR / "main", filename)


@app.route("/<path:filename>")
def frontend_file(filename: str):
    allowed_root_files = {
        "Robot.txt",
        "challenge.png",
        "google030997fbc0cf37d6.html",
        "google030997fbc0cf37d6.xml",
    }
    if filename in allowed_root_files:
        return send_from_directory(FRONTEND_DIR, filename)
    abort(404)


@app.route("/uploads/clients/<path:filename>")
def uploaded_client_image(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/clients")
def api_clients():
    grouped = {category: [] for category in CATEGORIES}
    for row in list_clients():
        category = row["category"]
        grouped.setdefault(category, [])
        grouped[category].append(
            {
                "id": row["id"],
                "name": row["name"],
                "image_url": row["image_url"],
            }
        )
    return jsonify([{"category": category, "clients": grouped.get(category, [])} for category in CATEGORIES])


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        verify_csrf()
        if admin_password_is_valid(request.form.get("password", "")):
            session.clear()
            session["admin_logged_in"] = True
            csrf_token()
            return redirect(url_for("admin_dashboard"))
        flash("Wrong password, or AMOUS_ADMIN_PASSWORD is not set.")
    return render_template_string(LOGIN_TEMPLATE)


@app.route("/admin/logout", methods=["POST"])
@login_required
def admin_logout():
    verify_csrf()
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template_string(
        ADMIN_TEMPLATE,
        categories=CATEGORIES,
        clients=list_clients(),
        database_name="Supabase" if using_supabase() else "SQLite local fallback",
    )


@app.route("/admin/clients", methods=["POST"])
@login_required
def add_client():
    verify_csrf()
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    image = request.files.get("image")

    if not name or category not in CATEGORIES:
        flash("Please enter a company name and choose a valid category.")
        return redirect(url_for("admin_dashboard"))

    try:
        image_filename = save_client_image(image)
    except ValueError as error:
        flash(str(error))
        return redirect(url_for("admin_dashboard"))

    create_client_record(category, name, image_filename)
    flash("Client added.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/clients/<int:client_id>/image", methods=["POST"])
@login_required
def update_client_image(client_id: int):
    verify_csrf()
    image = request.files.get("image")
    try:
        image_filename = save_client_image(image)
    except ValueError as error:
        flash(str(error))
        return redirect(url_for("admin_dashboard"))

    if not image_filename:
        flash("Choose an image before updating.")
        return redirect(url_for("admin_dashboard"))

    previous_image = get_client_image_path(client_id)
    if not update_client_image_path(client_id, image_filename):
        remove_client_image(image_filename)
        flash("Client not found.")
        return redirect(url_for("admin_dashboard"))
    remove_client_image(previous_image)
    flash("Client picture updated.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/clients/<int:client_id>/delete", methods=["POST"])
@login_required
def delete_client(client_id: int):
    verify_csrf()
    image_path = delete_client_record(client_id)
    if image_path is not None:
        remove_client_image(image_path)
        flash("Client deleted.")
    return redirect(url_for("admin_dashboard"))


LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AMOUS Admin Login</title>
  <style>
    body{font-family:Inter,Arial,sans-serif;background:#eef3f8;color:#102033;min-height:100vh;display:grid;place-items:center;margin:0}
    form{width:min(420px,calc(100% - 32px));background:#fff;border:1px solid #dbe5f0;border-radius:18px;padding:28px;box-shadow:0 24px 48px rgba(15,23,42,.12)}
    h1{margin:0 0 18px;font-size:1.6rem;color:#0f2f6b}
    label{display:block;font-weight:700;margin-bottom:8px}
    input,button{width:100%;box-sizing:border-box;border-radius:10px;font:inherit}
    input{border:1px solid #cbd5e1;padding:12px;margin-bottom:16px}
    button{border:0;background:#1d4ed8;color:#fff;font-weight:800;padding:12px;cursor:pointer}
    .msg{color:#b91c1c;margin-bottom:12px;font-weight:700}
  </style>
</head>
<body>
  <form method="post">
    <h1>AMOUS Admin</h1>
    {% for message in get_flashed_messages() %}<div class="msg">{{ message }}</div>{% endfor %}
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label for="password">Password</label>
    <input id="password" name="password" type="password" required autofocus>
    <button type="submit">Login</button>
  </form>
</body>
</html>
"""


ADMIN_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AMOUS Client Admin</title>
  <style>
    body{font-family:Inter,Arial,sans-serif;background:#eef3f8;color:#102033;margin:0}
    header{display:flex;justify-content:space-between;align-items:center;padding:18px 5%;background:#fff;border-bottom:1px solid #dbe5f0;position:sticky;top:0}
    main{width:min(1100px,90%);margin:34px auto}
    h1,h2{color:#0f2f6b}
    .panel{background:#fff;border:1px solid #dbe5f0;border-radius:18px;padding:24px;box-shadow:0 18px 38px rgba(15,23,42,.08);margin-bottom:24px}
    .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
    label{display:block;font-size:.82rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#556579;margin-bottom:8px}
    input,select,button{width:100%;box-sizing:border-box;border-radius:10px;font:inherit}
    input,select{border:1px solid #cbd5e1;padding:12px;background:#fff}
    button{border:0;background:#1d4ed8;color:#fff;font-weight:800;padding:12px;cursor:pointer}
    .logout{width:auto;background:#0f2f6b;padding:10px 14px}
    .danger{background:#b91c1c}
    .clients{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
    .client{display:flex;gap:14px;align-items:center;justify-content:space-between;background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:12px}
    .client-info{display:flex;align-items:center;gap:12px;min-width:0}
    .client img{width:52px;height:52px;border-radius:10px;object-fit:cover;background:#e2e8f0}
    .placeholder{width:52px;height:52px;border-radius:10px;background:#dbeafe;display:grid;place-items:center;color:#1d4ed8;font-weight:900}
    .name{font-weight:800}.cat{font-size:.82rem;color:#556579}.msg{font-weight:800;color:#166534;margin-bottom:14px}
    .actions{display:grid;gap:8px;min-width:210px}.image-form{display:grid;grid-template-columns:1fr auto;gap:8px}.image-form input{padding:8px;font-size:.82rem}.image-form button{padding:8px 10px}
    @media(max-width:760px){.grid,.clients{grid-template-columns:1fr}header{align-items:flex-start;gap:12px;flex-direction:column}.logout{width:100%}}
  </style>
</head>
<body>
  <header>
    <div>
      <strong>AMOUS Admin</strong>
      <div style="color:#556579;font-size:.9rem">Manage company names and pictures · {{ database_name }}</div>
    </div>
    <form method="post" action="{{ url_for('admin_logout') }}">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button class="logout" type="submit">Logout</button>
    </form>
  </header>
  <main>
    {% for message in get_flashed_messages() %}<div class="msg">{{ message }}</div>{% endfor %}
    <section class="panel">
      <h1>Add Company</h1>
      <form class="grid" method="post" action="{{ url_for('add_client') }}" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <div>
          <label for="name">Company Name</label>
          <input id="name" name="name" required>
        </div>
        <div>
          <label for="category">Column</label>
          <select id="category" name="category" required>
            {% for category in categories %}<option value="{{ category }}">{{ category }}</option>{% endfor %}
          </select>
        </div>
        <div>
          <label for="image">Picture / Logo</label>
          <input id="image" name="image" type="file" accept=".png,.jpg,.jpeg,.webp,.gif,image/*">
        </div>
        <div style="align-self:end"><button type="submit">Add Client</button></div>
      </form>
    </section>
    <section class="panel">
      <h2>Current Companies</h2>
      <div class="clients">
        {% for client in clients %}
        <div class="client">
          <div class="client-info">
            {% if client.image_url %}
              <img src="{{ client.image_url }}" alt="">
            {% else %}
              <div class="placeholder">{{ client.name[:1] }}</div>
            {% endif %}
            <div>
              <div class="name">{{ client.name }}</div>
              <div class="cat">{{ client.category }}</div>
            </div>
          </div>
          <div class="actions">
            <form class="image-form" method="post" action="{{ url_for('update_client_image', client_id=client.id) }}" enctype="multipart/form-data">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <input name="image" type="file" accept=".png,.jpg,.jpeg,.webp,.gif,image/*" required>
              <button type="submit">Pic</button>
            </form>
            <form method="post" action="{{ url_for('delete_client', client_id=client.id) }}">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <button class="danger" type="submit">Delete</button>
            </form>
          </div>
        </div>
        {% endfor %}
      </div>
    </section>
  </main>
</body>
</html>
"""


init_db()


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="127.0.0.1", port=5000, debug=debug_enabled)
