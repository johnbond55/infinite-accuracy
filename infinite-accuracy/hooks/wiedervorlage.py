#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wiedervorlage.py — den letzten Stand beim Sitzungsstart wieder vorlegen.

Laeuft bei SessionStart. Reihenfolge: erst aeltere Transkripte haerten, dann
das juengste Destillat, danach — soweit Budget bleibt — das juengste
Rohprotokoll, zuletzt die Meldungen der Hausmeister.

Bei `resume` passiert nichts: dort ist der Verlauf ohnehin da.

Begruendungen und Fallen: ../skills/kaskade/doku/wiedervorlage.md
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


def _zahl(name, vorgabe):
    try:
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def projekt_verzeichnis(daten):
    cwd = daten.get("cwd")
    if cwd and os.path.isdir(cwd):
        return cwd
    if konfig is not None:
        try:
            return konfig.projekt_wurzel()
        except Exception:                                         # noqa: BLE001
            pass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sitzungsordner(basis):
    if konfig is not None:
        try:
            return os.path.join(konfig.konfig_ordner(), "sitzungen")
        except Exception:                                         # noqa: BLE001
            pass
    return os.path.join(basis, ".claude", "infinite-accuracy", "sitzungen")


def juengste(ordner, roh):
    """Juengste Datei: roh=True -> Rohprotokolle, roh=False -> Destillate."""
    try:
        treffer = [e for e in os.scandir(ordner)
                   if e.is_file() and e.name.endswith(".md")
                   and (e.name.endswith("-roh.md") == roh)]
        if not treffer:
            return None
        return max(treffer, key=lambda e: e.stat().st_mtime)
    except Exception:                                             # noqa: BLE001
        return None


def lesen(eintrag, grenze):
    try:
        with open(eintrag.path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
    except Exception:                                             # noqa: BLE001
        return ""
    if len(text) > grenze:
        text = text[:grenze].rstrip() + "\n\n*… gekuerzt, vollstaendig in der Datei*"
    return text


def alter_hinweis(eintrag):
    tage = (time.time() - eintrag.stat().st_mtime) / 86400.0
    if tage >= _zahl("veraltet_nach_tagen", 3):
        return " — **%d Tage alt, Stand vor der Planung pruefen**" % int(tage)
    return ""


def backupleichen(basis):
    """Nur oberste Ebene, damit der Sitzungsstart nicht am ganzen Baum haengt."""
    try:
        return [e.name for e in os.scandir(basis)
                if e.is_file() and (".vor-" in e.name or e.name.endswith(".bak"))]
    except Exception:                                             # noqa: BLE001
        return []


def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass

    teile = []
    try:
        roh = sys.stdin.read()
        daten = json.loads(roh) if roh.strip() else {}
        if (daten.get("source") or "startup") == "resume":
            sys.exit(0)

        basis = projekt_verzeichnis(daten)
        ordner = sitzungsordner(basis)
        gesamt_max = _zahl("wiedervorlage_gesamt", 60000)

        try:
            import ernte
            n, dateien = ernte.alte_transkripte_haerten(
                aktuelles=daten.get("transcript_path"))
            if n:
                teile.append("[infinite-accuracy] %d Geheimnis(se) aus %d aelteren "
                             "Transkript(en) getilgt." % (n, dateien))
        except Exception:                                         # noqa: BLE001
            pass

        d = juengste(ordner, roh=False) if os.path.isdir(ordner) else None
        r = juengste(ordner, roh=True) if os.path.isdir(ordner) else None

        if d:
            text = lesen(d, _zahl("wiedervorlage_destillat", 40000))
            if text:
                teile.append("[infinite-accuracy — juengstes Destillat: %s%s]\n\n%s"
                             % (d.name, alter_hinweis(d), text))

        if r and sum(len(t) for t in teile) < gesamt_max - 800:
            grenze = (_zahl("wiedervorlage_roh", 20000) if teile
                      else _zahl("wiedervorlage_roh_allein", 45000))
            rest = min(grenze, gesamt_max - sum(len(t) for t in teile) - 400)
            text = lesen(r, rest)
            if text:
                teile.append("[infinite-accuracy — juengstes Rohprotokoll: %s%s]\n\n%s"
                             % (r.name, alter_hinweis(r), text))

        try:
            import gedaechtnis
            kurz = gedaechtnis.kurzmeldung(gedaechtnis.memory_dir())
            if kurz:
                teile.append(kurz)
        except Exception:                                         # noqa: BLE001
            pass

        leichen = backupleichen(basis)
        if leichen:
            teile.append("[Hausmeister] %d Sicherungsdatei(en) im "
                         "Projektwurzelverzeichnis: %s — nach bestaetigtem Erfolg "
                         "aufraeumen."
                         % (len(leichen), ", ".join(sorted(leichen)[:6])))
    except Exception:                                             # noqa: BLE001
        pass

    if teile:
        try:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n\n---\n\n".join(teile),
                }
            }, ensure_ascii=False))
        except Exception:                                         # noqa: BLE001
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
