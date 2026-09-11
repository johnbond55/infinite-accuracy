#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""journal.py — deterministisches Aufraeumen temporaerer Arbeitsdateien.

Eingetragen wird beim Erzeugen, geloescht nur, was in der Liste steht.
Vier Schranken: Pfadschranke, Metazeichenschranke, eine Datei je rm,
Nur-Journal-Loeschung.

Begruendungen und Fallen: doku/journal.md

Aufrufe:
    journal.py --eintragen <pfad> --ziel <zielname|lokal> --auftrag <id>
    journal.py --aufraeumen <auftrag>     ein Auftragsbuendel loeschen
    journal.py --nachlauf                 verwaiste Eintraege (aelter als 24 h)
    journal.py --liste                    offene Eintraege zeigen, nichts aendern
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
if HIER not in sys.path:
    sys.path.insert(0, HIER)
import konfig                                                    # noqa: E402

JOURNAL = os.path.join(konfig.konfig_ordner(), "journal.jsonl")


def erlaubte_praefixe(ziel):
    """Wo temporaere Arbeitsdateien liegen DUERFEN. Alles andere wird abgewiesen."""
    if konfig.ist_fern(ziel):
        return [konfig.temp_praefix(ziel)]
    scratch = os.environ.get("CLAUDE_SCRATCHPAD") or os.path.join(
        tempfile.gettempdir(), "claude")
    return [os.path.normcase(os.path.abspath(scratch)),
            os.path.normcase(os.path.abspath(os.path.join(
                konfig.konfig_ordner(), "temp")))]


META_SERVER = set("*?[]{}$`\"'\\|&;<>()!~ \t\n\r")
META_LOKAL = set("*?[]")


def _hat_metazeichen(pfad, ziel):
    """True, wenn der Pfad ein Zeichen enthaelt, das sein Ziel deutet."""
    verboten = META_SERVER if konfig.ist_fern(ziel) else META_LOKAL
    return any(z in verboten for z in pfad)


def msys_verdacht(pfad, ziel):
    """Erkennt einen von Git Bash umgeschriebenen Serverpfad."""
    if not konfig.ist_fern(ziel):
        return False
    return bool(pfad) and (not pfad.startswith("/") or ":" in pfad[:3])


def pfad_erlaubt(pfad, ziel):
    """True nur, wenn der Pfad unter einem erlaubten Temp-Ort liegt."""
    if not pfad or ".." in pfad.replace("\\", "/").split("/"):
        return False
    if _hat_metazeichen(pfad, ziel):
        return False
    if konfig.ist_fern(ziel):
        if not pfad.startswith("/"):
            return False
        return any(pfad.startswith(p) for p in erlaubte_praefixe(ziel))
    norm = os.path.normcase(os.path.abspath(pfad))
    return any(norm.startswith(p + os.sep) for p in erlaubte_praefixe(ziel))


def lesen():
    if not os.path.isfile(JOURNAL):
        return []
    eintraege = []
    with open(JOURNAL, "r", encoding="utf-8") as fh:
        for zeile in fh:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintraege.append(json.loads(zeile))
            except ValueError:
                continue
    return eintraege


