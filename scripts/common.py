"""Percorsi e funzioni condivise dagli script della pipeline."""
from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BDSR_DIR = DATA / "bdsr"
SNAP_DIR = BDSR_DIR / "snapshots"
ISTAT_DIR = DATA / "istat"
SITE_DATA = ROOT / "site" / "data"

USER_AGENT = (
    "mappa-affitti-brevi/1.0 (+https://github.com/; dati aperti BDSR/ISTAT)"
)


def http_get(url: str, accept: str = "*/*", retries: int = 4, timeout: int = 180) -> bytes:
    """Scarica un URL con qualche tentativo e attesa crescente tra un tentativo e l'altro."""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as err:  # noqa: BLE001 - riproviamo su qualunque errore di rete
            last_err = err
            wait = 10 * (attempt + 1)
            print(f"  tentativo {attempt + 1} fallito ({err}); riprovo tra {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Impossibile scaricare {url}: {last_err}")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def write_json(path: Path, obj, compact: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
