#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefstand.py — Proben gegen die eigenen Schranken.

Faehrt die Schranken dieses Pakets gegen Proben, deren Ausgang vorher
feststeht — in beiden Richtungen: was durchgehen muss und was blocken muss.
Verdichtung, Zettelkasten und Installer werden Ende-zu-Ende in temporaeren
Ordnern geprobt. Im Quell-Repository vergleicht eine Gruppe den Paketordner
mit dem Archiv des Tags v<version.json> - lokal per git, nur lesend.

Begruendungen und Fallen: doku/pruefstand.md

Aufruf:  pruefstand.py          alle Proben
         pruefstand.py --rot    Gegenprobe, kehrt jede Erwartung um;
                                dieser Lauf muss fehlschlagen
Exit:    0 = alle bestanden · 1 = mindestens eine Probe durchgefallen
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import abnahme                                                    # noqa: E402
import journal                                                    # noqa: E402
import konfig                                                     # noqa: E402

PROBE_ZIEL = "probeziel"
EUPL_DE_SHA256 = "208705beb6df6c418b821f73b2cf192d9d5c6837a1a59391a261c7abe2fb0dce"
LIZENZTEXTE = ("LICENSE", "EUPL-1.2-DE.txt")
PROBE_ZIELE = {PROBE_ZIEL: {"ssh": "nutzer@rechner.invalid",
                            "keys": [], "temp": "/tmp/ia-"}}
BOM = b"\xef\xbb\xbf"
konfig.setzen_fuer_proben(PROBE_ZIELE)


def _scratch():
    """Ein erlaubter lokaler Temp-Ort, so wie journal.py ihn bestimmt."""
    return journal.erlaubte_praefixe("lokal")[0]


def _wirft(f):
    try:
        f()
        return False
    except Exception:                                             # noqa: BLE001
        return True


def _hookordner():
    for kandidat in (os.path.join(os.path.dirname(os.path.dirname(HIER)), "hooks"),
                     os.path.join(os.path.dirname(HIER), "hooks")):
        if os.path.isfile(os.path.join(kandidat, "ernte.py")):
            return kandidat
    return None


def _modul(name):
    ordner = _hookordner()
    if not ordner:
        return None
    if ordner not in sys.path:
        sys.path.insert(0, ordner)
    try:
        return __import__(name)
    except Exception:                                             # noqa: BLE001
        return None


def _hooks_laden():
    """ernte.py, regelschub.py und gedaechtnis.py, falls sie neben dem Skill liegen."""
    ernte, regelschub, ged = _modul("ernte"), _modul("regelschub"), _modul("gedaechtnis")
    if ernte is None or regelschub is None or ged is None:
        return None, None, None
    return ernte, regelschub, ged


def _hook_prozess(pfad, eingabe, umgebung):
    env = dict(os.environ)
    env.update(umgebung)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", pfad], input=json.dumps(eingabe),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           encoding="utf-8", errors="replace", env=env, timeout=120)
        return p.returncode, p.stdout, p.stderr
    except Exception as ex:                                       # noqa: BLE001
        return -1, "", str(ex)


@contextlib.contextmanager
def _konfig_umgelenkt(ordner):
    """Konfiguration fuer die Dauer des Blocks aus ordner - im Pruefstand und in Hook-Prozessen."""
    alt = os.environ.get("IA_KONFIG")
    os.environ["IA_KONFIG"] = ordner
    konfig.zuruecksetzen()
    try:
        yield
    finally:
        if alt is None:
            os.environ.pop("IA_KONFIG", None)
        else:
            os.environ["IA_KONFIG"] = alt
        konfig.zuruecksetzen()
        konfig.setzen_fuer_proben(PROBE_ZIELE)


def _datei_zustand(pfad):
    """(mtime_ns, Groesse, Inhalt) oder None - Beleg, dass eine Datei unberuehrt bleibt."""
    try:
        st = os.stat(pfad)
        with open(pfad, "rb") as f:
            return st.st_mtime_ns, st.st_size, f.read()
    except OSError:
        return None


def _liegt_unter(pfad, ordner):
    try:
        a = os.path.normcase(os.path.realpath(pfad))
        b = os.path.normcase(os.path.realpath(ordner))
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


def _bytes_schreiben(pfad, inhalt):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "wb") as f:
        f.write(inhalt)


