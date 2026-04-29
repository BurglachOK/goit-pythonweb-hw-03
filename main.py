from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import mimetypes
import pathlib
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from socketserver import ThreadingMixIn

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Обробка кожного запиту в окремому потоці"""
    pass

BASE_DIR = pathlib.Path(__file__).resolve().parent
FRONT_DIR = BASE_DIR / "html"
STORAGE_DIR = BASE_DIR / "storage"
DATA_FILE = STORAGE_DIR / "data.json"
TEMPLATES_DIR = BASE_DIR / "templat"


def ensure_storage() -> None:
    STORAGE_DIR.mkdir(exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("{}", encoding="utf-8")


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path

        if ".well-known" in route or "devtools" in route:
            self.send_response(204) 
            self.end_headers()
            return

        if route in ("/", "/index.html"):
            self.send_html_file(FRONT_DIR / "index.html")
            return

        if route in ("/message", "/message.html"):
            self.send_html_file(FRONT_DIR / "message.html")
            return

        if route == "/read":
            self.render_read_page()
            return

        static_candidates = [
            FRONT_DIR / route.lstrip("/"),
            BASE_DIR / route.lstrip("/"),
        ]
        for file_path in static_candidates:
            if file_path.exists() and file_path.is_file():
                self.send_static(file_path)
                return

        self.send_html_file(FRONT_DIR / "error.html", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/message", "/message.html"):
            self.send_html_file(FRONT_DIR / "error.html", 404)
            return

        try:
            data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            data_parse = urllib.parse.unquote_plus(data.decode("utf-8"))
            data_dict = {
                key: value
                for key, value in [element.split("=", 1) for element in data_parse.split("&") if "=" in element]
            }
            self.save_data(data_dict)
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        except Exception:
            self.send_html_file(FRONT_DIR / "error.html", 500)

    def send_html_file(self, filename: pathlib.Path, status: int = 200):
        self.send_response(status)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        with open(filename, "rb") as file:
            self.wfile.write(file.read())

    def send_static(self, file_path: pathlib.Path):
        self.send_response(200)
        mime_type, _ = mimetypes.guess_type(str(file_path))
        self.send_header("Content-type", mime_type or "text/plain")
        self.end_headers()
        with open(file_path, "rb") as file:
            self.wfile.write(file.read())

    def save_data(self, data: dict):
        ensure_storage()
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                stored_data = json.load(file)
                if not isinstance(stored_data, dict):
                    stored_data = {}
        except (json.JSONDecodeError, FileNotFoundError):
            stored_data = {}

        stored_data[str(datetime.now())] = {
            "username": data.get("username", ""),
            "message": data.get("message", ""),
        }

        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(stored_data, file, ensure_ascii=False, indent=2)

    def render_read_page(self):
        ensure_storage()
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        template = env.get_template("read.html")
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                messages = json.load(file)
                if not isinstance(messages, dict):
                    messages = {}
        except (json.JSONDecodeError, FileNotFoundError):
            messages = {}

        content = template.render(messages=messages)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))


def run(server_class=ThreadedHTTPServer, handler_class=HttpHandler):
    ensure_storage()
    server_address = ("", 3000)
    http = server_class(server_address, handler_class)
    print("Server started at http://localhost:3000")
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http.server_close()


if __name__ == "__main__":
    run()