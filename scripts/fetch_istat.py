"""Scarica da ISTAT i denominatori per comune: residenti e abitazioni.

Fonti (servizio SDMX di esploradati.istat.it, Censimento permanente):
  - DF_DCSS_FAM_POP_TV_1, indicatore RESPOP_AV: popolazione residente;
  - DF_DCSS_ABITAZIONI_TV_1, indicatori NUM_DW_AV / NUM_OCC_DW_AV / NUM_UNOCC_DW_AV:
    abitazioni totali, occupate da almeno un residente, non occupate.
Per ogni comune si prende l'ultimo anno disponibile.

I dati cambiano una volta l'anno: lo script non riscarica se il file ha meno di
30 giorni, salvo --force.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import sys

from common import ISTAT_DIR, http_get, write_csv

BASE = "https://esploradati.istat.it/SDMXWS/rest/data/IT1,"
CSV_ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0"
POP_URL = BASE + "DF_DCSS_FAM_POP_TV_1/A..RESPOP_AV?lastNObservations=1"
ABIT_URL = (
    BASE
    + "DF_DCSS_ABITAZIONI_TV_1/A..NUM_DW_AV+NUM_OCC_DW_AV+NUM_UNOCC_DW_AV.ALL.TOT.ALL.ALL.TOTAL.TOTAL"
    + "?lastNObservations=1"
)
OUT = ISTAT_DIR / "denominatori.csv"
FIELDS = [
    "codice", "popolazione", "anno_popolazione",
    "abitazioni", "abitazioni_occupate", "abitazioni_non_occupate", "anno_abitazioni",
]


def sdmx_rows(url: str):
    text = http_get(url, accept=CSV_ACCEPT, timeout=600).decode("utf-8-sig")
    for r in csv.DictReader(io.StringIO(text)):
        code = r.get("REF_AREA", "")
        if len(code) == 6 and code.isdigit():
            yield r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if OUT.exists() and not args.force:
        age = dt.datetime.now() - dt.datetime.fromtimestamp(OUT.stat().st_mtime)
        if age.days < 30:
            print(f"ISTAT: {OUT.name} aggiornato {age.days} giorni fa, salto il download")
            return 0

    print("ISTAT: popolazione residente")
    data: dict[str, dict] = {}
    for r in sdmx_rows(POP_URL):
        d = data.setdefault(r["REF_AREA"], {"codice": r["REF_AREA"]})
        d["popolazione"] = int(float(r["OBS_VALUE"]))
        d["anno_popolazione"] = r["TIME_PERIOD"]

    print("ISTAT: abitazioni")
    keys = {"NUM_DW_AV": "abitazioni", "NUM_OCC_DW_AV": "abitazioni_occupate", "NUM_UNOCC_DW_AV": "abitazioni_non_occupate"}
    for r in sdmx_rows(ABIT_URL):
        d = data.setdefault(r["REF_AREA"], {"codice": r["REF_AREA"]})
        d[keys[r["INDICATOR"]]] = int(float(r["OBS_VALUE"]))
        d["anno_abitazioni"] = r["TIME_PERIOD"]

    if len(data) < 7000:
        raise RuntimeError(f"Solo {len(data)} comuni da ISTAT: probabile risposta incompleta")
    rows = [{f: data[c].get(f, "") for f in FIELDS} for c in sorted(data)]
    write_csv(OUT, FIELDS, rows)
    print(f"  salvati {len(rows)} comuni in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