def _skript(pfad, *argumente):
    """(rc, Ausgabe) eines Skripts im eigenen Prozess, ohne Eingabe."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", pfad] + list(argumente),
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, encoding="utf-8", errors="replace",
                           env=env, timeout=120)
        return p.returncode, p.stdout
    except Exception as ex:                                       # noqa: BLE001
        return -1, str(ex)


def _erfuellt(ist, soll, rot=False):
    """Erwartungen sind Wahrheitswerte - alles andere gilt als nicht erfuellt."""
    if not isinstance(soll, bool):
        return False
    return bool(ist) == (soll != rot)


def _konfigproben():
    """Proben fuer den Konfigurationszugang."""
    p = []
    p.append(("unbekannter Konfigurationswert wirft",
              _wirft(lambda: konfig.zahl("gibtsnicht")), True,
              "ein Tippfehler im Namen darf nicht still eine 0 ergeben"))
    p.append(("unbekannter Schalter wirft",
              _wirft(lambda: konfig.zeichen("gibtsnicht")), True,
              "ein Tippfehler im Namen darf nicht still die Vorgabe ergeben"))
    p.append(("unbekannter Ablageort wirft",
              _wirft(lambda: konfig.pfad("gibtsnicht")), True,
              "ein Tippfehler darf nicht still irgendwohin schreiben"))
    p.append(("bekannter Wert kommt aus der Vorgabe",
              konfig.zahl("riegel_bis_token") == konfig.VORGABEN["riegel_bis_token"],
              True, "ohne Eintrag in konfig.json gelten die eingebauten Werte"))
    p.append(("Ablageorte sind absolut",
              all(os.path.isabs(konfig.pfad(n)) for n in konfig.PFADE), True,
              "relative Orte haengen am Arbeitsverzeichnis des Hooks"))
    p.append(("Textvorgabe greift, wenn keine Datei da ist",
              konfig.text("gibtsnicht.md", vorgabe="VORGABE") == "VORGABE", True,
              "das Paket muss ohne Konfiguration laufen"))
    p.append(("Textdeckel kuerzt",
              len(konfig.text("gibtsnicht.md", vorgabe="x" * 500, deckel=100)) < 200,
              True, "die Regeldatei kostet bei JEDEM Prompt Kontext"))
    p.append(("Tabellenvorgabe greift",
              konfig.tabelle("gibtsnicht.json", vorgabe={"a": 1}) == {"a": 1}, True,
              "fehlende Tabelle darf nicht zum Absturz fuehren"))

    tmp = tempfile.mkdtemp(prefix="ia-bom-")
    try:
        _bytes_schreiben(os.path.join(tmp, konfig.ZAHLEN_DATEI),
                         BOM + b'{"riegel_bis_token": 123456}')
        _bytes_schreiben(os.path.join(tmp, konfig.ZIELE_DATEI),
                         BOM + b'{"bomziel": {"ssh": "nutzer@bom.invalid", "keys": []}}')
        _bytes_schreiben(os.path.join(tmp, "tabelle.json"), BOM + b'{"a": 1}')
        _bytes_schreiben(os.path.join(tmp, "text.md"), BOM + "Regel ä".encode("utf-8"))
        with _konfig_umgelenkt(tmp):
            p.append(("konfig.json mit BOM wird gelesen",
                      konfig.zahl("riegel_bis_token") == 123456, True,
                      "Windows-Editor und PowerShell schreiben ein BOM - mit utf-8 "
                      "galten still die Vorgaben"))
            p.append(("ziele.json mit BOM wird gelesen",
                      konfig.ist_fern("bomziel"), True,
                      "sonst verschwinden alle Fernziele ohne Meldung im Chat"))
            p.append(("Tabelle mit BOM wird gelesen",
                      konfig.tabelle("tabelle.json", vorgabe={}) == {"a": 1}, True,
                      "register-texte.json fiel still auf die Vorgabe zurueck"))
            p.append(("Text mit BOM ohne unsichtbares Zeichen",
                      konfig.text("text.md") == "Regel ä", True,
                      "regeln.md begann sonst mit U+FEFF"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    p.append(("nach der Umlenkung gilt wieder die Probenkonfiguration",
              konfig.ist_fern(PROBE_ZIEL) and "bomziel" not in konfig.namen(), True,
              "eine Probe darf die folgenden nicht mit ihrer Konfiguration verfaelschen"))
    return p


def _hookproben():
    """Proben fuer die Tilgung — nur wenn die Hooks neben dem Skill liegen."""
    ernte, regelschub, ged = _hooks_laden()
    if ernte is None:
        return [("Hooks vorhanden (uebersprungen)", True, True,
                 "ohne hooks/-Ordner gibt es nichts zu pruefen")]
    p = []
    for probe, art in [("sk-" + "a" * 40, "API-Schluessel"),
                       ("AKIA" + "B" * 16, "AWS-Schluessel"),
                       ("ghp_" + "c" * 36, "GitHub-Token"),
                       ("xoxb-" + "1" * 20, "Slack-Token"),
                       ('"api_key": "' + "d" * 20 + '"', "Feldwert"),
                       ("API_TOKEN=" + "e" * 20, "Umgebungsvariable"),
                       ("Bearer " + "f" * 30, "Bearer-Token")]:
        neu, n = ernte.geheimnisse_tilgen(probe)
        p.append(("Geheimnis erkannt: %s" % art, n >= 1, True,
                  "ein unerkanntes Geheimnis wandert ins Protokoll"))
        p.append(("Wert ist weg: %s" % art, probe.split("=")[-1][-12:] in neu, False,
                  "getilgt heisst getilgt"))
    p.append(("harmloser Satz bleibt unberuehrt",
              ernte.geheimnisse_tilgen("Das Passwort steht in der .env-Datei.")[1] == 0,
              True, "Fliesstext ist keine Zuweisung — Fehlalarm zerstoert Protokolle"))
    p.append(("Feldname bleibt nach dem Tilgen stehen",
              "api_key" in ernte.geheimnisse_tilgen('"api_key": "' + "x" * 20 + '"')[0],
              True, "ohne Feldname ist der Zusammenhang verloren"))
    p.append(("Schonfrist 0 gibt alles frei",
              ernte._schonfrist_grenze(["abc", "def"], 0) == 2, True,
              "SessionStart haertet aeltere Transkripte vollstaendig"))
    p.append(("Schonfrist schuetzt das Ende",
              ernte._schonfrist_grenze(["a" * 100, "b" * 100], 150) == 0, True,
              "der lebende Chat darf nicht angefasst werden"))
    p.append(("Destillatauftrag ueberlebt geschweifte Klammern",
              "{eigene}" in regelschub.destillat_auftrag(4, "x{eigene}y"), True,
              "str.format wuerde hier abstuerzen — deshalb replace"))

    tmp = tempfile.mkdtemp(prefix="ia-tilgung-")
    try:
        pfad = os.path.join(tmp, "t.jsonl")
        zeilen = [json.dumps({"message": {"content": "alt sk-" + "q" * 40}}),
                  json.dumps({"message": {"content": "Trenner\u2028bleibt"}}, ensure_ascii=False)]
        with open(pfad, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(zeilen) + "\n")
        n = ernte.transkript_haerten(pfad, schonfrist_zeichen=0)
        with open(pfad, "r", encoding="utf-8", newline="") as f:
            danach = f.read()
        p.append(("Tilgung im Transkript greift", n == 1, True,
                  "Geheimnis in einer alten Zeile"))
        p.append(("Zeilentrenner U+2028 zerlegt keine Zeile",
                  danach.count("\n") == 2 and all(json.loads(z) for z in danach.split("\n") if z),
                  True, "splitlines() trennte dort und zerbrach das JSON des Transkripts"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for ph in ["{env:KEY}", "$MEINVAR", "<dein-token>", "changeme", "xxxxx"]:
        p.append(("Platzhalter loest keinen Alarm aus: %s" % ph,
                  bool(ged.PLATZHALTER.match(ph)), True,
                  "eine Warnung, die nie stimmt, wird ignoriert"))
    p.append(("echter Wert gilt nicht als Platzhalter",
              bool(ged.PLATZHALTER.match("A7f3K9x2Lm4Qp8Zw")), False,
              "sonst uebersieht die Meldung genau das, was sie finden soll"))
    return p


def _transkript(ordner, name, zeilen):
    pfad = os.path.join(ordner, name)
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        for z in zeilen:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")
    return pfad


def _antwort(tokens):
    return {"type": "assistant",
            "message": {"content": [{"type": "text", "text": "ok"}],
                        "usage": {"input_tokens": 1, "cache_creation_input_tokens": 0,
                                  "cache_read_input_tokens": tokens - 1}}}


def _verdichtungsproben():
    """Ablage-Auftrag, Riegel, Anweisung, Kennmarke — bis zum echten Hook-Prozess."""
    ernte, regelschub, _ = _hooks_laden()
    if ernte is None:
        return [("Verdichtung (uebersprungen)", True, True,
                 "ohne hooks/-Ordner gibt es nichts zu pruefen")]
    p = []
    tmp = tempfile.mkdtemp(prefix="ia-verdichtung-")
    try:
        t1 = _transkript(tmp, "a.jsonl", [_antwort(150000)])
        tok, verdichtet = ernte.kontext_token(t1)
        p.append(("Kontext kommt aus der usage-Zeile", tok == 150000, True,
                  "Zeichen zu zaehlen verfehlte das Verhaeltnis um bis zu Faktor 14"))
        p.append(("ohne Verdichtungsmarke nicht verdichtet", verdichtet, False,
                  "sonst wuerde der Auftrag bei jedem Prompt neu scharf"))
        t2 = _transkript(tmp, "b.jsonl",
                         [_antwort(150000), {"type": "system", "subtype": "compact_boundary"}])
        p.append(("Verdichtungsmarke hinter der Antwort wird erkannt",
                  ernte.kontext_token(t2)[1], True,
                  "danach muss der Ablage-Auftrag wieder scharf werden"))

        p.append(("Riegel sperrt automatische Verdichtung ohne Ablage",
                  bool(ernte.riegel_grund("auto", 200000, {})), True,
                  "sonst faellt Unabgelegtes aus dem Kontext"))
        p.append(("Riegel laesst manuelle Verdichtung durch",
                  bool(ernte.riegel_grund("manual", 200000, {})), False,
                  "wer /compact tippt, will verdichten"))
        p.append(("Riegel gibt ueber der Grenze frei",
                  bool(ernte.riegel_grund("auto", 10 ** 7, {})), False,
                  "sonst laeuft das Fenster voll"))
        destillat = os.path.join(tmp, "destillat.md")
        with open(destillat, "w", encoding="utf-8") as f:
            f.write("# Destillat\nInhalt-Probe")
        frisch = {"destillat": destillat, "auftrag_ts": 0}
        p.append(("Riegel gibt nach frischer Ablage frei",
                  bool(ernte.riegel_grund("auto", 200000, frisch)), False,
                  "abgelegt ist abgelegt"))

        anweisung = ernte.verdichtungs_anweisung("ia-probe-1", frisch)
        p.append(("Anweisung traegt die Kennmarke", "ia-probe-1" in anweisung, True,
                  "ohne Kennmarke ist die Uebernahme nicht pruefbar"))
        p.append(("Anweisung traegt das Destillat", "Inhalt-Probe" in anweisung, True,
                  "das Destillat ist der Grundstock der Zusammenfassung"))
        destillat_bom = os.path.join(tmp, "destillat-bom.md")
        _bytes_schreiben(destillat_bom, BOM + b"# Destillat\nInhalt-Probe")
        mit_bom = ernte.verdichtungs_anweisung(
            "ia-probe-1", {"destillat": destillat_bom, "auftrag_ts": 0})
        p.append(("Destillat mit BOM geht ohne BOM in die Anweisung",
                  "\n# Destillat\nInhalt-Probe" in mit_bom and "\ufeff" not in mit_bom,
                  True, "ein mit PowerShell gespeichertes Destillat trug das BOM in die Zusammenfassung"))
        wiedervorlage = _modul("wiedervorlage")
        p.append(("Destillat mit BOM wird beim Sitzungsstart ohne BOM vorgelegt",
                  wiedervorlage is not None
                  and wiedervorlage.lesen(destillat_bom, 1000) == "# Destillat\nInhalt-Probe",
                  True, "sonst beginnt die Vorlage mit einem unsichtbaren Zeichen"))

        t3 = _transkript(tmp, "c.jsonl", [
            _antwort(100),
            {"type": "user", "isCompactSummary": True,
             "message": {"content": "Zusammenfassung [infinite-accuracy Kennmarke ia-probe-1] Rest"}}])
        zus = ernte.letzte_zusammenfassung(t3)
        p.append(("Zusammenfassung wird im Transkript gefunden",
                  zus is not None and "ia-probe-1" in zus, True,
                  "die Kennmarkenpruefung braucht den Text"))
        p.append(("Kennmarke wird bestaetigt",
                  ernte.kennmarke_pruefen("ia-probe-1", zus)[0] == "ok", True,
                  "Regelfall"))
        p.append(("fehlende Kennmarke wird gemeldet",
                  ernte.kennmarke_pruefen("ia-andere", zus)[0] == "fehlt", True,
                  "ein Update von Claude Code darf nicht still alles aushebeln"))
        p.append(("ohne Zusammenfassung heisst unpruefbar, nicht fehlt",
                  ernte.kennmarke_pruefen("ia-probe-1", None)[0] == "unpruefbar", True,
                  "ein Fehlalarm bei jeder Verdichtung wird ignoriert"))

        t4 = _transkript(tmp, "d.jsonl", [
            {"type": "user", "isCompactSummary": True,
             "timestamp": "2026-09-16T05:00:00.000Z",
             "message": {"content": "alte Zusammenfassung [Kennmarke ia-probe-0]"}},
            _antwort(100)])
        zus4, zeit4 = ernte.zusammenfassung_mit_zeit(t4)
        p.append(("Zusammenfassung wird mit ihrer Zeit gelesen",
                  zeit4 is not None and "ia-probe-0" in (zus4 or ""), True,
                  "ohne Zeit ist nicht zu sagen, zu welcher Kennmarke sie gehoert"))
        p.append(("aeltere Zusammenfassung heisst unpruefbar, nicht fehlt",
                  ernte.kennmarke_pruefen("ia-probe-9", zus4, zeit4,
                                          zeit4 + 60)[0] == "unpruefbar", True,
                  "der Riegel schiebt die Verdichtung auf - das ist kein Befund"))
        p.append(("juengere Zusammenfassung ohne Marke bleibt ein Befund",
                  ernte.kennmarke_pruefen("ia-probe-9", zus4, zeit4,
                                          zeit4 - 60)[0] == "fehlt", True,
                  "sonst bliebe ein echter Ausfall der Anweisung unbemerkt"))

        konf = os.path.join(tmp, "konf")
        os.makedirs(konf)
        with open(os.path.join(konf, "konfig.json"), "w", encoding="utf-8") as f:
            json.dump({"pfade": {"sitzungen": os.path.join(tmp, "sitzungen"),
                                 "state": os.path.join(tmp, "state"),
                                 "zettelkasten": os.path.join(tmp, "zk")}}, f)

        proj = os.path.join(tmp, "projekt-kennmarke")
        os.makedirs(os.path.join(proj, ".claude", "state"))
        t5 = _transkript(tmp, "e.jsonl", [
            {"type": "user", "isCompactSummary": True,
             "timestamp": "2026-09-16T06:00:00.000Z",
             "message": {"content":
                         "Zusammenfassung [infinite-accuracy Kennmarke ia-probe-5]"}},
            _antwort(1000)])
        echt_pfad = ernte.stand_pfad(proj, "sid-5")
        echt = _datei_zustand(echt_pfad)
        with _konfig_umgelenkt(konf):
            umgelenkt = ernte.stand_pfad(proj, "sid-5")
            ernte.stand_schreiben(proj, "sid-5",
                                  {"kennmarke": "ia-probe-5", "kennmarke_ts": 1000})
            _hook_prozess(os.path.join(_hookordner(), "regelschub.py"),
                          {"session_id": "sid-5", "transcript_path": t5, "cwd": proj,
                           "hook_event_name": "UserPromptSubmit", "prompt": "x"},
                          {"IA_KONFIG": konf})
            geprueft = ernte.stand_lesen(proj, "sid-5").get("kennmarke_geprueft")
        p.append(("Kennmarke wird auch nach der ersten Antwort noch geprueft",
                  geprueft == "ok", True,
                  "beim ersten Prompt nach der Verdichtung fehlt die Zusammenfassung oft noch"))
        p.append(("Kennmarken-Probe schreibt in den Probenordner",
                  _liegt_unter(umgelenkt, tmp) and not _liegt_unter(echt_pfad, tmp), True,
                  "sonst legt jeder Probenlauf last-sid-5.json im echten Stand an"))
        p.append(("Kennmarken-Probe laesst den echten Stand unberuehrt",
                  _datei_zustand(echt_pfad) == echt, True,
                  "der Pruefstand darf nicht veraendern, was er prueft"))
        p.append(("Ablage-Auftrag ueberlebt geschweifte Klammern",
                  "{eigene}" in regelschub.auftrag_text(200000, "x{eigene}y", "e.json"), True,
                  "str.format wuerde hier abstuerzen"))

        t4 = _transkript(tmp, "d.jsonl", [_antwort(200000)])
        eingabe = {"hook_event_name": "PreCompact", "trigger": "auto",
                   "transcript_path": t4, "session_id": "probe-sitzung", "cwd": tmp}
        rc, aus, _ = _hook_prozess(ernte.__file__, eingabe, {"IA_KONFIG": konf})
        p.append(("PreCompact ohne Ablage endet mit Exit 2", rc == 2, True,
                  "Exit 2 ist das Signal an Claude Code, die Verdichtung aufzuschieben"))
        eingabe["trigger"] = "manual"
        rc, aus, _ = _hook_prozess(ernte.__file__, eingabe, {"IA_KONFIG": konf})
        p.append(("PreCompact manuell gibt die Anweisung aus",
                  rc == 0 and "Kennmarke" in aus, True,
                  "die Standardausgabe wird zur Anweisung an die Zusammenfassung"))
        stand = ernte.stand_lesen(tmp, "probe-sitzung")
        p.append(("ohne Einstellung kein Zugriff auf den echten Stand",
                  "kennmarke" in stand, False,
                  "der Probenprozess schreibt nur in seinen Probenordner"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return p


def _gedaechtnisdatei(ordner, name, typ, beschreibung, modified=None, zeit=None):
    kopf = ["---", "name: %s" % name, "description: %s" % beschreibung,
            "metadata:", "  type: %s" % typ]
    if modified:
        kopf.append("  modified: %s" % modified)
    kopf += ["---", "", "Inhalt %s" % name, ""]
    pfad = os.path.join(ordner, name + ".md")
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(kopf))
    if zeit is not None:
        os.utime(pfad, (zeit, zeit))
    return pfad


def _index_lesen(text, kopf):
    """(Dateistaemme der ganzen Zeilen, Schlagworte) aus einem Kurzindex."""
    ganz, worte = [], []
    anfang = "- %s " % kopf
    for zeile in text.split("\n"):
        if zeile.startswith("- [") and "](" in zeile:
            ganz.append(zeile.split("](", 1)[1].split(")", 1)[0][:-3])
        elif zeile.startswith(anfang) or zeile.startswith("  "):
            rest = zeile[len(anfang):] if zeile.startswith(anfang) else zeile
            worte += [w.strip() for w in rest.split("·") if w.strip()]
    return ganz, worte


def _gedaechtnisproben():
    """Kurzindex innerhalb der Ladegrenze - gebaut in eigenen Temp-Ordnern."""
    _, _, ged = _hooks_laden()
    if ged is None:
        return [("Gedaechtnisindex (uebersprungen)", True, True,
                 "ohne hooks/-Ordner gibt es nichts zu pruefen")]
    p = []
    t = ged.texte()
    kopf = t["schlagworte"]
    tmp = tempfile.mkdtemp(prefix="ia-gedaechtnis-")
    try:
        klein = os.path.join(tmp, "klein")
        os.makedirs(klein)
        _gedaechtnisdatei(klein, "a-regel", "feedback", "Regel A")
        _gedaechtnisdatei(klein, "b-vorhaben", "project", "Vorhaben B")
        _gedaechtnisdatei(klein, "c-vorhaben", "project", "Vorhaben C")
        _bytes_schreiben(os.path.join(klein, "d-bom.md"), BOM + (
            "---\nname: d-bom\ndescription: Mit BOM\nmetadata:\n  type: user\n"
            "---\n\nInhalt\n").encode("utf-8"))
        eintraege = ged.lesen(klein)
        text, info = ged.index_bauen(eintraege, t)
        rub = t["rubriken"]
        erwartet = "\n".join([
            t["kopfzeile"], "", t["vorspann"], "",
            "## %s" % rub["feedback"], "", "- [a-regel](a-regel.md) — Regel A", "",
            "## %s" % rub["user"], "", "- [d-bom](d-bom.md) — Mit BOM", "",
            "## %s" % rub["project"], "",
            "- [b-vorhaben](b-vorhaben.md) — Vorhaben B",
            "- [c-vorhaben](c-vorhaben.md) — Vorhaben C"]) + "\n"
        p.append(("kleiner Index bleibt vollstaendig und unveraendert",
                  text == erwartet and info["kurz"] == 0 and info["weg"] == 0, True,
                  "passt der Index, darf die Kuerzung nichts aendern"))
        p.append(("Gedaechtnisdatei mit BOM behaelt ihren Typ",
                  [e["typ"] for e in eintraege if e["datei"] == "d-bom.md"] == ["user"],
                  True, "mit BOM griff das Kopfmuster nicht - Sonstiges, ohne Beschreibung"))

        gross = os.path.join(tmp, "gross")
        os.makedirs(gross)
        basis = 1700000000
        for i in range(40):
            _gedaechtnisdatei(gross, "regel-%03d" % i, "feedback",
                              "Regel %d, alt, aber immer ganz im Index" % i,
                              zeit=basis - 86400 * 400 + i)
        zeit = {}
        for i in range(300):
            zeit["vorhaben-%03d" % i] = basis + 60 * ((i * 7919) % 300)
            modified = None
            if i % 2 == 0:
                modified = time.strftime("%Y-%m-%dT%H:%M:%S.000Z",
                                         time.gmtime(zeit["vorhaben-%03d" % i]))
            _gedaechtnisdatei(gross, "vorhaben-%03d" % i, "project",
                              "Vorhaben %d mit einer langen Beschreibung, die den Index "
                              "fuellt, bis er an die Ladegrenze stoesst" % i,
                              modified=modified,
                              zeit=None if modified else zeit["vorhaben-%03d" % i])
        eintraege = ged.lesen(gross)
        text, info = ged.index_bauen(eintraege, t, 190, 24000)
        zeilen, zeichen = ged.index_mass(text, mit_cr=True)
        ganz, worte = _index_lesen(text, kopf)
        p.append(("gekuerzter Index haelt das Budget",
                  zeilen <= 190 and zeichen <= 24000 and info["passt"], True,
                  "was ueber der Ladegrenze steht, laedt Claude Code nicht - still"))
        p.append(("gekuerzter Index nennt jeden Eintrag genau einmal",
                  sorted(ganz + worte) == sorted(e["datei"][:-3] for e in eintraege), True,
                  "ein Eintrag, der nirgends steht, wird nie nachgeschlagen"))
        p.append(("grosser Index kuerzt zu Schlagworten statt wegzulassen",
                  info["kurz"] > 0 and info["weg"] == 0, True,
                  "ein Schlagwort kostet nur einen Bruchteil einer ganzen Zeile"))
        p.append(("Regeln stehen immer als ganze Zeile",
                  all(("regel-%03d" % i) in ganz for i in range(40)), True,
                  "wie ich arbeiten soll, muss bei jedem Start vollstaendig da sein"))
        ganze_vorhaben = sorted(g for g in ganz if g.startswith("vorhaben-"))
        neueste = sorted(sorted(zeit, key=lambda s: -zeit[s])[:len(ganze_vorhaben)])
        p.append(("ganze Zeilen gehen an die juengsten Vorhaben",
                  bool(ganze_vorhaben) and ganze_vorhaben == neueste, True,
                  "modified aus dem Kopf zaehlt vor der Dateizeit"))
        hinweis = (t["gekuerzt"].replace("{kurz}", str(info["kurz"]))
                   .replace("{gesamt}", str(info["gesamt"])))
        p.append(("Kopf sagt, dass gekuerzt wurde",
                  hinweis in text.split("\n## ", 1)[0], True,
                  "sonst haelt man die Schlagwortzeile fuer den ganzen Bestand"))
        p.append(("Schlagwortzeilen bleiben kurz",
                  all(len(z) <= 200 for z in text.split("\n")
                      if z.startswith("- %s " % kopf) or z.startswith("  ")), True,
                  "eine ueberlange Zeile verschiebt die Zeichenzaehlung"))

        viele = [{"datei": "e%04d.md" % i, "slug": "e%04d" % i, "typ": "project",
                  "beschreibung": "Eintrag %d" % i, "aktualitaet": float(i)}
                 for i in range(2000)]
        text, info = ged.index_bauen(viele, t, 190, 3000)
        zeilen, zeichen = ged.index_mass(text, mit_cr=True)
        p.append(("Extremfall haelt das Budget",
                  zeilen <= 190 and zeichen <= 3000 and info["passt"], True,
                  "auch bei zu vielen Eintraegen kein stilles Abschneiden"))
        p.append(("Extremfall laesst die aeltesten weg und sagt es im Kopf",
                  info["weg"] > 0
                  and t["weggelassen"].replace("{fehlt}", str(info["weg"]))
                  in text.split("\n## ", 1)[0]
                  and info["weg_liste"] == sorted("e%04d.md" % i for i in range(info["weg"])),
                  True, "wer fehlt, steht nur in REGISTER.md - der Kopf muss es sagen"))

        text, info = ged.index_bauen(eintraege, t, 20, 24000)
        p.append(("Zeilengrenze greift fuer sich allein",
                  ged.index_mass(text, mit_cr=True)[0] <= 20
                  and info["kurz"] + info["weg"] > 0, True,
                  "Claude Code schneidet auch nach 200 Zeilen ab"))
        p.append(("Zaehlung mit Zeilenenden stimmt",
                  ged.index_mass("a\nb\n", mit_cr=True) == (2, 6)
                  and ged.index_mass("a\r\nb\r\n", mit_cr=True) == (2, 6)
                  and ged.index_mass("", mit_cr=True) == (0, 0)
                  and ged.index_mass("a\nb") == (2, 3), True,
                  "unter Windows schreibt --register CRLF - gezaehlt wird, was auf der Platte steht"))

        rev = os.path.join(tmp, "rev")
        os.makedirs(rev)
        _gedaechtnisdatei(rev, "r-regel", "feedback", "Regel R")
        with open(os.path.join(rev, "MEMORY.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("- zeile\n" * 201)
        vorher = [a for a, _ in ged.review(rev)[0]]
        ged.register_bauen(rev, schreiben=True)
        nachher = [a for a, _ in ged.review(rev)[0]]
        with open(os.path.join(rev, "MEMORY.md"), "r", encoding="utf-8", newline="") as f:
            zeilen, zeichen = ged.index_mass(f.read())
        p.append(("zu langer Kurzindex wird gemeldet", "Kurzindex zu lang" in vorher, True,
                  "sonst fehlt der Rest bei jedem Start still"))
        p.append(("neu gebauter Kurzindex wird nicht mehr gemeldet",
                  "Kurzindex zu lang" not in nachher and zeilen <= 200 and zeichen <= 25000,
                  True, "--register ist der Ausweg, den die Meldung nennt"))
        ged.register_bauen(gross, schreiben=True)
        befunde = [a for a, _ in ged.review(gross)[0]]
        p.append(("gekuerzter Index loest keine Meldung aus",
                  "Kurzindex zu lang" not in befunde and "Kurzindex zu klein" not in befunde,
                  True, "eine Warnung, die nach dem Ausweg bleibt, wird ignoriert"))

        rev_cr = os.path.join(tmp, "rev-cr")
        os.makedirs(rev_cr)
        _gedaechtnisdatei(rev_cr, "r-regel", "feedback", "Regel R")
        with open(os.path.join(rev_cr, "MEMORY.md"), "w", encoding="utf-8",
                  newline="\r\n") as f:
            f.write(("- " + "x" * 164 + "\n") * 149)
        p.append(("Kurzindex nur mit CR ueber der Zeichengrenze wird gemeldet",
                  "Kurzindex zu lang" in [a for a, _ in ged.review(rev_cr)[0]], True,
                  "149 Zeilen: ohne CR 24.883 Zeichen, mit CR 25.032 - geladen wird mit CR"))

        konf = os.path.join(tmp, "konf-budget")
        os.makedirs(konf)
        with open(os.path.join(konf, "konfig.json"), "w", encoding="utf-8") as f:
            json.dump({"index_max_zeichen": 1500}, f)
        with _konfig_umgelenkt(konf):
            befunde = [a for a, _ in ged.review(gross)[0]]
        p.append(("zu kleines Budget meldet Kurzindex zu klein",
                  "Kurzindex zu klein" in befunde, True,
                  "wer nicht einmal als Schlagwort passt, steht nur noch in REGISTER.md"))
        with open(os.path.join(konf, "konfig.json"), "w", encoding="utf-8") as f:
            json.dump({"index_max_zeilen": 500, "index_max_zeichen": 50000}, f)
        with _konfig_umgelenkt(konf):
            _, info = ged.index_bauen(ged.lesen(klein), t)
        p.append(("Budget aus konfig.json wird auf die Ladegrenze gedeckelt",
                  (info["max_zeilen"], info["max_zeichen"]) == (200, 25000), True,
                  "ein Budget ueber der Ladegrenze liesse Claude Code wieder still abschneiden"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return p


def _zettel_laden():
    ordner = os.path.join(os.path.dirname(HIER), "zettel")
    if not os.path.isfile(os.path.join(ordner, "zettel.py")):
        return None
    if ordner not in sys.path:
        sys.path.insert(0, ordner)
    try:
        import zettel
        return zettel
    except Exception:                                             # noqa: BLE001
        return None


def _zettelproben():
    zettel = _zettel_laden()
    if zettel is None:
        return [("Zettelkasten vorhanden (uebersprungen)", True, True,
                 "ohne skills/zettel gibt es nichts zu pruefen")]
    p = []
    alt_zk, alt_state = zettel.ZK, zettel.STATE
    tmp = tempfile.mkdtemp(prefix="ia-zettel-")
    try:
        zettel.setzen_wurzel(tmp)
        zettel.setzen_state(tmp)
        n, _ = zettel.ablegen({
            "quelle": "probe",
            "eintraege": [
                {"titel": "Hiebsatz", "thema": "Forsteinrichtung",
                 "text": "**Ausgangslage:** A\n\n**Weg:** B\n\n**Ergebnis:** 42 Festmeter",
                 "schlagworte": ["hiebsatz", "Bäume"]},
                {"titel": "Wegebau", "thema": "Wege", "text": "Schotter 0/32",
                 "schlagworte": ["wegebau"]}],
            "dossiers": {"Forsteinrichtung": {"stand": "Hiebsatz steht.",
                                              "gesichert": "- 42 Festmeter",
                                              "offen": "- [ ] Kulturen"}},
            "erkenntnisse": ["Ein Fakt, eine Datei."]})
        p.append(("Ablage legt beide Eintraege ab", n == 2, True, "je Thema ein Eintrag"))
        tage = list(Path(tmp, "Journal").glob("*/*.md"))
        p.append(("Journal-Tagesseite entsteht", len(tage) == 1, True,
                  "je Tag eine Seite, append-only"))
        tagtext = tage[0].read_text(encoding="utf-8") if tage else ""
        p.append(("Umlaut im Schlagwort wird zum Slug", "#baeume" in tagtext, True,
                  "Register und Suche arbeiten mit Slugs"))
        doss = zettel.dossier_text("Forsteinrichtung")
        p.append(("Besuchs-Log verlinkt den Journal-Eintrag",
                  "[[Journal/" in doss.split("## Besuchs-Log")[-1], True,
                  "der Besuchsvermerk entsteht beim Ablegen"))
        p.append(("Stand geschrieben, Besuchs-Log bleibt",
                  "Hiebsatz steht." in doss and "## Besuchs-Log" in doss, True,
                  "die Titelseite wird neu geschrieben, der Log nie"))
        uebersicht = Path(tmp, "Dossiers.md")
        p.append(("Uebersicht verlinkt das Dossier",
                  uebersicht.is_file() and "[[Dossiers/forsteinrichtung]]"
                  in uebersicht.read_text(encoding="utf-8"), True,
                  "unverlinkt waere die Seite fuer den Hausmeister eine Waise"))
        p.append(("Register traegt das Schlagwort",
                  bool(zettel.register_treffer(["hiebsatz"])), True, "mittlere Abrufebene"))
        p.append(("Suche findet das Dossier",
                  "Dossier   Dossiers/forsteinrichtung" in zettel.suche(["Forsteinrichtung"]),
                  True, "erste Stufe: Dossiername"))
        p.append(("Suche findet ueber das Schlagwort",
                  "Journal   Journal/" in zettel.suche(["hiebsatz"]), True,
                  "zweite Stufe: Register"))
        p.append(("Volltext findet Ungetaggtes",
                  "Volltext  Journal/" in zettel.suche(["Schotter"]), True,
                  "dritte Stufe, Zusatz gegenueber Ferradea"))
        p.append(("unbekannter Begriff liefert keinen Treffer",
                  zettel.suche(["gibtsnichtxyz"]).startswith("Kein Treffer"), True,
                  "ehrliche Meldung statt Beliebigem"))
        gelesen = zettel.lies("Forsteinrichtung")
        p.append(("Lesen liefert Dossier und Journal-Tag",
                  "## Stand" in gelesen and "42 Festmeter" in gelesen, True,
                  "Trefferseiten im Ganzen"))
        p.append(("Lesen verlaesst die Wurzel nicht",
                  zettel.lies("../../etc/passwd").startswith("Nichts gefunden"), True,
                  "ein Seitenname darf nicht aus dem Zettelkasten fuehren"))
        p.append(("Erkenntnis steht im Index",
                  "Ein Fakt, eine Datei." in zettel.erkenntnis_text(), True,
                  "Spitze der Pyramide"))
        p.append(("Karte nennt Dossier und Stand",
                  "- Forsteinrichtung: Hiebsatz steht." in zettel.karte_saetze(), True,
                  "die Karte ist der stille Wegweiser"))
        Path(tmp, "Dossiers", "verwaist.md").write_text("# Verwaist\n", encoding="utf-8")
        w = zettel.waisen(zettel._seiten())
        p.append(("Hausmeister findet die Waise", "Dossiers/verwaist" in w, True,
                  "unverlinkt ist unerreichbar"))
        p.append(("verlinktes Dossier ist keine Waise", "Dossiers/forsteinrichtung" in w,
                  False, "sonst verschwindet Lebendes im Archiv"))
        p.append(("Journal ist nie archivierbar",
                  zettel._archivierbar("Journal/2026/2026-09-15"), False,
                  "der Strom ist heilig"))
        meldungen = []
        for i in range(3):
            _, meldungen = zettel.ablegen({"quelle": "probe", "eintraege": [
                {"titel": "Runde %d" % i, "thema": "Kreisel", "text": "wieder dasselbe",
                 "schlagworte": ["kreisel"]}]})
        p.append(("Kreis-Pruefung meldet sich nach drei Ablagen",
                  any("Kreis-Prüfung" in m for m in meldungen), True,
                  "Reflexion ohne Handlung ist Rumination"))
        leer, _ = zettel.ablegen({"eintraege": [{"thema": "x", "text": ""}]})
        p.append(("leere Ablage schreibt nichts", leer == 0, True,
                  "nichts Ablegbares heisst nichts geschrieben"))

        bom_wurzel = os.path.join(tmp, "bom")
        zettel.setzen_wurzel(bom_wurzel)
        _bytes_schreiben(os.path.join(bom_wurzel, "Dossiers", "wegebau.md"),
                         BOM + b"# Wegebau\n\nThemen-Dossier.\n")
        p.append(("Dossier mit BOM wird unter seinem Namen gefunden",
                  zettel.zettel_thema_aufloesen("Wege") == "Wegebau", True,
                  "mit BOM trug der Name ein unsichtbares Zeichen und die Raute"))
        uebersicht_bom = os.path.join(bom_wurzel, "Projekte", "forst", "Dossiers.md")
        _bytes_schreiben(uebersicht_bom,
                         BOM + b"# Dossiers - Forst\n\nTeilaspekt-Dossiers.\n")
        zettel.ablegen({"quelle": "probe", "projekt": "Forst", "eintraege": [
            {"titel": "Rueckegasse", "thema": "Erschliessung", "text": "Abstand 40 m",
             "schlagworte": ["rueckegasse"]}]})
        with open(uebersicht_bom, "rb") as f:
            seite = f.read().decode("utf-8-sig")
        p.append(("Projektuebersicht mit BOM behaelt genau einen Kopf",
                  seite.count("# Dossiers") == 1
                  and "[[Projekte/forst/Dossiers/erschliessung]]" in seite, True,
                  "mit BOM galt der Kopf als fehlend und wurde ein zweites Mal davorgesetzt"))
    finally:
        zettel.setzen_wurzel(alt_zk)
        zettel.setzen_state(alt_state)
        shutil.rmtree(tmp, ignore_errors=True)
    return p


def _installer_laden():
    paket = os.path.dirname(os.path.dirname(HIER))
    if not (os.path.isfile(os.path.join(paket, "installieren.py"))
            and os.path.isdir(os.path.join(paket, "skills"))):
        return None, None
    if paket not in sys.path:
        sys.path.insert(0, paket)
    try:
        import installieren
        return installieren, paket
    except Exception:                                             # noqa: BLE001
        return None, None


def _aktualisierungsproben():
    p = []
    akt = _modul("aktualisierung")
    if akt is not None:
        p.append(("Versionsvergleich: 2.0.10 ist neuer als 2.0.9",
                  akt.neuer(akt.version_tupel("2.0.10"), akt.version_tupel("2.0.9")), True,
                  "ein Zeichenkettenvergleich hielte 2.0.10 fuer aelter"))
        p.append(("ungueltige Version wird abgewiesen", akt.version_tupel("v2.0") is None,
                  True, "sonst wird ein Phantom-Tag geladen"))
        p.append(("Archivpfad mit .. wird abgewiesen",
                  akt.pfad_sicher("paket/../../x.py"), False,
                  "Zip-Slip schreibt ausserhalb des Zielordners"))
        p.append(("Archivpfad mit Laufwerk wird abgewiesen",
                  akt.pfad_sicher("C:/Windows/x.py"), False, "absolut ist nie erlaubt"))
        p.append(("gewoehnlicher Archivpfad wird angenommen",
                  akt.pfad_sicher("infinite-accuracy-2.0.0/infinite-accuracy/hooks/ernte.py"),
                  True, "Regelfall"))
        tmp = tempfile.mkdtemp(prefix="ia-bom-akt-")
        try:
            _bytes_schreiben(os.path.join(tmp, akt.META, "installiert.json"),
                             BOM + b'{"version": "9.9.9"}')
            p.append(("installiert.json mit BOM wird gelesen",
                      (akt.installiert(tmp) or {}).get("version") == "9.9.9", True,
                      "sonst gilt eine Installation als fehlend und die Update-Pruefung schweigt"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    inst, paket = _installer_laden()
    if inst is None:
        p.append(("Installer-Proben (uebersprungen: kein vollstaendiges Paket)", True, True,
                  "in einer Projektinstallation liegt nur ein Teil des Pakets"))
        return p

    tmp = tempfile.mkdtemp(prefix="ia-bom-inst-")
    try:
        pfad = os.path.join(tmp, "installation.json")
        _bytes_schreiben(pfad, BOM + b'{"ausnahmen": ["skills/einrichten"]}')
        try:
            gelesen = inst._json_lesen(pfad)
        except Exception:                                         # noqa: BLE001
            gelesen = None
        p.append(("Installer liest JSON mit BOM",
                  gelesen == {"ausnahmen": ["skills/einrichten"]}, True,
                  "eine mit PowerShell gespeicherte installation.json fiel still weg"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    fehler = inst.manifest_pruefen(paket)
    p.append(("Pruefsummen des Pakets stimmen", not fehler, True,
              "vor jedem Release: installieren.py --manifest (%s)" % "; ".join(fehler[:3])))
    tmp = tempfile.mkdtemp(prefix="ia-installation-")
    try:
        kopie = os.path.join(tmp, "paket")
        shutil.copytree(paket, kopie, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        projekt = os.path.join(tmp, "projekt")
        os.makedirs(os.path.join(projekt, ".claude"))

        def still(*_a, **_k):
            return None

        rc = inst.ausfuehren(kopie, projekt, "erstinstallation", ohne_abnahme=True, ausgabe=still)
        p.append(("Erstinstallation laeuft durch", rc == 0, True, "Regelfall"))
        if rc != 0:
            p.append(("Installer-Folgeproben (abgebrochen: Erstinstallation gescheitert)",
                      False, True, "zuerst die Probe 'Pruefsummen des Pakets stimmen' beheben"))
            return p
        p.append(("Hook liegt am Zielort",
                  os.path.isfile(os.path.join(projekt, ".claude", "hooks", "ernte.py")), True,
                  "hooks/ gehoert nach .claude/hooks/"))
        p.append(("Zettel-Skill liegt am Zielort",
                  os.path.isfile(os.path.join(projekt, ".claude", "skills", "zettel", "zettel.py")),
                  True, "skills/ gehoert nach .claude/skills/"))
        p.append(("hooks.json wird nicht installiert",
                  os.path.exists(os.path.join(projekt, ".claude", "hooks", "hooks.json")), False,
                  "ein Projekt verdrahtet ueber settings.json"))
        stand = inst.installiert_lesen(projekt) or {}
        p.append(("installiert.json nennt die Version",
                  stand.get("version") == inst.version_lesen(kopie), True,
                  "daran misst die Update-Pruefung"))
        rc = inst.ausfuehren(kopie, projekt, "update", ohne_abnahme=True, ausgabe=still)
        p.append(("Update ohne Aenderung tut nichts", rc == 0, True,
                  "zweimal installieren ist kein Fehler"))

        ziel = os.path.join(projekt, ".claude", "hooks", "ernte.py")
        with open(ziel, "a", encoding="utf-8") as f:
            f.write("\n# lokal geaendert\n")
        with open(os.path.join(kopie, "hooks", "ernte.py"), "a", encoding="utf-8") as f:
            f.write("\n# neue Fassung\n")
        inst.manifest_schreiben(kopie)
        rc = inst.ausfuehren(kopie, projekt, "update", ohne_abnahme=True, ausgabe=still)
        p.append(("lokal geaenderte Datei stoppt das Update", rc == 1, True,
                  "ein Update darf eigene Aenderungen nicht still ueberschreiben"))
        with open(ziel, "r", encoding="utf-8") as f:
            p.append(("lokale Aenderung bleibt nach dem Abbruch",
                      "# lokal geaendert" in f.read(), True, "abgebrochen heisst unberuehrt"))
        with open(os.path.join(kopie, "hooks", "regelschub.py"), "a", encoding="utf-8") as f:
            f.write("\n# manipuliert\n")
        p.append(("manipulierte Paketdatei faellt auf", bool(inst.manifest_pruefen(kopie)),
                  True, "Pruefsummen schuetzen vor halben Downloads"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return p


def _git(ordner, *argumente):
    """(rc, stdout als Bytes, stderr gekuerzt) - lokal, ohne Netz, ohne Sperrdateien."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["LC_ALL"] = "C"
    try:
        p = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                            "-C", ordner] + list(argumente),
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, timeout=120)
        return p.returncode, p.stdout, _text(p.stderr)[:160]
    except Exception as ex:                                       # noqa: BLE001
        return -1, b"", str(ex)[:160]


