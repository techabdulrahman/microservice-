import os
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_GATEWAY_URL = "http://127.0.0.1:8000"
FRONTEND_DIR = Path(__file__).resolve().parent


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def _proxy_api(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))) or None
        request = Request(
            f"{API_GATEWAY_URL}{self.path}",
            data=body,
            method=self.command,
            headers={
                key: value
                for key, value in self.headers.items()
                if key.lower() in {"content-type", "idempotency-key"}
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                status_code = response.status
                content_type = response.headers.get("Content-Type", "application/json")
                response_body = response.read()
        except HTTPError as error:
            status_code = error.code
            content_type = error.headers.get("Content-Type", "application/json")
            response_body = error.read()
        except (URLError, TimeoutError):
            status_code = 503
            content_type = "application/json"
            response_body = json.dumps({"detail": "API gateway is unavailable"}).encode()

        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self):
        if self.path == "/api" or self.path.startswith("/api/"):
            self._proxy_api()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api" or self.path.startswith("/api/"):
            self._proxy_api()
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        if not (self.path == "/healthz"):
            super().log_message(format, *args)


if __name__ == "__main__":
    host = os.getenv("DEMO_HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, 8080), DemoHandler)
    print("Colorful Market is ready at http://localhost:8080")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping the demo storefront.")
    finally:
        server.server_close()
