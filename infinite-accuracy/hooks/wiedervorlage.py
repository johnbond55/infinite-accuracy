#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wiedervorlage.py — den Stand beim Sitzungsstart und nach jeder Verdichtung vorlegen.

Laeuft bei SessionStart, je nach Quelle:
  resume    nichts — der Verlauf ist da
  compact   Kennmarke pruefen, Regeln, Destillat dieser Sitzung, Karte des
            Zettelkastens, Hinweis zum Weiterarbeiten
  sonst     juengstes Destillat, juengstes Rohprotokoll (soweit Budget), Karte,
            Hausmeister-Meldungen, Update-Hinweis

Haerten aelterer Transkripte und Nachernte laufen abgekoppelt in haertung.py;
der Hook selbst bleibt schnell.

Begruendungen und Fallen: ../skills/kaskade/doku/wiedervorlage.md
"""
import json
import os
import subprocess
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "skills", "kaskade")
ZETTEL = os.path.join(os.path.dirname(HIER), "skills", "zettel")
for _p in (HIER, KASKADE, ZETTEL):
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
    if ernte is not None:
        return ernte.sitzungsordner(basis)
    return os.path.join(basis, ".claude", "infinite-accuracy", "sitzungen")


def state_ordner(basis):
    if ernte is not None:
        return ernte.state_ordner(basis)
    return os.path.join(basis, ".claude", "infinite-accuracy", "state")


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
    pfad = getattr(eintrag, "path", eintrag)
    try:
        with open(pfad, "r", encoding="utf-8-sig", errors="replace") as f:
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


def nachlauf_starten(basis, transkript):
    """haertung.py abgekoppelt starten: eigene Standard-Handles, damit der Hook
    nicht auf das Kind wartet."""
    try:
        skript = os.path.join(HIER, "haertung.py")
        if not transkript or not os.path.isfile(skript):
            return
        state = state_ordner(basis)
        os.makedirs(state, exist_ok=True)
        log = open(os.path.join(state, "haertung.log"), "a", encoding="utf-8")
        args = [sys.executable, "-X", "utf8", skript,
                os.path.dirname(str(transkript)), str(transkript), basis]
        kw = dict(stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True)
        if os.name == "nt":
            kw["creationflags"] = 0x00000208
        else:
            kw["start_new_session"] = True
        subprocess.Popen(args, **kw)
        log.close()
    except Exception:                                             # noqa: BLE001
        pass


def zettel_aufruf():
    return 'python "%s"' % os.path.join(ZETTEL, "zettel.py")


def karte():
    try:
        import zettel
        return zettel.karte_text()
    except Exception:                                             # noqa: BLE001
        return ""


def hausmeister_zettel(basis):
    try:
        with open(os.path.join(state_ordner(basis), "zettel-hausmeister.json"),
                  "r", encoding="utf-8") as f:
            d = json.load(f)
        waisen = d.get("waisen") or []
        if not waisen:
            return ""
        return ("[Hausmeister Zettelkasten] %d verwaiste Seite(n): %s — archivieren "
                "nur mit Freigabe: %s hausmeister --archivieren"
                % (len(waisen), ", ".join(waisen[:6]), zettel_aufruf()))
    except Exception:                                             # noqa: BLE001
        return ""


def aktualisierung_hinweis(basis):
    try:
        import aktualisierung
        return aktualisierung.hinweis(basis)
    except Exception:                                             # noqa: BLE001
        return ""


def nach_verdichtung(daten, basis):
    teile = []
    sid = daten.get("session_id")
    transkript = daten.get("transcript_path")
    stand = ernte.stand_lesen(basis, sid) if (ernte is not None and sid) else {}

    if ernte is not None:
        zus, zeit = ernte.zusammenfassung_mit_zeit(transkript)
        art, meldung = ernte.kennmarke_pruefen(
            stand.get("kennmarke"), zus, zeit, stand.get("kennmarke_ts"))
        if sid and art in ("ok", "fehlt"):
            stand["geprueft_marke"] = stand.get("kennmarke")
            stand["kennmarke_geprueft"] = art
            ernte.stand_schreiben(basis, sid, stand)
    else:
        meldung = "ernte.py nicht ladbar — Kennmarke nicht pruefbar."
    teile.append("[infinite-accuracy — nach der Verdichtung] " + meldung)

    try:
        import regelschub
        teile.append(regelschub.regeln_laden())
    except Exception:                                             # noqa: BLE001
        pass

    pfad = stand.get("destillat")
    if pfad and os.path.isfile(pfad):
        text = lesen(pfad, _zahl("verdichtung_destillat_max", 12000))
        if text:
            teile.append("[infinite-accuracy — Destillat dieser Sitzung: %s]\n\n%s"
                         % (pfad, text))

    k = karte()
    if k:
        teile.append("[infinite-accuracy — Karte des Zettelkastens]\n" + k)

    teile.append("[infinite-accuracy] Setze die laufende Aufgabe fort. Frueheres "
                 "nicht raten, sondern nachschlagen: %s suche <begriffe>, dann "
                 "%s lies <seite oder thema>." % (zettel_aufruf(), zettel_aufruf()))
    return teile


def beim_start(daten, basis):
    teile = []
    ordner = sitzungsordner(basis)
    gesamt_max = _zahl("wiedervorlage_gesamt", 60000)

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

    k = karte()
    if k:
        teile.append("[infinite-accuracy — Karte des Zettelkastens]\n" + k)

    try:
        import gedaechtnis
        kurz = gedaechtnis.kurzmeldung(gedaechtnis.memory_dir())
        if kurz:
            teile.append(kurz)
    except Exception:                                             # noqa: BLE001
        pass

    hz = hausmeister_zettel(basis)
    if hz:
        teile.append(hz)

    leichen = backupleichen(basis)
    if leichen:
        teile.append("[Hausmeister] %d Sicherungsdatei(en) im "
                     "Projektwurzelverzeichnis: %s — nach bestaetigtem Erfolg "
                     "aufraeumen."
                     % (len(leichen), ", ".join(sorted(leichen)[:6])))

    akt = aktualisierung_hinweis(basis)
    if akt:
        teile.append(akt)
    return teile


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
        quelle = daten.get("source") or "startup"
        if quelle == "resume":
            sys.exit(0)
        basis = projekt_verzeichnis(daten)
        nachlauf_starten(basis, daten.get("transcript_path"))
        if quelle == "compact":
            teile = nach_verdichtung(daten, basis)
        else:
            teile = beim_start(daten, basis)
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
