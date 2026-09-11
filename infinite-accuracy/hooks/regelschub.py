#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regelschub.py — Regeln nachschieben und die Kontextlast messen.

Laeuft bei jedem Prompt (UserPromptSubmit). Zwei Aufgaben:

  1. Den Regeltext aus <konfigordner>/regeln.md als zusaetzlichen Kontext
     einspeisen, damit er mit wachsendem Kontext nicht verblasst.
  2. Die Kontextlast fortschreiben und bei erreichter Schwelle ein Destillat
     anfordern, das laufende Transkript haerten und den Zaehler zuruecksetzen.

Faellt irgendetwas aus, werden die Regeln trotzdem ausgeliefert — sie sind der
Hauptzweck.

Begruendungen und Fallen: ../skills/kaskade/doku/regelschub.md
"""
import json
import os
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "skills", "kaskade")
if KASKADE not in sys.path:
    sys.path.insert(0, KASKADE)
try:
    import konfig
except Exception:                                                 # noqa: BLE001
    konfig = None

REGELN_DATEI = "regeln.md"
DESTILLAT_DATEI = "destillat.md"

REGELN_VORGABE = """[Arbeitsregeln — bei jedem Prompt nachgeschoben]
Es ist keine eigene Regeldatei hinterlegt. Lege <konfigordner>/regeln.md an,
dann steht dieser Text hier.
"""

DESTILLAT_VORGABE = """
[infinite-accuracy — Kontextlast bei rund {tok} Tokens, Schnitt faellig]
Dies ist ein Userhalt: Der Nutzer ist am Zug, du unterbrichst keinen laufenden
Arbeitsgang. Schreibe deshalb JETZT, vor der eigentlichen Antwort, ein Destillat
nach {ablage} mit drei Abschnitten:
  was passierte · was gelernt wurde · was offen ist
Kurz halten (unter 10.000 Zeichen) — Details bleiben in den Projektdateien.
Danach die Frage normal beantworten, das Destillat in einem Satz erwaehnen und
**/compact** vorschlagen — ausdruecklich KEINEN neuen Chat. Der Faden bleibt
bestehen, nur der Kontext wird zusammengefasst; der PreCompact-Hook erntet und
tilgt dabei von selbst. Ausloesen kannst du /compact nicht, das ist ein
Handgriff des Nutzers."""


def _zahl(name, vorgabe):
    try:
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def _ordner(unterordner, basis):
    if konfig is not None:
        try:
            return os.path.join(konfig.konfig_ordner(), unterordner)
        except Exception:                                         # noqa: BLE001
            pass
    return os.path.join(basis, ".claude", "infinite-accuracy", unterordner)


def regeln_laden():
    """Der Regeltext des Nutzers, woertlich und gedeckelt."""
    if konfig is None:
        return REGELN_VORGABE
    try:
        return konfig.text(REGELN_DATEI, vorgabe=REGELN_VORGABE,
                           deckel=konfig.zahl("regeln_max_zeichen"))
    except Exception:                                             # noqa: BLE001
        return REGELN_VORGABE


def destillat_auftrag(zeichen, ablage):
    """Der Schnittauftrag, mit eingesetzten Werten.

    Ersetzt per str.replace, nie per str.format: Eine geschweifte Klammer im
    Nutzertext wuerde format() zum Absturz bringen.
    """
    text = DESTILLAT_VORGABE
    if konfig is not None:
        try:
            text = konfig.text(DESTILLAT_DATEI, vorgabe=DESTILLAT_VORGABE)
        except Exception:                                         # noqa: BLE001
            pass
    tok = "{:,}".format(zeichen // 4).replace(",", ".")
    return (text.replace("{tok}", tok)
                .replace("{datum}", time.strftime("%Y-%m-%d-%H%M"))
                .replace("{ablage}", ablage))


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


def _zeichen_der_zeile(zeile):
    """Wie viel Kontext kostet diese Transkript-Zeile?"""
    try:
        o = json.loads(zeile)
    except Exception:                                             # noqa: BLE001
        return 0
    inhalt = (o.get("message") or {}).get("content")
    if isinstance(inhalt, str):
        return len(inhalt)
    if not isinstance(inhalt, list):
        return 0
    n = 0
    for teil in inhalt:
        if not isinstance(teil, dict):
            continue
        art = teil.get("type")
        if art == "text":
            n += len(str(teil.get("text", "")))
        elif art == "thinking":
            n += len(str(teil.get("thinking", "")))
        elif art in ("tool_use", "tool_result"):
            wert = teil.get("input") if art == "tool_use" else teil.get("content")
            if wert is not None:
                try:
                    n += len(json.dumps(wert, ensure_ascii=False))
                except Exception:                                 # noqa: BLE001
                    n += len(str(wert))
    return n


def kontextlast(basis, session_id, transkript):
    """Fortgeschriebene Kontextlast in Zeichen."""
    if not session_id or not transkript or not os.path.isfile(transkript):
        return None
    ordner = _ordner("state", basis)
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, "last-%s.json" % str(session_id)[:64])

    stand = {"pos": 0, "zeichen": 0}
    if os.path.isfile(pfad):
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                stand.update(json.load(f))
        except Exception:                                         # noqa: BLE001
            pass

    groesse = os.path.getsize(transkript)
    if groesse < stand["pos"]:
        stand = {"pos": 0, "zeichen": 0}

    try:
        with open(transkript, "r", encoding="utf-8", errors="replace") as f:
            f.seek(stand["pos"])
            for zeile in f:
                if zeile.strip():
                    stand["zeichen"] += _zeichen_der_zeile(zeile)
            stand["pos"] = f.tell()
    except Exception:                                             # noqa: BLE001
        return stand.get("zeichen")

    try:
        with open(pfad, "w", encoding="utf-8") as f:
            json.dump({"pos": stand["pos"], "zeichen": stand["zeichen"],
                       "ts": int(time.time())}, f)
    except Exception:                                             # noqa: BLE001
        pass

    aufraeumen(ordner)
    return stand["zeichen"]


def stand_zuruecksetzen(basis, session_id, transkript):
    """Nach einem Schnitt neu zaehlen — ab der aktuellen Position."""
    try:
        pfad = os.path.join(_ordner("state", basis),
                            "last-%s.json" % str(session_id)[:64])
        with open(pfad, "w", encoding="utf-8") as f:
            json.dump({"pos": os.path.getsize(transkript), "zeichen": 0,
                       "ts": int(time.time())}, f)
    except Exception:                                             # noqa: BLE001
        pass


def aufraeumen(ordner):
    """Hausmeister: Zaehlerdateien alter Sitzungen entfernen."""
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
    if not transkript:
        return 0
    try:
        if HIER not in sys.path:
            sys.path.insert(0, HIER)
        import ernte
        return ernte.haerten_und_buchen(
            transkript, "kontextlast", _ordner("sitzungen", basis))
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
        zeichen = kontextlast(basis, sid, transkript)
        if zeichen is not None and zeichen >= _zahl("schwelle_zeichen", 500000):
            ablage = os.path.join(_ordner("sitzungen", basis),
                                  time.strftime("%Y-%m-%d-%H%M") + ".md")
            text += destillat_auftrag(zeichen, ablage)
            getilgt = tilgen_anstossen(basis, transkript)
            if getilgt:
                text += ("\n[infinite-accuracy] %d Geheimnis(se) aus dem laufenden "
                         "Transkript getilgt (die letzten Zeichen bleiben "
                         "unberuehrt).\n" % getilgt)
            stand_zuruecksetzen(basis, sid, transkript)
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