def _text(roh):
    return roh.decode("utf-8", "replace").strip()


def _version(text):
    """(x, y, z) nur fuer genau drei ASCII-Zifferngruppen, sonst None."""
    teile = str(text).split(".")
    if len(teile) != 3 or not all(t.isascii() and t.isdigit() for t in teile):
        return None
    return tuple(int(t) for t in teile)


def _staende(tags):
    """{(x, y, z): tagname} fuer die Release-Tags v<x.y.z>; Tags mit Zusatz zaehlen nicht."""
    return {_version(t[1:]): t for t in sorted(tags)
            if t.startswith("v") and _version(t[1:]) is not None}


def _tagurteil(version, tags, erster):
    """(bestanden, zustand): getaggt | vorbereitet | Grund fuer Rot."""
    eigen = _version(version)
    if eigen is None:
        return False, "version.json traegt keine gueltige Version: %r" % (version,)
    if "v" + version in tags:
        return True, "getaggt"
    staende = _staende(tags)
    if eigen in staende:
        return False, "der Tag heisst %s, geladen wird v%s" % (staende[eigen], version)
    if not staende:
        if erster:
            return True, "vorbereitet"
        return False, "keine Release-Tags im Klon - git fetch --tags"
    juengster = max(staende)
    if eigen > juengster:
        return True, "vorbereitet"
    return False, ("ohne Tag und nicht neuer als %s - version.json und plugin.json anheben"
                   % staende[juengster])


