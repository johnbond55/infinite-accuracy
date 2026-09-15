#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""haertung.py — Hintergrundlauf nach dem Sitzungsstart, von wiedervorlage.py abgekoppelt.

1. Haerten: aeltere Transkripte des Projekts tilgen. Nur Dateien, die sich seit
   dem letzten Lauf veraendert haben, nie das laufende Transkript, nie Dateien
   juenger als nachlese_mindestalter_sekunden.
2. Nachernte: Transkripte ohne gemeldetes Sitzungsende, die laenger als
   nachernte_ruhe_sekunden ruhen und seit der letzten Ernte gewachsen sind,
   bekommen ein Rohprotokoll <letzte-aktivitaet>-nachernte-<id>-roh.md. Beim
   allerersten Lauf gelten Transkripte aelter als nachernte_fenster_tage als
   bereits geerntet.
3. Hausmeister des Zettelkastens: verwaiste Seiten zaehlen, nichts verschieben.

Aufruf:  haertung.py <transkript-ordner> <aktuelles-transkript> <projektwurzel>
Stand:   <state>/haertung.json   Sperre: <state>/haertung.lock   Log: <state>/haertung.log
Ausgang immer 0.

Begruendungen und Fallen: ../skills/kaskade/doku/wiedervorlage.md
"""
import json
import os
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "skills", "kaskade")
ZETTEL = os.path.join(os.path.dirname(HIER), "skills", "zettel")
for _p in (HIER, KASKADE, ZETTEL):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _zahl(name, vorgabe):
    try:
        import konfig
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def buchen(sitzungen, name, n):
    try:
        with open(os.path.join(sitzungen, "tilgungen.log"), "a", encoding="utf-8") as f:
            f.write("%s  %-12s  %s  %d getilgt\n"
                    % (time.strftime("%Y-%m-%d %H:%M"), "nachlauf", name, n))
    except Exception:                                             # noqa: BLE001
        pass


def nachernten(ernte, pfad, st, basis, sitzungen):
    fakten = ernte.ernten(pfad)
    if len(fakten["prompts"]) < _zahl("protokoll_min_prompts", 2):
        return False
    text, getilgt = ernte.geheimnisse_tilgen(
        ernte.protokoll_bauen(fakten, "Nachernte (kein Sitzungsende gemeldet)", basis))
    if getilgt:
        text += "\n\n*Im Protokoll wurden %d Geheimnisse getilgt.*\n" % getilgt
    name = "%s-nachernte-%s-roh.md" % (
        time.strftime("%Y-%m-%d-%H%M", time.localtime(st.st_mtime)),
        os.path.basename(pfad)[:8])
    ziel = os.path.join(sitzungen, name)
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(text)
    os.utime(ziel, (st.st_mtime, st.st_mtime))
    return True


def zettel_hausmeister(state_dir):
    try:
        import zettel
        seiten = zettel._seiten()
        waisen = [n for n in zettel.waisen(seiten) if zettel._archivierbar(n)]
        with open(os.path.join(state_dir, "zettel-hausmeister.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"ts": int(time.time()), "waisen": waisen}, f, ensure_ascii=False)
    except Exception:                                             # noqa: BLE001
        pass


def main():
    if len(sys.argv) < 4:
        return
    ordner, aktuelles, basis = sys.argv[1:4]
    try:
        import ernte
    except Exception:                                             # noqa: BLE001
        return
    state_dir = ernte.state_ordner(basis)
    sitzungen = ernte.sitzungsordner(basis)
    try:
        os.makedirs(state_dir, exist_ok=True)
        os.makedirs(sitzungen, exist_ok=True)
    except Exception:                                             # noqa: BLE001
        return
    sperre = os.path.join(state_dir, "haertung.lock")
    try:
        if (os.path.exists(sperre) and time.time() - os.path.getmtime(sperre)
                < _zahl("haertung_sperre_minuten", 30) * 60):
            return
        with open(sperre, "w") as f:
            f.write(str(os.getpid()))
    except Exception:                                             # noqa: BLE001
        return

    frisch = _zahl("nachlese_mindestalter_sekunden", 300)
    ruhe_grenze = _zahl("nachernte_ruhe_sekunden", 7200)
    fenster = _zahl("nachernte_fenster_tage", 7) * 86400

    start = time.time()
    log = open(os.path.join(state_dir, "haertung.log"), "a", encoding="utf-8")
    try:
        stand_pfad = os.path.join(state_dir, "haertung.json")
        stand = {}
        try:
            with open(stand_pfad, "r", encoding="utf-8") as f:
                stand = json.load(f)
            if not isinstance(stand, dict):
                stand = {}
        except Exception:                                         # noqa: BLE001
            stand = {}
        erster_lauf = not stand
        jetzt = time.time()
        gehaertet = geerntet = dateien = 0
        for e in sorted(os.scandir(ordner), key=lambda e: e.name):
            if not e.is_file() or not e.name.endswith(".jsonl"):
                continue
            if aktuelles and os.path.abspath(e.path) == os.path.abspath(aktuelles):
                continue
            dateien += 1
            st = e.stat()
            eintrag = stand.get(e.name) or {}
            if jetzt - st.st_mtime >= frisch and (
                    eintrag.get("size") != st.st_size
                    or eintrag.get("mtime") != int(st.st_mtime)):
                n = ernte.transkript_haerten(e.path, schonfrist_zeichen=0)
                n = n[0] if isinstance(n, tuple) else (n or 0)
                if n:
                    gehaertet += n
                    buchen(sitzungen, e.name, n)
                st = os.stat(e.path)
                eintrag["size"] = st.st_size
                eintrag["mtime"] = int(st.st_mtime)
            ruhe = jetzt - st.st_mtime
            if erster_lauf and ruhe > fenster:
                eintrag["geerntet_size"] = st.st_size
            elif ruhe >= ruhe_grenze and st.st_size > (eintrag.get("geerntet_size") or 0):
                try:
                    if nachernten(ernte, e.path, st, basis, sitzungen):
                        geerntet += 1
                    eintrag["geerntet_size"] = st.st_size
                except Exception as ex:                           # noqa: BLE001
                    log.write("%s Nachernte-Fehler %s: %r\n"
                              % (time.strftime("%Y-%m-%d %H:%M"), e.name, ex))
            stand[e.name] = eintrag
        if geerntet:
            ernte.hausmeister(sitzungen)
        with open(stand_pfad, "w", encoding="utf-8") as f:
            json.dump(stand, f)
        zettel_hausmeister(state_dir)
        log.write("%s dateien=%d gehaertet=%d nachgeerntet=%d dauer=%.1fs\n"
                  % (time.strftime("%Y-%m-%d %H:%M"), dateien, gehaertet, geerntet,
                     time.time() - start))
    except Exception as ex:                                       # noqa: BLE001
        try:
            log.write("%s Fehler: %r\n" % (time.strftime("%Y-%m-%d %H:%M"), ex))
        except Exception:                                         # noqa: BLE001
            pass
    finally:
        try:
            log.close()
        except Exception:                                         # noqa: BLE001
            pass
        try:
            os.remove(sperre)
        except Exception:                                         # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
    sys.exit(0)
