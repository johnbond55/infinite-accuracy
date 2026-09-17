#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""abnahme.py — der maschinelle Zaehler der Kaskade.

Fuehrt Pruefbefehle aus, vergleicht die Ausgabe gegen die Erwartung und zaehlt.
Kein Ermessen. Veraendernde Befehle werden abgewiesen (Heuristik, kein Beweis).

Begruendungen und Fallen: doku/abnahme.md

Eingabe: JSON-Datei mit einer Liste von Pruefpunkten.

    [
      {"punkt": "Datei liegt mit erwartetem Hash auf dem Zielsystem",
       "ziel": "<zielname>",
       "befehl": "sha256sum /opt/x/y.py | cut -d' ' -f1",
       "art": "exakt",
       "erwartet": "a3f2..."},
      {"punkt": "Modul importiert sauber (py_compile ist keine Abnahme)",
       "ziel": "<zielname>",
       "befehl": "python3 -c 'import y'",
       "art": "leer"},
      {"punkt": "alle neun Funktionen vorhanden",
       "ziel": "lokal", "befehl": "grep -c '^def ' y.py",
       "art": "zahl", "erwartet": "9"}
    ]

Ziele: "lokal" oder ein Name aus ziele.json (siehe konfig.py).
Vergleichsarten: exakt | enthaelt | zahl | leer | nichtleer

Aufruf:  abnahme.py <pruefpunkte.json>
Exit:    0 = alle bestanden · 1 = mindestens einer durchgefallen · 2 = Eingabefehler
"""
import json
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
if HIER not in sys.path:
    sys.path.insert(0, HIER)
import konfig                                                    # noqa: E402

VERAENDERND_VERB = re.compile(
    r"(?<![A-Za-z0-9_-])("
    r"rm|mv|cp|dd|truncate|shred|unlink|rmdir|mkdir|touch|ln|"
    r"chmod|chown|chgrp|mkfs|sed\s+-i|tee|"
    r"curl|wget|scp|rsync|"
    r"git\s+(reset|checkout|clean|revert|rebase|merge|pull|push|commit|apply)|"
    r"kill|pkill|killall|systemctl\s+(start|stop|restart|enable|disable|mask)|"
    r"docker\s+(rm|rmi|stop|restart|kill|run|exec|build|pull|push|"
    r"compose\s+(up|down|start|stop|restart|rm|kill|build|pull|create))|"
    r"apt(-get)?\s+(install|remove|purge)|pip\s+install|npm\s+(install|ci)|"
    r"make|"
    r"xargs"
    r")\b", re.I)
FIND_AKTION = re.compile(r"(?<![A-Za-z0-9_-])find\b[^|;]*"
                         r"-(delete|exec|execdir|ok|okdir)\b", re.I)
UMLEITUNG = re.compile(r">{1,2}(?!&)")


def _ohne_quotes(befehl):
    """Ersetzt alles innerhalb von Anfuehrungszeichen durch Leerzeichen."""
    raus, offen = [], None
    for z in befehl:
        if offen:
            raus.append(" ")
            if z == offen:
                offen = None
        elif z in "'\"":
            offen = z
            raus.append(" ")
        else:
            raus.append(z)
    return "".join(raus)


def ist_veraendernd(befehl):
    """True, wenn der Befehl den Zustand anfassen koennte."""
    return bool(VERAENDERND_VERB.search(befehl)
                or FIND_AKTION.search(befehl)
                or UMLEITUNG.search(_ohne_quotes(befehl)))


def ausfuehren(befehl, ziel):
    """Gibt (ausgabe, fehlertext) zurueck. stderr zaehlt zur Ausgabe nur bei 'leer'."""
    if ist_veraendernd(befehl):
        return None, ("Pruefbefehl ist veraendernd — abgewiesen. Eine Pruefung "
                      "darf den Zustand nicht anfassen.")
    if not konfig.ist_fern(ziel):
        if ziel != konfig.LOKAL:
            return None, ("unbekanntes Ziel %r. Bekannt: %s"
                          % (ziel, ", ".join(konfig.namen())))
        kommando, shell = befehl, True
    else:
        basis = konfig.ssh_basis(ziel)
        if basis is None:
            return None, "kein SSH-Schluessel fuer %s gefunden" % ziel
        kommando = basis + [befehl]
        shell = False
    try:
        r = subprocess.run(kommando, shell=shell, capture_output=True,
                           text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as ex:
        return None, "Ausfuehrung fehlgeschlagen: %s" % ex
    return {"out": (r.stdout or "").strip(),
            "err": (r.stderr or "").strip(),
            "code": r.returncode}, None


def vergleichen(ergebnis, art, erwartet):
    """Gibt (erfuellt, begruendung) zurueck."""
    out, err, code = ergebnis["out"], ergebnis["err"], ergebnis["code"]
    art = (art or "exakt").lower()
    if art == "leer":
        if code == 0 and not out and not err:
            return True, "keine Ausgabe, Exit 0"
        return False, "Exit %d, stdout=%r stderr=%r" % (code, out[:120], err[:120])
    if art == "nichtleer":
        return (bool(out), "Ausgabe %r" % out[:120]) if out else (False, "leer")
    if code != 0 and not out:
        return False, "Exit %d, stderr=%r" % (code, err[:160])
    if art == "exakt":
        return (out == (erwartet or "").strip(),
                "ist %r, erwartet %r" % (out[:120], (erwartet or "")[:120]))
    if art == "enthaelt":
        return ((erwartet or "") in out,
                "%r %s in %r" % ((erwartet or "")[:60],
                                 "steht" if (erwartet or "") in out else "FEHLT",
                                 out[:120]))
    if art == "zahl":
        try:
            return (float(out) == float(erwartet),
                    "ist %s, erwartet %s" % (out[:40], erwartet))
        except (TypeError, ValueError):
            return False, "nicht als Zahl lesbar: %r / %r" % (out[:40], erwartet)
    return False, "unbekannte Vergleichsart %r" % art


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        with open(sys.argv[1], "r", encoding="utf-8-sig") as fh:
            punkte = json.load(fh)
    except (OSError, ValueError) as ex:
        print("Pruefpunkte nicht lesbar: %s" % ex)
        return 2
    if not isinstance(punkte, list) or not punkte:
        print("Pruefpunkte muessen eine nichtleere Liste sein.")
        return 2

    bestanden, durchgefallen = [], []
    print("=" * 72)
    for i, p in enumerate(punkte, 1):
        name = p.get("punkt") or "Punkt %d" % i
        ergebnis, fehler = ausfuehren(p.get("befehl", ""), p.get("ziel", "lokal"))
        if fehler:
            durchgefallen.append(name)
            print("%2d. NICHT ERFUELLT  %s\n      -> %s" % (i, name, fehler))
            continue
        ok, warum = vergleichen(ergebnis, p.get("art"), p.get("erwartet"))
        (bestanden if ok else durchgefallen).append(name)
        print("%2d. %s  %s\n      -> %s"
              % (i, "ERFUELLT      " if ok else "NICHT ERFUELLT", name, warum))
    print("=" * 72)

    print("Pruefprotokoll maschinell: %d bestanden, %d durchgefallen, %d gesamt"
          % (len(bestanden), len(durchgefallen), len(punkte)))
    print("STATUS: %s" % ("GRUEN" if not durchgefallen else "ESKALATION"))
    if durchgefallen:
        print("ERGEBNIS: NICHT BEHOBEN — das grosse Modell uebernimmt selbst.")
        print("Offen: " + " | ".join(durchgefallen))
    return 1 if durchgefallen else 0


if __name__ == "__main__":
    sys.exit(main())
