import threading
import time
import webbrowser

from python.helpers import dotenv, runtime
import run_ui


def _open_browser_when_ready() -> None:
    host = runtime.get_arg("host") or dotenv.get_dotenv_value("WEB_UI_HOST") or "localhost"
    port = runtime.get_web_ui_port()
    url = f"http://{host}:{port}/"

    # Keep retries short; server startup can take a few seconds.
    for _ in range(30):
        try:
            webbrowser.open(url, new=1)
            return
        except Exception:
            time.sleep(1)


def main() -> None:
    runtime.initialize()
    dotenv.load_dotenv()

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    run_ui.run()


if __name__ == "__main__":
    main()
