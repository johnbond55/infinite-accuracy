#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aktualisierung.py — nach einer neuen Fassung auf GitHub fragen und sie installieren.

Gilt fuer Projektinstallationen (<projekt>/.claude/infinite-accuracy/installiert.json).
Wer das Paket ueber das Plugin-System von Claude Code installiert hat, bekommt
Updates von dort.

Aufrufe:
    aktualisierung.py --pruefen [--projekt P]
    aktualisierung.py --installieren <version> [--projekt P] [--erstinstallation]
    aktualisierung.py --installieren <version> --archiv <zipdatei>
Option --ohne-abnahme nur fuer Proben.

Begruendungen und Fallen: ../skills/kaskade/doku/aktualisierung.md
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "skills", "kaskade")
if KASKADE not in sys.path:
    sys.path.insert(0, KASKADE)
try:
    import konfig
except Exception:                                                 # noqa: BLE001
    konfig = None

PAKET = "infinite-accuracy"
URL_VERSION = "https://raw.githubusercontent.com/{repo}/{zweig}/" + PAKET + "/version.json"
URL_ARCHIV = "https://codeload.github.com/{repo}/zip/refs/tags/v{version}"
URL_SEITE = "https://github.com/{repo}"
META = os.path.join(".claude", "infinite-accuracy")