def _bytes(pfad):
    try:
        with open(pfad, "rb") as f:
            return f.read()
    except Exception:                                             # noqa: BLE001
        return None


def _baum_lesen(inst, paket):
    """Paketdateien so, wie der Installer sie auswaehlt, dazu PRUEFSUMMEN.json; None = unlesbar."""
    rels = list(inst.paket_dateien(paket))
    if os.path.isfile(os.path.join(paket, inst.MANIFEST)):
        rels.append(inst.MANIFEST)
    return {rel: _bytes(os.path.join(paket, *rel.split("/"))) for rel in rels}


def _abweichungen(archiv, baum):
    fehler = []
    for rel in sorted(set(archiv) | set(baum)):
        if rel not in baum:
            fehler.append("nur im Tag: %s" % rel)
        elif baum[rel] is None:
            fehler.append("unlesbar: %s" % rel)
        elif rel not in archiv:
            fehler.append("nicht im Tag: %s" % rel)
        elif archiv[rel] != baum[rel]:
            fehler.append("abweichend: %s" % rel)
    return fehler


def _archiv(wurzel, ref, praefix):
    """({rel: bytes}, fehler) - der Paketordner so, wie git archive ihn ausliefert."""
    rc, roh, fehler = _git(wurzel, "archive", "--format=tar", ref, "--", praefix or ".")
    if rc != 0:
        return {}, "archive rc %d: %s" % (rc, fehler)
    dateien = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(roh), mode="r:") as tar:
            for m in tar.getmembers():
                if m.isfile() and m.name.startswith(praefix):
                    dateien[m.name[len(praefix):]] = tar.extractfile(m).read()
    except Exception as ex:                                       # noqa: BLE001
        return {}, "Archiv unlesbar: %s" % ex
    if not dateien:
        return {}, "Archiv ohne Paketdateien"
    return dateien, ""


