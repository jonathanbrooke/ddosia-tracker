import logging
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Downloader:
    def __init__(self, base_url: str, download_dir: Path, delay_between_downloads: float = 1.0):
        self.base_url = base_url.rstrip('/') + '/'
        self.download_dir = Path(download_dir)
        # directories used by the pipeline
        self.pending_dir = self.download_dir.parent / "pending"
        self.processed_dir = self.download_dir.parent / "processed"
        self.delay = float(delay_between_downloads)

        # ensure dirs exist (no race if multiple replicas; mkdir with exist_ok)
        for d in (self.download_dir, self.pending_dir, self.processed_dir):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception:
                logger.debug("Could not ensure directory %s exists", d)

        # requests session with retries
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=(500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

    def check_for_json(self):
        try:
            resp = self.session.get(self.base_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch directory listing %s: %s", self.base_url, e)
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        pre = soup.find("pre") or soup
        links = pre.find_all("a")

        json_hrefs = []
        for a in links:
            href = a.get("href", "")
            # skip parent link and last.json
            if href in ("../", "") or href.lower().endswith("last.json"):
                continue
            parsed = urlparse(href)
            if parsed.scheme or parsed.netloc:
                if href.lower().endswith(".json"):
                    json_hrefs.append(href)
            else:
                if href.lower().endswith(".json"):
                    json_hrefs.append(urljoin(self.base_url, href))

        # unique and sorted for deterministic processing
        for file_url in sorted(set(json_hrefs)):
            try:
                self._download_file(file_url)
            except Exception:
                logger.exception("Error while processing %s", file_url)

    def _download_file(self, file_url: str):
        parsed = urlparse(file_url)
        filename = Path(parsed.path).name

        # defensive skip
        if filename.lower() == "last.json":
            logger.info("Skipping last.json (duplicate)")
            return

        # candidate locations
        pending_dest = self.pending_dir / filename
        processed_dest = self.processed_dir / filename
        downloads_dest = self.download_dir / filename

        # skip if already present in any of the pipeline dirs
        if processed_dest.exists():
            logger.info("Skipping %s — already in processed", filename)
            return
        if pending_dest.exists():
            logger.info("Skipping %s — already in pending", filename)
            return
        if downloads_dest.exists():
            # in case some legacy code used downloads dir
            logger.info("Skipping %s — already in downloads", filename)
            return

        # prepare temp file in pending dir
        tmp = pending_dest.with_suffix(pending_dest.suffix + ".part")

        # avoid colliding with other workers: if a .part exists, assume another worker is active
        if tmp.exists():
            logger.info("Skipping %s — partial exists (another worker?)", filename)
            return

        logger.info("Downloading %s -> %s", file_url, pending_dest)
        try:
            with self.session.get(file_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                # ensure pending dir exists (redundant but defensive)
                self.pending_dir.mkdir(parents=True, exist_ok=True)
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            fh.write(chunk)

            # atomic move into pending
            tmp.replace(pending_dest)
            logger.info("Saved to pending: %s", pending_dest)
            time.sleep(self.delay)
        except requests.RequestException as e:
            logger.error("HTTP error downloading %s: %s", file_url, e)
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    logger.debug("Failed to remove partial file %s", tmp)
        except Exception:
            logger.exception("Unexpected error downloading %s", file_url)
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    logger.debug("Failed to remove partial file %s", tmp)