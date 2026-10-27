"""Prepara i file JSON letti dalla mappa (cartella site/data).

Legge le istantanee BDSR, le tabelle di decodifica e i denominatori ISTAT e scrive:
  site/data/meta.json          date disponibili, categorie, definizioni predefinite
  site/data/comuni.json        nome, provincia, regione e denominatori di ogni comune
  site/data/snap/AAAA-MM-GG.json  conteggi per comune e sottocategoria di ogni istantanea
  site/data/export/ultimi_dati.csv  tabella scaricabile con l'ultima istantanea

Le istantanee già convertite non vengono riscritte, salvo --all.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys

from common import BDSR_DIR, ISTAT_DIR, ROOT, SITE_DATA, SNAP_DIR, read_csv, write_csv, write_json

CONFIG = json.loads((ROOT / "config" / "categorie.json").read_text(encoding="utf-8"))


def excluded(code: str) -> bool:
    return any(code.startswith(p) for p in CONFIG["escludi_prefissi"])


def load_snapshot(path):
    text = gzip.decompress(path.read_bytes()).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def group_of(code: str) -> str:
    if code.startswith("B4"):
        return "B4"
    if code.startswith("C"):
        return "C"
    return "B"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="riconverte tutte le istantanee")
    args = ap.parse_args()

    snaps = sorted(SNAP_DIR.glob("*.csv.gz"))
    if not snaps:
        print("Nessuna istantanea BDSR: eseguire prima scripts/fetch_bdsr.py")
        return 1

    categorie = {r["codice"]: r for r in read_csv(BDSR_DIR / "categorie.csv")}
    codes = sorted(c for c in categorie if not excluded(c))
    index = {c: i for i, c in enumerate(codes)}

    # Istantanee -> JSON compatto: {comune: [[indice_codice, totale, con_cin], ...]}
    dates = []
    for path in snaps:
        date = path.name.split(".")[0]
        dates.append(date)
        out = SITE_DATA / "snap" / f"{date}.json"
        if out.exists() and not args.all and path != snaps[-1]:
            continue
        per_comune: dict[str, list] = {}
        for r in load_snapshot(path):
            code = r["codice"]
            if code not in index:
                continue
            tot = int(r["totale"])
            cin = int(r["cin_verificato"]) + int(r["cin_non_verificato"])
            if tot or cin:
                per_comune.setdefault(r["comune"], []).append([index[code], tot, cin])
        write_json(out, per_comune)

    # Comuni: nome e denominatori
    nomi = {r["codice"]: r for r in read_csv(BDSR_DIR / "comuni.csv")}
    den_path = ISTAT_DIR / "denominatori.csv"
    den = {r["codice"]: r for r in read_csv(den_path)} if den_path.exists() else {}
    anni_pop, anni_abit = set(), set()

    def num(v):
        return int(v) if v not in (None, "") else None

    comuni = {}
    for code in sorted(set(nomi) | set(den)):
        n, d = nomi.get(code, {}), den.get(code, {})
        if d.get("anno_popolazione"):
            anni_pop.add(d["anno_popolazione"])
        if d.get("anno_abitazioni"):
            anni_abit.add(d["anno_abitazioni"])
        comuni[code] = [
            n.get("comune", ""),
            n.get("provincia", ""),
            n.get("regione", ""),
            num(d.get("popolazione")),
            num(d.get("abitazioni")),
            num(d.get("abitazioni_non_occupate")),
        ]
    write_json(SITE_DATA / "comuni.json", comuni)

    categorie_out = []
    for c in codes:
        r = categorie[c]
        categorie_out.append({
            "codice": c,
            "label": CONFIG["etichette"].get(c, r["categoria"]),
            "gruppo": group_of(c),
            "categoria": r["categoria"],
            "descrizione": r["descrizione"],
        })
    meta = {
        "aggiornato": dates[-1],
        "istantanee": dates,
        "codici": codes,
        "categorie": categorie_out,
        "gruppi": CONFIG["gruppi"],
        "preset": CONFIG["preset"],
        "anni": {
            "popolazione": max(anni_pop) if anni_pop else None,
            "abitazioni": max(anni_abit) if anni_abit else None,
        },
    }
    write_json(SITE_DATA / "meta.json", meta, compact=False)

    # Tabella scaricabile dell'ultima istantanea, con nomi e denominatori
    last = load_snapshot(snaps[-1])
    rows = []
    for r in last:
        n = nomi.get(r["comune"], {})
        d = den.get(r["comune"], {})
        rows.append({
            "data": dates[-1],
            "codice_comune": r["comune"],
            "comune": n.get("comune", ""),
            "provincia": n.get("provincia", ""),
            "regione": n.get("regione", ""),
            "codice_sottocategoria": r["codice"],
            "sottocategoria": CONFIG["etichette"].get(r["codice"], categorie.get(r["codice"], {}).get("categoria", "")),
            "cin_verificato": r["cin_verificato"],
            "cin_non_verificato": r["cin_non_verificato"],
            "senza_cin": r["senza_cin"],
            "totale": r["totale"],
            "popolazione": d.get("popolazione", ""),
            "abitazioni": d.get("abitazioni", ""),
            "abitazioni_non_occupate": d.get("abitazioni_non_occupate", ""),
        })
    write_csv(SITE_DATA / "export" / "ultimi_dati.csv", list(rows[0].keys()), rows)

    print(f"Sito: {len(dates)} istantanee, {len(comuni)} comuni, {len(codes)} sottocategorie in mappa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
