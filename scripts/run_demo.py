import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def start_service(name, app, port, extra_env=None):
    environment = os.environ.copy()
    environment.update(extra_env or {})
    command = [
        PYTHON,
        "-m",
        "uvicorn",
        app,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    process = subprocess.Popen(command, cwd=ROOT, env=environment)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{name} exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                if response.status == 200:
                    print(f"{name} is ready on port {port}")
                    return process
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    process.terminate()
    raise TimeoutError(f"{name} did not become ready on port {port}")


def main():
    processes = []
    try:
        processes.append(
            start_service(
                "Product Service",
                "app.main:app",
                8001,
                {"PYTHONPATH": str(ROOT / "services" / "product-service")},
            )
        )
        processes.append(
            start_service(
                "Order Service",
                "app.main:app",
                8002,
                {
                    "PYTHONPATH": str(ROOT / "services" / "order-service"),
                    "PRODUCT_SERVICE_URL": "http://127.0.0.1:8001",
                },
            )
        )
        processes.append(
            start_service(
                "API Gateway",
                "app.main:app",
                8000,
                {
                    "PYTHONPATH": str(ROOT / "api-gateway"),
                    "PRODUCT_SERVICE_URL": "http://127.0.0.1:8001",
                    "ORDER_SERVICE_URL": "http://127.0.0.1:8002",
                },
            )
        )
        frontend = subprocess.Popen(
            [PYTHON, str(ROOT / "frontend" / "dev_server.py")],
            cwd=ROOT,
        )
        processes.append(frontend)
        time.sleep(0.5)
        if frontend.poll() is not None:
            raise RuntimeError(f"Frontend exited with code {frontend.returncode}")
        print("\nOpen http://localhost:8080 in your browser.")
        print("Press Ctrl+C here to stop all demo services.\n")
        frontend.wait()
    except KeyboardInterrupt:
        print("\nStopping the demo services.")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            if process.poll() is None:
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
