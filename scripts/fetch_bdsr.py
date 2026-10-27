"""Scarica le statistiche per comune della Banca Dati Strutture Ricettive (BDSR).

Il Ministero del Turismo pubblica su https://bdsr.ministeroturismo.gov.it/mappa-italia
un CSV con, per ogni comune e sottocategoria ISTAT, il numero di strutture con CIN
verificato, con CIN non verificato, senza CIN e il totale.

Lo script:
  1. scarica il CSV (oppure lo legge da file con --file);
  2. lo normalizza in un formato compatto (codice comune, codice sottocategoria, conteggi);
  3. se i numeri sono cambiati rispetto all'ultima istantanea, salva
     data/bdsr/snapshots/AAAA-MM-GG.csv.gz e aggiorna le tabelle di decodifica.

Uso:
  python scripts/fetch_bdsr.py                 # scarica dal Ministero
  python scripts/fetch_bdsr.py --file x.csv    # usa un CSV già scaricato
  python scripts/fetch_bdsr.py --date 2026-10-27
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import gzip
import io
import json
import sys
from zoneinfo import ZoneInfo

from common import BDSR_DIR, SNAP_DIR, http_get, read_csv, write_csv

API_URL = "https://api-bdsr.ministeroturismo.gov.it/ui/user/downloadCsvDashboard"
SNAP_FIELDS = ["comune", "codice", "cin_verificato", "cin_non_verificato", "senza_cin", "totale"]

# Colonne del CSV ministeriale, nell'ordine in cui arrivano.
COLS = [
    "cod_regione", "regione", "cod_provincia", "provincia", "cod_comune", "comune",
    "cod_macro", "macro", "cod_categoria", "categoria", "cod_sottocategoria", "sottocategoria",
    "cin_verificato", "cin_non_verificato", "senza_cin", "totale",
]


def download_csv_text() -> str:
    raw = http_get(API_URL, accept="application/json")
    payload = json.loads(raw)
    if "csv" not in payload:
        raise RuntimeError(f"Risposta inattesa dal Ministero: chiavi {list(payload)}")
    print(f"  file del Ministero: {payload.get('nomeFile')}")
    return base64.b64decode(payload["csv"]).decode("utf-8-sig")


def parse(text: str):
    """Restituisce (righe istantanea, comuni, categorie)."""
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    if len(header) != len(COLS) or "Totale strutture" not in header[-1]:
        raise RuntimeError(f"Intestazione del CSV cambiata: {header}")

    counts: dict[tuple[str, str], list[int]] = {}
    comuni: dict[str, dict] = {}
    categorie: dict[str, dict] = {}
    skipped = 0
    for row in reader:
        if not row or all(not c for c in row):
            continue
        if len(row) != len(COLS):
            skipped += 1
            continue
        r = dict(zip(COLS, row))
        cod_comune = r["cod_provincia"].zfill(3) + r["cod_comune"].zfill(3)
        codice = r["cod_sottocategoria"].strip()
        if not codice:
            # Alcune righe non hanno la sottocategoria: le teniamo sotto la categoria.
            codice = (r["cod_categoria"] or r["cod_macro"]) + "00"
        try:
            vals = [int(r[k] or 0) for k in ("cin_verificato", "cin_non_verificato", "senza_cin", "totale")]
        except ValueError:
            skipped += 1
            continue
        acc = counts.setdefault((cod_comune, codice), [0, 0, 0, 0])
        for i, v in enumerate(vals):
            acc[i] += v
        comuni[cod_comune] = {
            "codice": cod_comune,
            "comune": r["comune"],
            "cod_provincia": r["cod_provincia"].zfill(3),
            "provincia": r["provincia"],
            "cod_regione": r["cod_regione"].zfill(2),
            "regione": r["regione"],
        }
        if codice not in categorie:
            categorie[codice] = {
                "codice": codice,
                "cod_macro": r["cod_macro"],
                "macro": r["macro"],
                "cod_categoria": r["cod_categoria"],
                "categoria": r["categoria"],
                "descrizione": r["sottocategoria"] or "Sottocategoria non indicata nel file del Ministero",
            }
    if skipped:
        print(f"  attenzione: {skipped} righe con formato inatteso ignorate")
    rows = [
        dict(zip(SNAP_FIELDS, [c, k, *v]))
        for (c, k), v in sorted(counts.items())
    ]
    return rows, comuni, categorie


def snapshot_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SNAP_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def latest_snapshot():
    files = sorted(SNAP_DIR.glob("*.csv.gz"))
    return files[-1] if files else None


def merge_table(path, key: str, new: dict[str, dict]) -> None:
    """Aggiorna una tabella di decodifica tenendo le voci vecchie e aggiungendo le nuove."""
    old = {r[key]: r for r in read_csv(path)} if path.exists() else {}
    old.update(new)
    fields = list(next(iter(old.values())).keys())
    write_csv(path, fields, [old[k] for k in sorted(old)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="CSV del Ministero già scaricato")
    ap.add_argument("--date", help="data dell'istantanea (AAAA-MM-GG); default: oggi a Roma")
    args = ap.parse_args()

    print("BDSR: lettura dati")
    text = open(args.file, encoding="utf-8-sig").read() if args.file else download_csv_text()
    rows, comuni, categorie = parse(text)
    print(f"  {len(rows)} righe, {len(comuni)} comuni, {len(categorie)} sottocategorie")
    if len(comuni) < 100:
        raise RuntimeError("Troppi pochi comuni nel file: probabile risposta incompleta")

    date = args.date or dt.datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    data = snapshot_bytes(rows)
    prev = latest_snapshot()
    if prev is not None and gzip.decompress(prev.read_bytes()) == data:
        print(f"  nessuna novità rispetto a {prev.name}: istantanea non salvata")
    else:
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        out = SNAP_DIR / f"{date}.csv.gz"
        # mtime=0 rende il file identico a parità di contenuto (niente commit inutili).
        out.write_bytes(gzip.compress(data, mtime=0))
        print(f"  salvata {out.relative_to(BDSR_DIR.parent.parent)}")

    merge_table(BDSR_DIR / "comuni.csv", "codice", comuni)
    merge_table(BDSR_DIR / "categorie.csv", "codice", categorie)
    return 0


if __name__ == "__main__":
    sys.exit(main())