def _archiv_pruefsummen(inst, archiv):
    """Das Archiv in einen Temp-Ordner legen und so pruefen, wie der Installer prueft."""
    if not archiv:
        return ["kein Archiv"]
    tmp = tempfile.mkdtemp(prefix="ia-tagarchiv-")
    try:
        for rel, inhalt in archiv.items():
            teile = rel.split("/")
            if not rel or rel.startswith("/") or ":" in rel or ".." in teile:
                return ["unzulaessiger Pfad im Archiv: %s" % rel]
            pfad = os.path.join(tmp, *teile)
            os.makedirs(os.path.dirname(pfad), exist_ok=True)
            with open(pfad, "wb") as f:
                f.write(inhalt)
        return inst.manifest_pruefen(tmp)
    except Exception as ex:                                       # noqa: BLE001
        return ["Archiv nicht pruefbar: %s" % ex]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _gitordner_ueber(pfad):
    pfad = os.path.abspath(pfad)
    while True:
        if os.path.exists(os.path.join(pfad, ".git")):
            return True
        oben = os.path.dirname(pfad)
        if oben == pfad:
            return False
        pfad = oben


def _tagproben():
    """Paketordner gegen das Archiv des Tags v<version.json> - nur im Quell-Repository."""
    p = []
    p.append(("Tag-Urteil: getaggte Version",
              _tagurteil("2.0.2", ["v2.0.1", "v2.0.2"], False) == (True, "getaggt"), True,
              "danach vergleichen die Archiv-Proben Byte fuer Byte"))
    p.append(("Tag-Urteil: angehobene Version vor dem Tag ist vorbereitet",
              _tagurteil("2.0.3", ["v2.0.1", "v2.0.2"], False) == (True, "vorbereitet"), True,
              "der Pruefstand laeuft vor dem Tag - das darf nicht rot sein"))
    p.append(("Tag-Urteil: 2.0.9 ohne Tag ist neben v2.0.10 nicht vorbereitet",
              _tagurteil("2.0.9", ["v2.0.10"], False)[0], False,
              "ein Zeichenkettenvergleich hielte 2.0.9 fuer neuer"))
    p.append(("Tag-Urteil: v2.0.02 ersetzt v2.0.2 nicht",
              _tagurteil("2.0.2", ["v2.0.02"], False)[0], False,
              "geladen wird der Tag, der genau so heisst wie die Version"))
    p.append(("Tag-Urteil: ungueltige Version",
              _tagurteil("2.0", [], True)[0], False, "ohne Nummer kein Tag"))
    p.append(("Tag-Urteil: leere Tagliste in gewachsenem Repository ist nicht vorbereitet",
              _tagurteil("2.0.3", [], False)[0], False,
              "ein Klon ohne Tags wuerde sonst jede Aenderung durchlassen"))
    p.append(("Tag-Urteil: erster Stand ohne Tag ist vorbereitet",
              _tagurteil("1.0.0", [], True) == (True, "vorbereitet"), True,
              "neues Repository mit genau einem Commit"))
    p.append(("Tag-Urteil: Tag mit Zusatz zaehlt nicht als Release",
              _tagurteil("2.0.2", ["v2.0.1", "v2.0.2-rc1"], False) == (True, "vorbereitet"),
              True, "aktualisierung.py laedt nur v<x.y.z>"))
    p.append(("Tag-Vergleich: gleicher Stand ergibt keine Abweichung",
              _abweichungen({"a.py": b"x\n"}, {"a.py": b"x\n"}), False, "Regelfall"))
    p.append(("Tag-Vergleich: geaenderte Paketdatei faellt auf",
              _abweichungen({"a.py": b"x\n"}, {"a.py": b"y\n"}), True,
              "Aenderung am Zweig ohne neue Version erreicht kein Projekt"))
    p.append(("Tag-Vergleich: CRLF statt LF faellt auf",
              _abweichungen({"a.txt": b"x\n"}, {"a.txt": b"x\r\n"}), True,
              "das Archiv liefert Bytes, der Installer prueft Bytes - git diff saehe es nicht"))
    p.append(("Tag-Vergleich: neue Paketdatei ohne Tag faellt auf",
              _abweichungen({"a.py": b"x\n"}, {"a.py": b"x\n", "b.txt": b"z\n"}), True,
              "der Installer nimmt jede Datei im Paketordner"))
    p.append(("Tag-Vergleich: im Tag fehlende Datei faellt auf",
              _abweichungen({"a.py": b"x\n", "b.txt": b"z\n"}, {"a.py": b"x\n"}), True,
              "geloeschte Datei ohne neue Version"))
    p.append(("Tag-Vergleich: unlesbare Datei faellt auf",
              _abweichungen({"a.py": b"x\n"}, {"a.py": None}), True,
              "eine gesperrte Datei darf nicht als gleich gelten"))

    inst, paket = _installer_laden()
    if inst is None:
        p.append(("Tag-Proben (uebersprungen: kein vollstaendiges Paket)", True, True,
                  "in einer Projektinstallation liegt weder Paketordner noch Repository"))
        return p
    rc_w, aus_w, err_w = _git(paket, "rev-parse", "--show-toplevel")
    rc_p, aus_p, err_p = _git(paket, "rev-parse", "--show-prefix")
    if rc_w != 0 or rc_p != 0:
        if _gitordner_ueber(paket):
            p.append(("git ist aufrufbar, wo das Paket in einem Repository liegt", False, True,
                      "absichtlich rot: ohne git kein Tag-Vergleich, im Repository wird "
                      "nicht still uebersprungen (%s)" % (err_w or err_p)))
        else:
            p.append(("Tag-Proben (uebersprungen: Paket liegt in keinem git-Repository)",
                      True, True, "Paketkopie ohne Versionsgeschichte"))
        return p
    wurzel, praefix = _text(aus_w), _text(aus_p)

    rc_f, aus_f, err_f = _git(paket, "ls-files", "--", inst.MANIFEST)
    if rc_f != 0:
        p.append(("git liest den Index des Repositorys", False, True,
                  "ls-files rc %d: %s" % (rc_f, err_f)))
        return p
    if not _text(aus_f):
        p.append(("Tag-Proben (uebersprungen: Paket wird in diesem Repository nicht verfolgt)",
                  True, True, "die Tags eines fremden Repositorys gehoeren nicht zum Paket"))
        return p

    for name in LIZENZTEXTE:
        oben = _bytes(os.path.join(wurzel, name))
        unten = _bytes(os.path.join(paket, name))
        p.append(("Lizenztext in Wurzel und Paket bytegleich: %s" % name,
                  oben is not None and oben == unten, True,
                  "die Wurzel zeigt GitHub, das Paket erreicht die Projekte (Wurzel %s, Paket %s)"
                  % ("fehlt" if oben is None else "da", "fehlt" if unten is None else "da")))
    deutsch = _bytes(os.path.join(paket, "EUPL-1.2-DE.txt"))
    p.append(("EUPL-1.2-DE.txt im Paket ist die amtliche Fassung",
              deutsch is not None and hashlib.sha256(deutsch).hexdigest() == EUPL_DE_SHA256,
              True, "BOM und CRLF gehoeren zum Wortlaut; --manifest nimmt jeden Stand hin"))
    rc_a, aus_a, err_a = _git(paket, "check-attr", "text", "--", "EUPL-1.2-DE.txt")
    p.append(("EUPL-1.2-DE.txt ist von der Zeilenend-Normalisierung ausgenommen",
              rc_a == 0 and _text(aus_a).endswith(": text: unset"), True,
              "ohne '-text' in .gitattributes speichert git LF und das Tag-Archiv verfehlt "
              "die Pruefsumme (%s)" % (_text(aus_a) or err_a)))

    rc_t, aus_t, err_t = _git(wurzel, "for-each-ref", "--format=%(refname)", "refs/tags/")
    p.append(("Tagliste ist lesbar", rc_t == 0, True, "for-each-ref rc %d: %s" % (rc_t, err_t)))
    if rc_t != 0:
        return p
    tags = [z[len("refs/tags/"):] for z in _text(aus_t).splitlines()
            if z.startswith("refs/tags/")]
    erster = False
    if not _staende(tags):
        rc_c, aus_c, _f = _git(wurzel, "rev-list", "--count", "HEAD")
        rc_s, aus_s, _f = _git(wurzel, "rev-parse", "--is-shallow-repository")
        erster = (rc_c == 0 and _text(aus_c) == "1"
                  and rc_s == 0 and _text(aus_s) == "false")
    try:
        version = inst.version_lesen(paket)
    except Exception as ex:                                       # noqa: BLE001
        version = "unlesbar: %s" % ex
    bestanden, zustand = _tagurteil(version, tags, erster)
    p.append(("Version ist getaggt oder als naechstes Release vorbereitet", bestanden, True,
              "Version %s: %s" % (version, zustand)))

    baum = _baum_lesen(inst, paket)
    eigen = _version(version)
    aeltere = sorted(s for s in _staende(tags) if eigen is not None and s < eigen)
    if aeltere:
        vorgaenger = _staende(tags)[aeltere[-1]]
        alt, fehler = _archiv(wurzel, "refs/tags/" + vorgaenger, praefix)
        p.append(("Gegenprobe: Paketordner weicht vom Archiv des Vorgaenger-Tags ab",
                  bool(alt) and bool(_abweichungen(alt, baum)), True,
                  "der Vergleich muss eine echte Abweichung sehen (%s %s)"
                  % (vorgaenger, fehler or "ohne Unterschied")))
    leer, fehler = _archiv(wurzel, "HEAD", praefix + "gibtsnicht-ia-probe/")
    p.append(("Gegenprobe: Archiv eines fehlenden Pfads meldet einen Fehler",
              bool(fehler) and not leer, True,
              "sonst gilt ein leeres Archiv als gueltiger Stand"))

    if zustand != "getaggt":
        p.append(("Archiv-Proben (uebersprungen: Version noch ohne Tag)", True, True,
                  "nach git tag v<version> den Pruefstand erneut fahren, erst dann pushen"))
        return p
    archiv, fehler = _archiv(wurzel, "refs/tags/v" + version, praefix)
    p.append(("Tag der Version liefert ein Archiv mit Paketdateien", not fehler, True,
              "aktualisierung.py laedt genau dieses Archiv (%s)" % fehler))
    try:
        tagversion = json.loads(archiv["version.json"].decode("utf-8-sig")).get("version")
    except Exception:                                             # noqa: BLE001
        tagversion = None
    p.append(("Archiv des Tags traegt die Version aus version.json", tagversion == version,
              True, "Zweig und Tag muessen dieselbe Fassung meinen (Tag: %r)" % (tagversion,)))
    fehler = _archiv_pruefsummen(inst, archiv)
    p.append(("Archiv des Tags erfuellt seine eigenen Pruefsummen", not fehler, True,
              "sonst bricht das Update in jedem Projekt ab (%d: %s)"
              % (len(fehler), "; ".join(fehler[:5]))))
    fehler = _abweichungen(archiv, baum)
    p.append(("Paketordner gleicht Byte fuer Byte dem Archiv des Tags", not fehler, True,
              "Paketdatei geaendert ohne neue Version - version.json und plugin.json "
              "anheben (%d: %s)" % (len(fehler), "; ".join(fehler[:5]))))
    return p


