#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nachlauf.py — SessionEnd-Wrapper fuer das Aufraeum-Journal.

Duenner Wrapper um journal.py. Die Mechanik steht dort, hier wird nichts
nachgebaut.

Loescht die verwaisten Journal-Eintraege (aelter als 24 h). Es wird
ausschliesslich geloescht, was beim Erzeugen registriert wurde: kein Glob, kein
find, eine Datei je rm. Ein Fehler hier darf eine Sitzung nie kippen — deshalb
endet der Hook immer mit 0.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
JOURNAL_DIR = os.path.join(os.path.dirname(HIER), "skills", "kaskade")


def main():
    if not os.path.isfile(os.path.join(JOURNAL_DIR, "journal.py")):
        return 0                      # Skill nicht installiert: still nichts tun
    sys.path.insert(0, JOURNAL_DIR)
    try:
        import journal
    except Exception as ex:           # noqa: BLE001 — Hook darf nie werfen
        print("ia-nachlauf: journal.py nicht ladbar (%s)" % ex)
        return 0
    try:
        import time
        grenze = int(time.time()) - 86400
        offen = [e for e in journal.lesen() if not e.get("weg")]
        verwaist = [e for e in offen if e.get("stempel", 0) < grenze]
        if not verwaist:
            return 0                  # Waechter melden nur Vorfaelle
        journal.aufraeumen(verwaist, "ia-nachlauf (verwaist, aelter als 24 h)")
    except Exception as ex:           # noqa: BLE001
        print("ia-nachlauf: uebersprungen (%s)" % ex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
