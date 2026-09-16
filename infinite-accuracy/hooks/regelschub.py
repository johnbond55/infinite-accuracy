#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regelschub.py — Regeln nachschieben, Kontextlast messen, Ablage anfordern.

Laeuft bei jedem Prompt (UserPromptSubmit):
  1. den Regeltext aus <konfigordner>/regeln.md einspeisen
  2. die Kontextlast der juengsten Antwort aus ihrer usage-Zeile lesen und ab
     ablage_schwelle_token einmal je Ueberschreitung die Ablage anfordern
     (Zettelkasten und Destillat); das laufende Transkript wird dabei gehaertet
  3. nach einer Verdichtung die Kennmarke nachpruefen, falls wiedervorlage.py
     sie noch nicht bestaetigen konnte

Nach einer Verdichtung oder unter der Schwelle wird der Auftrag wieder scharf.
Faellt irgendetwas aus, werden die Regeln trotzdem ausgeliefert.

Begruendungen und Fallen: ../skills/kaskade/doku/regelschub.md
"""
import json
import os
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "skills", "kaskade")
for _p in (HIER, KASKADE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    import konfig
except Exception:                                                 # noqa: BLE001
    konfig = None
try:
    import ernte
except Exception:                                                 # noqa: BLE001
    ernte = None

REGELN_DATEI = "regeln.md"
AUFTRAG_DATEI = "destillat.md"

REGELN_VORGABE = """[Arbeitsregeln — bei jedem Prompt nachgeschoben]
Es ist keine eigene Regeldatei hinterlegt. Lege <konfigordner>/regeln.md an,
dann steht dieser Text hier.
"""

AUFTRAG_VORGABE = """
[infinite-accuracy — Kontext {tok} Token, Ablage faellig (Schwelle {schwelle})]
Userhalt: der Nutzer ist am Zug, du unterbrichst keinen Arbeitsgang. Lege JETZT,
vor der eigentlichen Antwort, ab:
1. Zettelkasten: je Thema dieser Sitzung ein Eintrag (Ausgangslage, Weg,
   Ergebnis; Fakten woertlich: Pfade, Zahlen, Befehle, Entscheidungen) und der
   fortgeschriebene Dossier-Stand. Eingabedatei nach {eingang} schreiben,
   dann: python "{zettel}" ablegen "{eingang}"
   Aufbau der Datei: Skill zettel.
2. Destillat nach {ablage} mit drei Abschnitten:
   was passierte · was gelernt wurde · was offen ist — unter 10.000 Zeichen.
