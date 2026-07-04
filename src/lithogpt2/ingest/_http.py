"""Polite bulk fetcher: throttled, resumable, checksummed, robots-aware.

Engineering rules (handoff Section 4.1): respect robots.txt; throttle to at
most one request per 2 seconds per host; identify the project via a User-Agent
carrying Ammar's contact email; make every fetcher resumable via a local
manifest of completed downloads; checksum and never modify raw files.

Uses only the standard library so ingestion has no third-party HTTP
dependency. Raw data is written under data/raw/{source}/ and never mutated.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from . import USER_AGENT

MIN_INTERVAL_S = 2.0  # per-host minimum spacing between requests


@dataclass
class FetchLog:
    ok: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (url, error verbatim)


class PoliteFetcher:
    """Throttled, resumable downloader with a JSON manifest per source."""

    def __init__(
        self,
        source: str,
        raw_root: Path | str = "data/raw",
        min_interval_s: float = MIN_INTERVAL_S,
        respect_robots: bool = True,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.source = source
        self.dest_dir = Path(raw_root) / source
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.dest_dir / "_manifest.json"
        self.min_interval_s = min_interval_s
        self.respect_robots = respect_robots
        self.user_agent = user_agent
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self.manifest: dict[str, dict] = self._load_manifest()

    # ---------------------------------------------------------------- #
    def _load_manifest(self) -> dict[str, dict]:
        if self.manifest_path.exists():
            with self.manifest_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        return {}

    def _save_manifest(self) -> None:
        tmp = self.manifest_path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(self.manifest, fh, indent=2, sort_keys=True)
        tmp.replace(self.manifest_path)

    def _throttle(self, host: str) -> None:
        now = time.monotonic()
        last = self._last_request.get(host)
        if last is not None:
            wait = self.min_interval_s - (now - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        host = parts.netloc
        rp = self._robots.get(host)
        if rp is None:
            rp = RobotFileParser()
            robots_url = f"{parts.scheme}://{host}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
            except Exception:  # noqa: BLE001 - missing robots => allow
                rp = None
            self._robots[host] = rp
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)

    # ---------------------------------------------------------------- #
    def fetch(self, url: str, rel_path: str, log: FetchLog | None = None) -> Path | None:
        """Fetch one URL to data/raw/{source}/{rel_path}, resumable.

        Returns the local path on success or if already present with a matching
        checksum; returns None on failure (recorded verbatim in ``log``).
        """
        log = log if log is not None else FetchLog()
        dest = self.dest_dir / rel_path
        entry = self.manifest.get(url)
        if entry is not None and dest.exists():
            if _sha256(dest) == entry.get("sha256"):
                log.skipped.append(url)
                return dest

        if not self._allowed(url):
            log.failed.append((url, "blocked by robots.txt"))
            return None

        host = urlsplit(url).netloc
        self._throttle(host)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})  # noqa: S310
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                data = resp.read()
            dest.write_bytes(data)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            log.failed.append((url, f"{type(exc).__name__}: {exc}"))
            return None

        digest = _sha256(dest)
        self.manifest[url] = {
            "rel_path": rel_path,
            "sha256": digest,
            "bytes": dest.stat().st_size,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._save_manifest()
        log.ok.append(url)
        return dest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
