# Atlante affitti brevi

Mappa interattiva dei comuni italiani con il numero di alloggi turistici registrati nella
**Banca dati strutture ricettive (BDSR)** del Ministero del Turismo, cioè le unità che hanno
o dovrebbero avere il **CIN** (Codice identificativo nazionale), messo in rapporto con
residenti e abitazioni ISTAT.

Il repository si aggiorna da solo: ogni giorno GitHub Actions scarica i dati del Ministero
e, quando sono cambiati, salva una nuova istantanea. Così lo storico si allunga settimana
dopo settimana e la mappa permette di tornare a ogni data salvata.

## Che cosa mostra

Per ogni comune la mappa calcola una di tre misure, ognuna con la sua scala di colore:

| Misura | Formula | Colore |
|---|---|---|
| Ogni 1.000 residenti | unità ÷ residenti × 1.000 | viola |
| % sulle abitazioni | unità ÷ abitazioni totali × 100 | arancio |
| % sulle abitazioni non occupate | unità ÷ abitazioni senza residenti × 100 | verde acqua |

Le unità si possono contare in tre modi: **tutte le registrate**, **solo con CIN**
(verificato o in verifica) oppure **solo senza CIN**.

Si possono scegliere le sottocategorie ISTAT da contare, una per una, oppure usare due
definizioni pronte:

- **Ampia**: B403, B404, B405, B407, C101, C201, C202, C203, C204. Tutto l'extralberghiero
  nelle case: appartamenti, camere e B&B, gestiti come impresa o da privati.
- **Stretta**: B404, B405, C202, C203, C204. Solo abitazioni intere, senza camere e B&B.

Alberghi (categoria A) e agriturismi (B5) sono esclusi. Le definizioni si cambiano in
[`config/categorie.json`](config/categorie.json).

Cliccando un comune si vedono i conteggi, le tre misure, il dettaglio per sottocategoria e
l'andamento nel tempo.

## Fonti

| Dato | Fonte | Aggiornamento |
|---|---|---|
| Strutture per comune e sottocategoria, con e senza CIN | Ministero del Turismo, BDSR, "BDSR in numeri" (https://bdsr.ministeroturismo.gov.it/mappa-italia) | circa settimanale |
| Popolazione residente | ISTAT, Censimento permanente, `DF_DCSS_FAM_POP_TV_1` | annuale |
| Abitazioni totali, occupate e non occupate | ISTAT, Censimento permanente, `DF_DCSS_ABITAZIONI_TV_1` | annuale |
| Confini comunali | ISTAT, tramite [geojson-italy](https://github.com/guglielmo/geojson-italy), edizione 1° gennaio 2025 | fisso |

## Come pubblicarlo su GitHub

1. Crea un nuovo repository pubblico su GitHub (per esempio `atlante-affitti-brevi`).
2. Carica tutti i file di questa cartella, comprese le cartelle nascoste `.github`.
   Da riga di comando:
   ```sh
   git init
   git add .
   git commit -m "Prima versione"
   git branch -M main
   git remote add origin https://github.com/TUO-UTENTE/atlante-affitti-brevi.git
   git push -u origin main
   ```
3. Su GitHub apri **Settings → Pages** e in **Source** scegli **GitHub Actions**.
4. Apri **Actions → Aggiorna dati e mappa → Run workflow** per lanciare il primo
   aggiornamento a mano. Dopo qualche minuto la mappa è online all'indirizzo
   `https://TUO-UTENTE.github.io/atlante-affitti-brevi/`.

Da quel momento il workflow gira da solo ogni giorno.

## Come funziona

```
scripts/fetch_bdsr.py   scarica il CSV del Ministero, salva data/bdsr/snapshots/AAAA-MM-GG.csv.gz se è cambiato
scripts/fetch_istat.py  scarica residenti e abitazioni in data/istat/denominatori.csv (al massimo una volta al mese)
scripts/build_site.py   prepara i JSON letti dalla mappa in site/data/
site/index.html         la mappa (Leaflet + TopoJSON, nessun server necessario)
```

Lo storico vive nel repository: ogni istantanea è un file compresso di circa 200 KB, con
una riga per comune e sottocategoria (CIN verificato, CIN non verificato, senza CIN,
totale). Si possono usare anche senza la mappa.

Per provarlo sul proprio computer servono solo Python 3.10 o successivo e un browser:

```sh
python scripts/fetch_bdsr.py
python scripts/fetch_istat.py
python scripts/build_site.py
python -m http.server -d site 8000   # poi apri http://localhost:8000
```

## Limiti da conoscere

- **Si contano unità registrate, non annunci online.** Chi affitta senza essersi mai
  registrato non compare. Per stimare il sommerso bisogna confrontare questi numeri con gli
  annunci attivi sulle piattaforme.
- **Le sottocategorie sono nazionali, ma ogni regione decide dove mettere le proprie
  tipologie.** La Liguria, per esempio, registra quasi tutti gli appartamenti dei privati
  (AAUT con codice CITRA) come C204 "altre locazioni", altre regioni potrebbero usare C202.
  Per confrontare regioni diverse conviene la definizione ampia.
- **Provincia di Bolzano**: non alimenta la BDSR, quindi i suoi comuni risultano senza dati.
- **Anni diversi**: i dati BDSR sono settimanali, quelli ISTAT annuali (popolazione e
  abitazioni dell'ultimo anno disponibile, in genere 2023 o 2024).
- **Codici dei comuni**: la BDSR usa ancora i codici ISTAT precedenti alla riforma delle
  province sarde del 1° gennaio 2026, come i confini usati qui. Se il Ministero passerà ai
  nuovi codici, i comuni sardi andranno ricollegati con il codice catastale.
- **Comuni piccolissimi**: pochi alloggi su poche case danno percentuali molto alte.
- Se il sito del Ministero blocca le richieste da GitHub, il workflow fallisce e GitHub
  avvisa per email. In quel caso si può lanciare `python scripts/fetch_bdsr.py` dal proprio
  computer e fare il push dei file in `data/`.
- GitHub sospende i workflow pianificati dei repository senza attività per 60 giorni; i
  commit settimanali dei dati di solito bastano a tenerlo attivo.

## Licenze

Il codice è rilasciato con licenza MIT (vedi `LICENSE`). I dati ISTAT e i confini sono
distribuiti con licenza CC BY 4.0: citare ISTAT come fonte. I dati BDSR sono pubblicati dal
Ministero del Turismo: citare il Ministero come fonte.