Danach normal antworten und die Ablage in einem Satz nennen. Die Verdichtung
laeuft danach von selbst: der Faden bleibt, Abgelegtes faellt aus dem Kontext
und wird bei Bedarf nachgeschlagen: python "{zettel}" suche <begriffe>"""


def _zahl(name, vorgabe):
    try:
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def _punkt(n):
    return "{:,}".format(int(n)).replace(",", ".")


def zettel_werkzeug():
    return os.path.join(os.path.dirname(HIER), "skills", "zettel", "zettel.py")


def regeln_laden():
    """Der Regeltext des Nutzers, woertlich und gedeckelt."""
    if konfig is None:
        return REGELN_VORGABE
    try:
        return konfig.text(REGELN_DATEI, vorgabe=REGELN_VORGABE,
                           deckel=konfig.zahl("regeln_max_zeichen"))
    except Exception:                                             # noqa: BLE001
        return REGELN_VORGABE


def auftrag_text(tok, ablage, eingang):
    """Der Ablage-Auftrag, mit eingesetzten Werten.

    Ersetzt per str.replace, nie per str.format: Eine geschweifte Klammer im
    Nutzertext wuerde format() zum Absturz bringen.
    """
    text = AUFTRAG_VORGABE
    if konfig is not None:
        try:
            text = konfig.text(AUFTRAG_DATEI, vorgabe=AUFTRAG_VORGABE)
        except Exception:                                         # noqa: BLE001
            pass
    return (text.replace("{tok}", _punkt(tok))
                .replace("{schwelle}", _punkt(_zahl("ablage_schwelle_token", 180000)))
                .replace("{datum}", time.strftime("%Y-%m-%d-%H%M"))
                .replace("{ablage}", ablage)
                .replace("{eingang}", eingang)
                .replace("{zettel}", zettel_werkzeug()))


def destillat_auftrag(tok, ablage):
    """Alter Name, gleiche Wirkung."""
    return auftrag_text(tok, ablage, os.path.join("_eingang", "ablage.json"))


def projekt_verzeichnis(daten):
    """Projektwurzel bestimmen: cwd aus dem Hook, sonst ueber die Konfiguration."""
    cwd = daten.get("cwd")
    if cwd and os.path.isdir(cwd):
        return cwd
    if konfig is not None:
        try:
            return konfig.projekt_wurzel()
        except Exception:                                         # noqa: BLE001
            pass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def aufraeumen(ordner):
    """Hausmeister: Standdateien alter Sitzungen entfernen."""
    try:
        grenze = time.time() - _zahl("aufraeumen_nach_tagen", 14) * 86400
        entfernt = 0
        for eintrag in os.scandir(ordner):
            if entfernt >= 20:
                break
            if not eintrag.is_file():
                continue
            if not eintrag.name.startswith(("zaehler-", "last-")):
                continue
            if eintrag.stat().st_mtime < grenze:
                os.remove(eintrag.path)
                entfernt += 1
    except Exception:                                             # noqa: BLE001
        pass


def tilgen_anstossen(basis, transkript):
    """Das laufende Transkript haerten lassen — ueber ernte.py."""
    if not transkript or ernte is None:
        return 0
    try:
        return ernte.haerten_und_buchen(
            transkript, "kontextlast", ernte.sitzungsordner(basis))
    except Exception:                                             # noqa: BLE001
        return 0


def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass

    text = regeln_laden()
    try:
        roh = sys.stdin.read()
        daten = json.loads(roh) if roh.strip() else {}
        basis = projekt_verzeichnis(daten)
        sid = daten.get("session_id")
        transkript = daten.get("transcript_path")
        if sid and ernte is not None:
            stand = ernte.stand_lesen(basis, sid)
            tok, verdichtet = ernte.kontext_token(transkript)

            marke = stand.get("kennmarke")
            if marke and marke != stand.get("geprueft_marke"):
                # Nicht an `verdichtet` haengen: beim ersten Prompt nach der
                # Verdichtung steht die Zusammenfassung oft noch nicht im
                # Transkript (Rennen), danach meldet kontext_token sie nicht
                # mehr - die Marke bliebe sonst fuer immer ungeprueft.
                zus, zeit = ernte.zusammenfassung_mit_zeit(transkript)
                art, meldung = ernte.kennmarke_pruefen(
                    marke, zus, zeit, stand.get("kennmarke_ts"))
                if art in ("ok", "fehlt"):
                    stand["geprueft_marke"] = marke
                    stand["kennmarke_geprueft"] = art
                if art == "fehlt":
                    text += "\n[infinite-accuracy] " + meldung

            if tok is None or verdichtet or tok < _zahl("ablage_schwelle_token", 180000):
                stand["gemeldet"] = False
            elif not stand.get("gemeldet"):
                datum = time.strftime("%Y-%m-%d-%H%M")
                ablage = os.path.join(ernte.sitzungsordner(basis), datum + ".md")
                eingang = os.path.join(ernte._pfad("zettelkasten", basis),
                                       "_eingang", datum + ".json")
                text += auftrag_text(tok, ablage, eingang)
                getilgt = tilgen_anstossen(basis, transkript)
                if getilgt:
                    text += ("\n[infinite-accuracy] %d Geheimnis(se) aus dem laufenden "
                             "Transkript getilgt (die letzten Zeichen bleiben "
                             "unberuehrt).\n" % getilgt)
                stand["gemeldet"] = True
                stand["auftrag_ts"] = int(time.time())
                stand["destillat"] = ablage
            stand["tok"] = tok
            stand["ts"] = int(time.time())
            ernte.stand_schreiben(basis, sid, stand)
            aufraeumen(ernte.state_ordner(basis))
    except Exception:                                             # noqa: BLE001
        pass

    try:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": text,
            }
        }, ensure_ascii=False))
    except Exception:                                             # noqa: BLE001
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