def _zahl(name, vorgabe):
    try:
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def _zeichen(name, vorgabe):
    try:
        return konfig.zeichen(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def version_tupel(text):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def neuer(entfernt, lokal):
    return bool(entfernt and lokal and entfernt > lokal)


def pfad_sicher(name):
    """Darf dieser Archivpfad entpackt werden?"""
    name = str(name)
    if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
        return False
    return ".." not in name.replace("\\", "/").split("/")


def installiert(basis):
    try:
        with open(os.path.join(basis, META, "installiert.json"), "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:                                             # noqa: BLE001
        return None


def _state_datei(basis):
    ordner = os.path.join(basis, META, "state")
    if konfig is not None:
        try:
            ordner = konfig.pfad("state")
        except Exception:                                         # noqa: BLE001
            pass
    os.makedirs(ordner, exist_ok=True)
    return os.path.join(ordner, "aktualisierung.json")


def _anfrage(url, zeitlimit):
    req = urllib.request.Request(url, headers={"User-Agent": "infinite-accuracy"})
    return urllib.request.urlopen(req, timeout=zeitlimit)


def _repo():
    return _zeichen("aktualisierung_repo", "johnbond55/infinite-accuracy")


def entfernt_holen(zeitlimit=None):
    zeitlimit = zeitlimit or _zahl("aktualisierung_zeitlimit_sekunden", 3)
    url = URL_VERSION.format(repo=_repo(), zweig=_zeichen("aktualisierung_zweig", "main"))
    with _anfrage(url, zeitlimit) as r:
        daten = json.loads(r.read().decode("utf-8-sig"))
    if not isinstance(daten, dict) or not version_tupel(daten.get("version")):
        raise ValueError("version.json ohne gueltige Version")
    return daten


def pruefen(basis, erzwingen=False):
    pfad = _state_datei(basis)
    try:
        with open(pfad, "r", encoding="utf-8") as f:
            stand = json.load(f)
        if not isinstance(stand, dict):
            stand = {}
    except Exception:                                             # noqa: BLE001
        stand = {}
    jetzt = time.time()
    intervall = _zahl("aktualisierung_intervall_stunden", 12) * 3600
    if erzwingen or jetzt - float(stand.get("geprueft") or 0) >= intervall:
        try:
            stand["entfernt"] = entfernt_holen()
            stand["fehler"] = ""
        except Exception as ex:                                   # noqa: BLE001
            stand["fehler"] = str(ex)[:200]
        stand["geprueft"] = int(jetzt)
        try:
            with open(pfad, "w", encoding="utf-8") as f:
                json.dump(stand, f, ensure_ascii=False)
        except Exception:                                         # noqa: BLE001
            pass
    lokal = (installiert(basis) or {}).get("version")
    entfernt = stand.get("entfernt") or {}
    return {"installiert": lokal, "entfernt": entfernt,
            "neuer": neuer(version_tupel(entfernt.get("version")), version_tupel(lokal)),
            "fehler": stand.get("fehler") or "", "geprueft": stand.get("geprueft")}


def hinweis(basis):
    """Text fuer den Sitzungsstart, wenn eine neuere Fassung bereitliegt."""
    if _zeichen("aktualisierung", "an").lower() != "an":
        return ""
    if not installiert(basis):
        return ""
    r = pruefen(basis)
    if not r["neuer"]:
        return ""
    e = r["entfernt"]
    groesse = e.get("groesse_bytes")
    groesse_text = ("%d KB" % max(1, groesse // 1024)) if isinstance(groesse, int) and groesse else "unbekannt"
    zeilen = ["[infinite-accuracy — Update verfuegbar]",
              "Installiert: %s · verfuegbar: %s (%s)"
              % (r["installiert"], e.get("version"), e.get("datum") or "ohne Datum")]
    aenderungen = [str(a) for a in (e.get("aenderungen") or [])][:8]
    if aenderungen:
        zeilen.append("Aenderungen:")
        zeilen += ["- " + a for a in aenderungen]
    zeilen += [
        "Quelle: %s (Tag v%s, Archiv von codeload.github.com, Paketgroesse %s)"
        % (URL_SEITE.format(repo=_repo()), e.get("version"), groesse_text),
        "Frage den Nutzer im ersten Satz deiner naechsten Antwort, ob du das Update "
        "installieren sollst — nenne Version, Quelle und Groesse. Erst nach einem "
        "klaren Ja:",
        '  python "%s" --installieren %s --projekt "%s"'
        % (os.path.abspath(__file__), e.get("version"), basis),
        "Das Werkzeug laedt das Archiv, prueft die Pruefsummen, sichert, ersetzt, "
        "faehrt den Pruefstand und spielt bei Rot die vorige Fassung zurueck. Das "
        "Ergebnis als Tabelle melden.",
    ]
    return "\n".join(zeilen)


def _entpacken(zipdatei, ziel):
    with zipfile.ZipFile(zipdatei) as z:
        for name in z.namelist():
            if not pfad_sicher(name):
                raise ValueError("unsicherer Pfad im Archiv: %s" % name)
        z.extractall(ziel)


def paket_finden(ordner):
    for wurzel, dirs, files in os.walk(ordner):
        if (os.path.basename(wurzel) == PAKET and "installieren.py" in files
                and "version.json" in files):
            return wurzel
        if os.path.relpath(wurzel, ordner).count(os.sep) >= 2:
            dirs[:] = []
    return None


def archiv_laden(version, ziel, zeitlimit=120):
    url = URL_ARCHIV.format(repo=_repo(), version=version)
    with _anfrage(url, zeitlimit) as r, open(ziel, "wb") as f:
        shutil.copyfileobj(r, f)
    return url


def installieren(basis, version, erstinstallation=False, archiv=None, ohne_abnahme=False):
    if not version_tupel(version):
        print("Ungueltige Version %r — erwartet wird etwa 2.0.0." % version)
        return 1
    tmp = tempfile.mkdtemp(prefix="ia-aktualisierung-")
    try:
        if archiv:
            zipdatei, herkunft = archiv, archiv
        else:
            zipdatei = os.path.join(tmp, "paket.zip")
            try:
                herkunft = archiv_laden(version, zipdatei)
            except Exception as ex:                               # noqa: BLE001
                print("Laden gescheitert: %s — nichts geaendert." % ex)
                return 1
        print("Archiv: %s (%d Bytes)" % (herkunft, os.path.getsize(zipdatei)))
        entpackt = os.path.join(tmp, "entpackt")
        try:
            _entpacken(zipdatei, entpackt)
        except Exception as ex:                                   # noqa: BLE001
            print("Entpacken abgebrochen: %s — nichts geaendert." % ex)
            return 1
        paket = paket_finden(entpackt)
        if not paket:
            print("Im Archiv liegt kein Paket %s — nichts geaendert." % PAKET)
            return 1
        try:
            with open(os.path.join(paket, "version.json"), "r", encoding="utf-8-sig") as f:
                traegt = json.load(f).get("version")
        except Exception as ex:                                   # noqa: BLE001
            print("version.json im Archiv unlesbar: %s — nichts geaendert." % ex)
            return 1
        if traegt != version:
            print("Archiv traegt Version %s, verlangt war %s — nichts geaendert."
                  % (traegt, version))
            return 1
        befehl = [sys.executable, "-X", "utf8", os.path.join(paket, "installieren.py"),
                  "--projekt", basis, "--quelle", paket,
                  "--erstinstallation" if erstinstallation else "--update"]
        if ohne_abnahme:
            befehl.append("--ohne-abnahme")
        sys.stdout.flush()
        return subprocess.call(befehl)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass
    p = argparse.ArgumentParser(prog="aktualisierung.py")
    p.add_argument("--projekt")
    p.add_argument("--pruefen", action="store_true")
    p.add_argument("--installieren", metavar="VERSION")
    p.add_argument("--erstinstallation", action="store_true")
    p.add_argument("--archiv")
    p.add_argument("--ohne-abnahme", action="store_true")
    args = p.parse_args(argv)
    if args.projekt:
        basis = os.path.abspath(args.projekt)
    elif konfig is not None:
        basis = konfig.projekt_wurzel()
    else:
        basis = os.getcwd()
    if args.installieren:
        return installieren(basis, args.installieren, args.erstinstallation,
                            args.archiv, args.ohne_abnahme)
    r = pruefen(basis, erzwingen=True)
    print("Projekt:     %s" % basis)
    print("Installiert: %s" % (r["installiert"] or "keine Projektinstallation"))
    print("Auf GitHub:  %s" % ((r["entfernt"] or {}).get("version") or "unbekannt"))
    print("Neuer:       %s" % ("ja" if r["neuer"] else "nein"))
    if r["fehler"]:
        print("Fehler:      %s" % r["fehler"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