def schreiben(eintraege):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "w", encoding="utf-8") as fh:
        for e in eintraege:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def eintragen(pfad, ziel, auftrag):
    if ziel not in konfig.namen():
        print("ABGEWIESEN: unbekanntes Ziel %r. Bekannt: %s"
              % (ziel, ", ".join(konfig.namen())))
        print("Ziele stehen in %s"
              % os.path.join(konfig.konfig_ordner(), konfig.ZIELE_DATEI))
        return 2
    if msys_verdacht(pfad, ziel):
        print("PFAD VERFAELSCHT: %r ist kein Serverpfad mehr." % pfad)
        print("Git Bash hat ihn umgeschrieben. Der Eintrag waere still falsch, "
              "deshalb wird er abgewiesen — das ist NICHT die Pfadschranke.")
        print("Abhilfe: MSYS_NO_PATHCONV=1 voranstellen, z. B.")
        print("  MSYS_NO_PATHCONV=1 python journal.py --eintragen /tmp/ia-... "
              "--ziel %s --auftrag <id>" % ziel)
        print("oder den Aufruf ueber das PowerShell-Werkzeug fahren.")
        return 3
    if _hat_metazeichen(pfad, ziel):
        print("ABGEWIESEN: %r enthaelt ein Zeichen, das eine Shell deutet." % pfad)
        print("Das ist NICHT die Pfadschranke. Ein Sternchen wuerde aus "
              "'eine Datei je rm' ein Glob-Loeschen machen; ein Semikolon "
              "haengte einen zweiten Befehl an.")
        print("Abhilfe: jede Datei einzeln und woertlich eintragen — keine "
              "Muster, keine Platzhalter.")
        return 2
    if not pfad_erlaubt(pfad, ziel):
        print("ABGEWIESEN: %s liegt nicht unter einem erlaubten Temp-Ort (%s)."
              % (pfad, ", ".join(erlaubte_praefixe(ziel))))
        print("Das ist kein Fehler, sondern die Pfadschranke: fertige "
              "Programmdateien sind absichtlich nicht eintragbar.")
        return 2
    eintraege = lesen()
    for e in eintraege:
        if e.get("pfad") == pfad and e.get("ziel") == ziel and not e.get("weg"):
            print("schon eingetragen: %s (%s)" % (pfad, ziel))
            return 0
    eintraege.append({"pfad": pfad, "ziel": ziel, "auftrag": auftrag,
                      "erzeugt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "stempel": int(time.time())})
    schreiben(eintraege)
    print("eingetragen: %s (%s, Auftrag %s)" % (pfad, ziel, auftrag))
    return 0


def _loeschen_einzeln(eintrag):
    """Genau EINE Datei loeschen. Kein -r, kein Glob. Gibt (ok, meldung)."""
    pfad, ziel = eintrag["pfad"], eintrag["ziel"]
    if not pfad_erlaubt(pfad, ziel):
        return False, "Pfadschranke verletzt (Eintrag ignoriert): %s" % pfad
    if not konfig.ist_fern(ziel):
        try:
            if os.path.isdir(pfad):
                return False, "ist ein Verzeichnis, wird nicht geloescht: %s" % pfad
            if os.path.exists(pfad):
                os.remove(pfad)
                return True, "geloescht: %s" % pfad
            return True, "war schon weg: %s" % pfad
        except OSError as ex:
            return False, "FEHLER %s: %s" % (pfad, ex)
    basis = konfig.ssh_basis(ziel)
    if basis is None:
        return False, "kein Schluessel fuer %s — %s bleibt liegen" % (ziel, pfad)
    kommando = basis + ["rm -f -- " + shlex.quote(pfad)]
    try:
        r = subprocess.run(kommando, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as ex:
        return False, "FEHLER ssh %s: %s" % (pfad, ex)
    if r.returncode == 0:
        return True, "geloescht: %s:%s" % (ziel, pfad)
    return False, "FEHLER %s:%s — %s" % (ziel, pfad, (r.stderr or "").strip()[:200])


def aufraeumen(auswahl, was):
    """auswahl: Liste von Eintraegen. Gibt Anzahl (ok, fehler) zurueck."""
    if not auswahl:
        print("nichts aufzuraeumen (%s)." % was)
        return 0, 0
    alle = lesen()
    ok = fehler = 0
    for e in auswahl:
        gelungen, meldung = _loeschen_einzeln(e)
        print("  " + meldung)
        if gelungen:
            ok += 1
            for a in alle:
                if (a.get("pfad") == e.get("pfad")
                        and a.get("ziel") == e.get("ziel")):
                    a["weg"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            fehler += 1
    grenze = int(time.time()) - 7 * 86400
    schreiben([a for a in alle
               if not (a.get("weg") and a.get("stempel", 0) < grenze)])
    print("%s: %d geloescht, %d Fehler." % (was, ok, fehler))
    return ok, fehler


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--eintragen", metavar="PFAD")
    p.add_argument("--ziel", choices=konfig.namen(), default=konfig.LOKAL)
    p.add_argument("--auftrag", default="ohne")
    p.add_argument("--aufraeumen", metavar="AUFTRAG")
    p.add_argument("--nachlauf", action="store_true",
                   help="verwaiste Eintraege aelter als 24 h loeschen")
    p.add_argument("--liste", action="store_true")
    a = p.parse_args()

    if a.eintragen:
        return eintragen(a.eintragen, a.ziel, a.auftrag)

    offen = [e for e in lesen() if not e.get("weg")]

    if a.liste:
        if not offen:
            print("Journal: keine offenen Eintraege.")
            return 0
        print("Journal: %d offene Eintraege" % len(offen))
        for e in offen:
            print("  %-9s %-40s Auftrag %s  %s"
                  % (e.get("ziel"), e.get("pfad"), e.get("auftrag"),
                     e.get("erzeugt")))
        return 0

    if a.aufraeumen:
        return 0 if aufraeumen(
            [e for e in offen if e.get("auftrag") == a.aufraeumen],
            "Auftrag %s" % a.aufraeumen)[1] == 0 else 1

    if a.nachlauf:
        grenze = int(time.time()) - 86400
        aufraeumen([e for e in offen if e.get("stempel", 0) < grenze],
                   "Nachlauf (verwaist, aelter als 24 h)")
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
