#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""konfig.py — der eine Zugang zur Konfiguration.

Alles Betriebseigene steht in <projektwurzel>/.claude/infinite-accuracy/.
Fehlt die Konfiguration, laeuft alles rein lokal.

Begruendungen und Fallen: doku/konfig.md

ziele.json:
    {
      "<name>": {"ssh": "benutzer@rechner", "keys": ["pfad", ...],
                 "temp": "/tmp/ia-"}
    }
"""
import io
import json
import os
import sys

ORDNER = "infinite-accuracy"
ZIELE_DATEI = "ziele.json"
ZAHLEN_DATEI = "konfig.json"
LOKAL = "lokal"
TEMP_VORGABE = "/tmp/ia-"

VORGABEN = {
    "schwelle_zeichen": 500000,
    "regeln_max_zeichen": 8000,
    "schonfrist_zeichen": 120000,
    "aufraeumen_nach_tagen": 14,
    "veraltet_nach_tagen": 3,
    "wiedervorlage_gesamt": 60000,
    "wiedervorlage_destillat": 40000,
    "wiedervorlage_roh": 20000,
    "wiedervorlage_roh_allein": 45000,
    "protokoll_max_zeilen": 40000,
    "protokoll_min_prompts": 2,
    "protokoll_max_prompts": 25,
    "protokoll_max_promptlaenge": 420,
    "protokoll_max_kommandos": 40,
    "protokoll_max_schluss": 2500,
    "nachlese_mindestalter_sekunden": 300,
    "journal_verwaist_stunden": 24,
    "index_max_zeichen": 12000,
    "eintrag_monster_zeichen": 6000,
}

_zwischenspeicher = {}


def projekt_wurzel():
    """Projektwurzel finden: aufwaerts nach .claude suchen."""
    umgebung = os.environ.get("CLAUDE_PROJECT_DIR")
    if umgebung and os.path.isdir(os.path.join(umgebung, ".claude")):
        return os.path.abspath(umgebung)
    hier = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(hier, ".claude")):
            return hier
        eltern = os.path.dirname(hier)
        if eltern == hier:
            break
        hier = eltern
    return os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def konfig_ordner():
    """Wo die Konfiguration des Nutzers liegt."""
    return os.environ.get("IA_KONFIG") or os.path.join(
        projekt_wurzel(), ".claude", ORDNER)


def ziele():
    """Die konfigurierten Fernziele. Leeres dict, wenn keine Datei da ist."""
    if "ziele" in _zwischenspeicher:
        return _zwischenspeicher["ziele"]
    pfad = os.path.join(konfig_ordner(), ZIELE_DATEI)
    geladen = {}
    if os.path.isfile(pfad):
        try:
            with io.open(pfad, "r", encoding="utf-8") as fh:
                roh = json.load(fh)
            if isinstance(roh, dict):
                geladen = {k: v for k, v in roh.items()
                           if isinstance(v, dict) and k != LOKAL}
            else:
                sys.stderr.write("ia-konfig: %s ist kein Objekt\n" % pfad)
        except (OSError, ValueError) as ex:
            sys.stderr.write("ia-konfig: %s nicht lesbar (%s)\n" % (pfad, ex))
    _zwischenspeicher["ziele"] = geladen
    return geladen


def namen():
    """Alle gueltigen Zielnamen, lokal immer dabei."""
    return sorted(ziele()) + [LOKAL]


def _zahlen():
    if "zahlen" in _zwischenspeicher:
        return _zwischenspeicher["zahlen"]
    pfad = os.path.join(konfig_ordner(), ZAHLEN_DATEI)
    geladen = {}
    if os.path.isfile(pfad):
        try:
            with io.open(pfad, "r", encoding="utf-8") as fh:
                roh = json.load(fh)
            if isinstance(roh, dict):
                geladen = {k: v for k, v in roh.items()
                           if isinstance(v, (int, float)) and not isinstance(v, bool)}
            else:
                sys.stderr.write("ia-konfig: %s ist kein Objekt\n" % pfad)
        except (OSError, ValueError) as ex:
            sys.stderr.write("ia-konfig: %s nicht lesbar (%s)\n" % (pfad, ex))
    _zwischenspeicher["zahlen"] = geladen
    return geladen


def zahl(name):
    """Ein Betriebsparameter. Unbekannte Namen sind ein Programmierfehler."""
    if name not in VORGABEN:
        raise KeyError("unbekannter Konfigurationswert %r" % name)
    return _zahlen().get(name, VORGABEN[name])


def text(datei, vorgabe="", deckel=None):
    """Eine Textdatei aus dem Konfigurationsordner, woertlich.

    Kein .format(), keine Platzhalter — geschweifte Klammern im Nutzertext
    duerfen nichts ausloesen.
    """
    pfad = os.path.join(konfig_ordner(), datei)
    inhalt = vorgabe
    if os.path.isfile(pfad):
        try:
            with io.open(pfad, "r", encoding="utf-8") as fh:
                inhalt = fh.read()
        except OSError as ex:
            sys.stderr.write("ia-konfig: %s nicht lesbar (%s)\n" % (pfad, ex))
    if deckel and len(inhalt) > deckel:
        inhalt = inhalt[:deckel] + "\n[gekuerzt: %s ist laenger als %d Zeichen]" % (
            datei, deckel)
    return inhalt


def tabelle(datei, vorgabe=None):
    """Eine JSON-Tabelle aus dem Konfigurationsordner."""
    pfad = os.path.join(konfig_ordner(), datei)
    if not os.path.isfile(pfad):
        return dict(vorgabe or {})
    try:
        with io.open(pfad, "r", encoding="utf-8") as fh:
            roh = json.load(fh)
        if isinstance(roh, dict):
            return roh
        sys.stderr.write("ia-konfig: %s ist kein Objekt\n" % pfad)
    except (OSError, ValueError) as ex:
        sys.stderr.write("ia-konfig: %s nicht lesbar (%s)\n" % (pfad, ex))
    return dict(vorgabe or {})


def ist_fern(ziel):
    """True, wenn das Ziel ueber ssh angesprochen wird."""
    return ziel in ziele()


def ssh_ziel(ziel):
    """benutzer@rechner fuer ein Fernziel, sonst None."""
    return (ziele().get(ziel) or {}).get("ssh")


def temp_praefix(ziel):
    """Erlaubtes Praefix fuer temporaere Dateien auf einem Fernziel."""
    return (ziele().get(ziel) or {}).get("temp") or TEMP_VORGABE


def schluessel(ziel):
    """Erster existierender SSH-Schluessel des Ziels, sonst None."""
    wurzel = projekt_wurzel()
    for k in (ziele().get(ziel) or {}).get("keys") or []:
        pfad = k if os.path.isabs(k) else os.path.join(wurzel, k)
        if os.path.isfile(pfad):
            return pfad
    return None


def ssh_basis(ziel):
    """Kommandoanfang fuer einen ssh-Aufruf, sonst None."""
    ort, key = ssh_ziel(ziel), schluessel(ziel)
    if not ort or not key:
        return None
    return ["ssh", "-i", key, "-o", "BatchMode=yes", ort]


def zuruecksetzen():
    """Zwischenspeicher leeren. Nur fuer Proben."""
    _zwischenspeicher.clear()


def setzen_fuer_proben(gesetzt):
    """Ziele fuer die Dauer eines Probenlaufs festlegen. Nur fuer pruefstand.py."""
    _zwischenspeicher["ziele"] = dict(gesetzt)


def main():
    print("Konfigurationsordner: %s" % konfig_ordner())
    gefunden = ziele()
    if not gefunden:
        print("Keine Fernziele konfiguriert — nur %r ist moeglich." % LOKAL)
        print("Anlegen: %s" % os.path.join(konfig_ordner(), ZIELE_DATEI))
        return 0
    print("Ziele: %s" % ", ".join(namen()))
    for name in sorted(gefunden):
        key = schluessel(name)
        print("  %-12s %-28s temp=%s  schluessel=%s"
              % (name, ssh_ziel(name) or "?", temp_praefix(name),
                 "gefunden" if key else "FEHLT"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
