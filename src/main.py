import os
import time
import logging
from pathlib import Path
from downloader import Downloader
import shutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def ensure_download_dir(path: Path):
    # If a file exists where we want a directory, move it out of the way
    if path.exists() and not path.is_dir():
        backup = path.with_suffix(path.suffix + ".bak")
        logging.warning("A file exists at %s — moving to %s", path, backup)
        try:
            shutil.move(str(path), str(backup))
        except Exception as e:
            logging.error("Failed to move existing file %s: %s", path, e)
            raise

    # Create directory if missing
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
            logging.info("Created directory: %s", path)
        except PermissionError:
            logging.exception("Permission denied creating directory: %s", path)
            raise

def main():
    url = os.getenv("BASE_URL", "https://www.witha.name/data/")
    download_directory = Path(os.getenv("DOWNLOAD_DIR", "/app/data/downloads"))
    poll_interval = int(os.getenv("DOWNLOADER_POLL_INTERVAL", "300"))
    download_delay = float(os.getenv("DOWNLOAD_DELAY", "1.0"))

    ensure_download_dir(download_directory)

    downloader = Downloader(
        url, download_directory, delay_between_downloads=download_delay
    )

    # simple loop: adjust sleep as desired
    while True:
        try:
            downloader.check_for_json()
            time.sleep(poll_interval)
        except Exception:
            logging.exception("Unexpected error in main loop, sleeping 60s")
            time.sleep(60)


if __name__ == "__main__":
    main()
