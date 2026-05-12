#!/usr/bin/env python3
"""
PinkyBrain v5.2.0 — Windows System Tray Launcher
Minimal system tray app for managing the PinkyBrain service.

Requirements: pystray, Pillow (installed with the app)
"""

import json
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
except ImportError:
    # Attempt auto-install
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pystray", "Pillow", "--quiet"])
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw

BASE_DIR = Path(os.environ.get("PINKYBRAIN_HOME", r"C:\PinkyBrain"))
NODE_JSON = BASE_DIR / "data" / "config" / "node.json"
LOGS_DIR = BASE_DIR / "data" / "logs"
SHARED_MODELS_DIR = BASE_DIR / "shared_models"
CONFIG_DIR = BASE_DIR / "data" / "config"


def get_port() -> int:
    """Read port from node.json."""
    try:
        config = json.loads(NODE_JSON.read_text())
        return config.get("node", {}).get("port", 8080)
    except Exception:
        return 8080


def get_service_status() -> str:
    """Check if PinkyBrain service is running."""
    try:
        result = subprocess.run(
            ["sc", "query", "PinkyBrain"],
            capture_output=True, text=True, timeout=5
        )
        if "RUNNING" in result.stdout:
            return "running"
        return "stopped"
    except Exception:
        return "unknown"


def create_icon_image(color: str = "green") -> Image.Image:
    """Create a simple tray icon."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    colors = {
        "green": (34, 197, 94),
        "red": (239, 68, 68),
        "yellow": (234, 179, 8),
    }
    fill = colors.get(color, colors["green"])

    # Draw a hexagon (mesh node symbol)
    cx, cy, r = size // 2, size // 2, size // 2 - 4
    import math
    points = []
    for i in range(6):
        angle = math.pi / 6 + i * math.pi / 3
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=fill, outline=(255, 255, 255, 200))

    # Draw "N" letter
    draw.text((cx - 8, cy - 10), "N", fill=(255, 255, 255), font=None)
    return img


def open_web_ui(icon, item):
    """Open PinkyBrain Web UI in default browser."""
    port = get_port()
    webbrowser.open(f"http://localhost:{port}")


def open_folder(path: Path):
    """Open a folder in Explorer."""
    os.startfile(str(path))


def open_config(icon, item):
    open_folder(CONFIG_DIR)


def open_shared_models(icon, item):
    open_folder(SHARED_MODELS_DIR)


def open_logs(icon, item):
    open_folder(LOGS_DIR)


def start_service(icon, item):
    subprocess.run(["sc", "start", "PinkyBrain"], capture_output=True)


def stop_service(icon, item):
    subprocess.run(["sc", "stop", "PinkyBrain"], capture_output=True)


def restart_service(icon, item):
    subprocess.run(["sc", "stop", "PinkyBrain"], capture_output=True)
    import time
    time.sleep(3)
    subprocess.run(["sc", "start", "PinkyBrain"], capture_output=True)


def quit_app(icon, item):
    icon.stop()


def build_menu(status: str) -> Menu:
    """Build context menu based on service status."""
    status_label = f"● Running" if status == "running" else "● Stopped" if status == "stopped" else "● Unknown"

    if status == "running":
        service_menu = Menu(
            MenuItem("Stop", stop_service),
            MenuItem("Restart", restart_service),
        )
    else:
        service_menu = Menu(
            MenuItem("Start", start_service),
        )

    return Menu(
        MenuItem(lambda _: status_label, lambda i, _: None, enabled=False),
        Menu.SEPARATOR,
        MenuItem("Open Web UI", open_web_ui, default=True),
        MenuItem("Service", service_menu),
        Menu.SEPARATOR,
        MenuItem("Open Config", open_config),
        MenuItem("Open Shared Models", open_shared_models),
        MenuItem("Open Logs", open_logs),
        Menu.SEPARATOR,
        MenuItem("Quit", quit_app),
    )


def poll_status(icon: Icon):
    """Background thread: poll service status and update icon."""
    while icon.visible:
        status = get_service_status()
        color = "green" if status == "running" else "red"
        icon.icon = create_icon_image(color)
        icon.menu = build_menu(status)
        icon.title = f"PinkyBrain — {'Running' if status == 'running' else 'Stopped'}"
        import time
        time.sleep(5)


def main():
    # Create shared_models dir if needed
    SHARED_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    status = get_service_status()
    color = "green" if status == "running" else "red"

    icon = Icon(
        "PinkyBrain",
        icon=create_icon_image(color),
        title=f"PinkyBrain — {'Running' if status == 'running' else 'Stopped'}",
        menu=build_menu(status),
    )

    # Start status polling thread
    poller = threading.Thread(target=poll_status, args=(icon,), daemon=True)
    poller.start()

    icon.run()


if __name__ == "__main__":
    main()