def _sprachdatei(ordner, name, text, bom=False):
    pfad = os.path.join(ordner, name)
    _bytes_schreiben(pfad, (BOM if bom else b"") + text.encode("utf-8"))
    return pfad


def _sprachzahl(funde, stufe=None, rid=None):
    return sum(1 for f in funde
               if (stufe is None or f["stufe"] == stufe)
               and (rid is None or f["id"] == rid))


def _sprachproben():
    """Textpruefer des Skills sprachregel - Katalog, Zonen, Mass, Aufruf."""
    ordner = os.path.join(os.path.dirname(HIER), "sprachregel")
    pfad = os.path.join(ordner, "pruefe.py")
    if not os.path.isfile(pfad):
        return []
    if ordner not in sys.path:
        sys.path.insert(0, ordner)
    try:
        import pruefe                                             # noqa: E402
    except Exception as ex:                                       # noqa: BLE001
        return [("sprachregel: pruefe.py laedt", str(ex), True,
                 "ohne Modul keine Textpruefung")]

    p = []
    kat = pruefe.katalog()
    p.append(("sprachregel: Katalog traegt beide Stufen",
              {r[1] for r in kat} == {"A", "B"}, True,
              "Stufe A urteilt, Stufe B fragt - eine allein taugt nicht"))
    p.append(("sprachregel: jede Regel nennt einen Ersatz",
              all(r[3].strip() for r in kat), True,
              "eine Regel ohne Ersatz laesst den Text anderswo ausufern"))
    p.append(("sprachregel: Regelkennungen sind eindeutig",
              len({r[0] for r in kat}) == len(kat), True,
              "zwei Regeln mit derselben Kennung sind im Bericht nicht trennbar"))

    p.append(("sprachregel: Fuellwort wird gefunden",
              _sprachzahl(pruefe.pruefen("x", "Das ist eigentlich gut.\n"), "A"), True,
              "Stufe A ist der Kern des Katalogs"))
    p.append(("sprachregel: sauberer Satz bleibt ohne Fund",
              pruefe.pruefen("x", "Der Dienst laeuft seit 12 Uhr.\n"), False,
              "ein Falschalarm im Regelfall macht den Pruefer unbrauchbar"))
    p.append(("sprachregel: Zitatzeile wird nicht geprueft",
              pruefe.pruefen("x", "> Das ist eigentlich gut.\n"), False,
              "fremder Wortlaut wird nicht geglaettet"))
    p.append(("sprachregel: Codeblock wird nicht geprueft",
              pruefe.pruefen("x", "```\neigentlich\n```\n"), False,
              "Programmausgabe ist Beweisstueck"))
    p.append(("sprachregel: Kopfblock wird nicht geprueft",
              pruefe.pruefen("x", "---\nname: eigentlich\n---\n\nText.\n"), False,
              "das Frontmatter ist Konfiguration, kein Satz"))
    p.append(("sprachregel: Inline-Code wird maskiert",
              pruefe.pruefen("x", "Das Wort `eigentlich` steht im Katalog.\n"), False,
              "sonst loest der Regeltext seine eigene Regel aus"))
    p.append(("sprachregel: --alles prueft die Zonen mit",
              _sprachzahl(pruefe.pruefen("x", "> Das ist eigentlich gut.\n", True), "A"),
              True, "mit --alles wird ausdruecklich alles geprueft"))

    lang = "Der Dienst " + "sehr " * 30 + "laeuft.\n"
    p.append(("sprachregel: ueberlanger Satz wird gemeldet",
              _sprachzahl(pruefe.pruefen("x", lang), None, "B5"), True,
              "Satzlaenge ist ein Mass, kein Wortlaut"))
    liste = "".join("- Punkt %d mit sieben weiteren Woertern in dieser Zeile\n" % i
                    for i in range(1, 5))
    p.append(("sprachregel: Aufzaehlung meldet keine Ueberlaenge",
              _sprachzahl(pruefe.pruefen("x", liste), None, "B5"), False,
              "verbundene Listenpunkte galten sonst als ein Satz"))
    p.append(("sprachregel: Aufzaehlung meldet keine Strichhaeufung",
              _sprachzahl(pruefe.pruefen("x", "- a — b\n- c — d\n"), None, "B6"),
              False, "je Punkt ein Strich ist kein Absatz mit vier Strichen"))

    tmp = tempfile.mkdtemp(prefix="ia-sprachregel-")
    try:
        schmutzig = _sprachdatei(tmp, "schmutzig.md", "Das ist eigentlich gut.\n")
        sauber = _sprachdatei(tmp, "sauber.md", "Der Dienst laeuft seit 12 Uhr.\n")
        mitbom = _sprachdatei(tmp, "bom.md", "Das ist eigentlich gut.\n", True)
        hinweise = _sprachdatei(tmp, "hinweise.md",
                                "Die Datei wurde geschrieben.\n\n"
                                "Der Wert wurde gesetzt.\n")

        rc, aus = _skript(pfad, "--liste")
        p.append(("sprachregel: --liste druckt den Katalog ohne Datei",
                  rc == 0 and "A1" in aus and "B5" in aus, True,
                  "die Anleitung verweist auf diese Ausgabe statt sie abzuschreiben"))
        rc, aus = _skript(pfad)
        p.append(("sprachregel: Aufruf ohne Datei meldet Aufruffehler",
                  rc == 2, True, "kein stdin - ein wartender Aufruf haengt"))
        rc, aus = _skript(pfad, schmutzig)
        p.append(("sprachregel: Stufe-A-Fund faerbt rot",
                  rc == 1 and "STATUS: ROT" in aus, True,
                  "sonst laesst sich die Pruefung nicht in eine Abnahme haengen"))
        rc, aus = _skript(pfad, sauber)
        p.append(("sprachregel: sauberer Text bleibt gruen",
                  rc == 0 and "STATUS: GRUEN" in aus, True, "Regelfall"))
        rc, aus = _skript(pfad, mitbom)
        p.append(("sprachregel: Datei mit BOM wird gelesen",
                  rc == 1 and "A5" in aus, True,
                  "mit PowerShell gespeicherte Dateien tragen ein BOM"))
        rc, aus = _skript(pfad, "--schwelle", "0", hinweise)
        p.append(("sprachregel: Schwelle 0 faerbt Hinweise rot",
                  rc == 1, True, "die Schwelle muss wirken"))
        rc, aus = _skript(pfad, "--schwelle", "9", hinweise)
        p.append(("sprachregel: Hinweise unter der Schwelle bleiben gruen",
                  rc == 0, True, "Stufe B ist eine Frage, kein Urteil"))
        rc, aus = _skript(pfad, "--json", schmutzig)
        try:
            daten = json.loads(aus)
        except Exception:                                         # noqa: BLE001
            daten = {}
        p.append(("sprachregel: --json liefert Funde und Urteil",
                  daten.get("urteil") == "ROT" and bool(daten.get("funde")), True,
                  "maschinell weiterverarbeitbar"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for name in (os.path.join(ordner, "SKILL.md"),
                 os.path.join(HIER, "doku", "sprachregel.md")):
        if os.path.isfile(name):
            with open(name, "r", encoding="utf-8-sig") as f:
                p.append(("sprachregel: %s ohne Fund der Stufe A" % os.path.basename(name),
                          _sprachzahl(pruefe.pruefen(name, f.read()), "A"), False,
                          "ein Regeltext, der seine eigene Regel bricht, gilt nicht"))
    return p


def proben():
    """Liste von (name, ist_wahr, erwartet, warum). Nebenwirkungen nur in Temp-Ordnern."""
    s = _scratch()
    p = []

    for muster, was in [("/tmp/ia-42-*", "Sternchen"),
                        ("/tmp/ia-42-?", "Fragezeichen"),
                        ("/tmp/ia-42-[ab]", "Zeichenklasse"),
                        ("/tmp/ia-42;touch /tmp/x", "Semikolon"),
                        ("/tmp/ia-42$(id)", "Kommandosubstitution"),
                        ("/tmp/ia-42`id`", "Backtick"),
                        ("/tmp/ia-42|tee /tmp/x", "Pipe"),
                        ("/tmp/ia-42 mit leerzeichen", "Leerzeichen"),
                        ("/tmp/ia-42\nrm /etc/passwd", "Zeilenumbruch")]:
        p.append(("Serverpfad mit %s wird abgewiesen" % was,
                  journal.pfad_erlaubt(muster, PROBE_ZIEL), False,
                  "geht unquotiert an die entfernte Shell"))

    p.append(("gewoehnlicher Serverpfad wird angenommen",
              journal.pfad_erlaubt("/tmp/ia-42-modul.py", PROBE_ZIEL), True,
              "das ist der Regelfall, fuer den die Schranke gebaut ist"))
    p.append(("gewoehnlicher lokaler Pfad wird angenommen",
              journal.pfad_erlaubt(os.path.join(s, "ia-42-notiz.txt"), "lokal"),
              True, "Regelfall lokal"))

    p.append(("fertige Programmdatei wird abgewiesen",
              journal.pfad_erlaubt("/opt/dienst/programm.py", PROBE_ZIEL),
              False, "kein Temp-Ort — darf gar nicht erst ins Journal"))
    p.append(("Aufstieg per .. wird abgewiesen",
              journal.pfad_erlaubt("/tmp/ia-42/../../etc/passwd", PROBE_ZIEL),
              False, "sonst klettert man aus dem Temp-Ort heraus"))
    p.append(("relativer Serverpfad wird abgewiesen",
              journal.pfad_erlaubt("tmp/ia-42", PROBE_ZIEL), False,
              "Serverpfade sind absolut"))

    p.append(("Nachbarordner mit gleichem Praefix wird abgewiesen",
              journal.pfad_erlaubt(s + "-alt" + os.sep + "datei.txt", "lokal"),
              False, "startswith ohne Trenner trifft den Nachbarn mit"))

    p.append(("lokal ist immer ein gueltiges Ziel",
              konfig.LOKAL in konfig.namen(), True,
              "ohne Konfiguration muss das Paket vollstaendig lokal laufen"))
    p.append(("lokal gilt nicht als Fernziel",
              konfig.ist_fern(konfig.LOKAL), False,
              "sonst ginge ein lokales rm ueber ssh"))
    p.append(("konfiguriertes Ziel gilt als Fernziel",
              konfig.ist_fern(PROBE_ZIEL), True, "steht in der Konfiguration"))
    p.append(("unbekanntes Ziel gilt nicht als Fernziel",
              konfig.ist_fern("gibtsnicht"), False,
              "ein Tippfehler im Zielnamen darf nicht still zu lokal werden"))
    p.append(("unbekanntes Ziel steht nicht in der Namensliste",
              "gibtsnicht" in konfig.namen(), False,
              "argparse und eintragen() pruefen gegen diese Liste"))
    p.append(("Serverpfad eines unbekannten Ziels wird abgewiesen",
              journal.pfad_erlaubt("/tmp/ia-42-x", "gibtsnicht"), False,
              "ohne Konfiguration gibt es kein erlaubtes Fern-Praefix"))
    p.append(("Ziel ohne Schluessel liefert keine ssh-Basis",
              konfig.ssh_basis(PROBE_ZIEL) is None, True,
              "lieber liegen lassen als ohne Schluessel loeschen"))
    p.append(("Temp-Praefix kommt aus der Konfiguration",
              konfig.temp_praefix(PROBE_ZIEL) == "/tmp/ia-", True,
              "je Ziel einstellbar"))
    p.append(("Ziel ohne temp-Angabe bekommt die Vorgabe",
              konfig.temp_praefix("gibtsnicht") == konfig.TEMP_VORGABE, True,
              "fehlender Eintrag darf kein leeres Praefix ergeben"))

    p.extend(_konfigproben())
    p.extend(_hookproben())
    p.extend(_verdichtungsproben())
    p.extend(_gedaechtnisproben())
    p.extend(_zettelproben())
    p.extend(_sprachproben())
    p.extend(_tagproben())
    p.extend(_aktualisierungsproben())

    for befehl in ["rm -f /tmp/x", "mv a b", "cp a b", "touch x", "mkdir x",
                   "rmdir x", "unlink x", "ln -s a b", "chmod 644 x",
                   "chown u x", "dd if=a of=b", "truncate -s 0 x", "shred x",
                   "sed -i s/a/b/ x", "tee x", "curl http://example.invalid",
                   "wget http://example.invalid", "git reset --hard",
                   "git checkout -- x", "kill 1234", "pkill -f x",
                   "find . -name '*.tmp' -delete", "xargs rm < liste",
                   "systemctl restart dienst", "docker compose up -d",
                   "docker rm x", "apt-get install y", "pip install z",
                   "npm install", "make install", "ls > datei",
                   "ls >> datei", 'sh -c "rm -rf /"', "/usr/bin/rm x"]:
        p.append(("veraendernd erkannt: %s" % befehl,
                  abnahme.ist_veraendernd(befehl), True,
                  "eine Pruefung darf den Zustand nicht anfassen"))

    for befehl in ["sha256sum /opt/x/y.py | cut -d' ' -f1",
                   "grep -c '^def ' y.py",
                   "python3 -c 'import y'",
                   "systemctl is-active dienst",
                   "docker compose ps",
                   "docker ps -a",
                   "awk '$1 > 100 {print \"ja\"}'",
                   "wc -l datei",
                   "ls -l /opt/x",
                   "test -f /opt/x/y.py && echo da",
                   "cat /etc/hostname",
                   "confirm_firmware_version",
                   "echo 2>&1"]:
        p.append(("harmlos durchgelassen: %s" % befehl,
                  abnahme.ist_veraendernd(befehl), False,
                  "legitimer Pruefbefehl — Falschalarm macht ihn unbrauchbar"))

    tmp = tempfile.mkdtemp(prefix="ia-bom-abnahme-")
    try:
        punkte = os.path.join(tmp, "punkte.json")
        _bytes_schreiben(punkte, BOM + b"[]")
        _, aus = _skript(os.path.join(HIER, "abnahme.py"), punkte)
        p.append(("Pruefpunkte mit BOM werden gelesen",
                  "nichtleere Liste" in aus and "nicht lesbar" not in aus, True,
                  "eine mit PowerShell gespeicherte Datei galt als nicht lesbar"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    p.append(("Erwartung ohne Wahrheitswert gilt als nicht erfuellt",
              _erfuellt("ok", "ok"), False,
              "bool(ist) == bool(soll) liess jede nichtleere Antwort als Treffer durch"))
    p.append(("Wahrheitswerte werden streng verglichen",
              _erfuellt("ok", True) and not _erfuellt("", True) and _erfuellt(0, False),
              True, "Regelfall"))
    return p


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass
    rot = "--rot" in sys.argv
    ergebnisse = proben()
    bestanden, durchgefallen = 0, []
    print("=" * 72)
    if rot:
        print("GEGENPROBE (--rot): jede Erwartung umgekehrt. "
              "Dieser Lauf MUSS fehlschlagen.")
        print("=" * 72)
    for name, ist, soll, warum in ergebnisse:
        if _erfuellt(ist, soll, rot):
            bestanden += 1
            continue
        durchgefallen.append(name)
        if not isinstance(soll, bool):
            print("NICHT ERFUELLT  %s\n      -> Erwartung %r ist kein Wahrheitswert (%s)"
                  % (name, soll, warum))
        else:
            print("NICHT ERFUELLT  %s\n      -> ist %r, erwartet %r (%s)"
                  % (name, bool(ist), soll != rot, warum))
    print("=" * 72)
    print("Pruefprotokoll maschinell: %d bestanden, %d durchgefallen, %d gesamt"
          % (bestanden, len(durchgefallen), len(ergebnisse)))
    print("STATUS: %s" % ("GRUEN" if not durchgefallen else "ESKALATION"))
    return 1 if durchgefallen else 0


if __name__ == "__main__":
    sys.exit(main())
