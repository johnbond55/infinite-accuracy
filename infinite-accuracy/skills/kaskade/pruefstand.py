#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefstand.py — Proben gegen die eigenen Schranken.

Faehrt die Schranken dieses Pakets gegen Proben, deren Ausgang vorher
feststeht — in beiden Richtungen: was durchgehen muss und was blocken muss.
Verdichtung, Zettelkasten und Installer werden Ende-zu-Ende in temporaeren
Ordnern geprobt.

Begruendungen und Fallen: doku/pruefstand.md

Aufruf:  pruefstand.py          alle Proben
         pruefstand.py --rot    Gegenprobe, kehrt jede Erwartung um;
                                dieser Lauf muss fehlschlagen
Exit:    0 = alle bestanden · 1 = mindestens eine Probe durchgefallen
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import abnahme                                                    # noqa: E402
import journal                                                    # noqa: E402
import konfig                                                     # noqa: E402

PROBE_ZIEL = "probeziel"
konfig.setzen_fuer_proben({PROBE_ZIEL: {"ssh": "nutzer@rechner.invalid",
                                        "keys": [], "temp": "/tmp/ia-"}})


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
              ernte.geheimnisse_tilgen("Das Passwort steht in der .env-Datei.")[1],
              0, "Fliesstext ist keine Zuweisung — Fehlalarm zerstoert Protokolle"))
    p.append(("Feldname bleibt nach dem Tilgen stehen",
              "api_key" in ernte.geheimnisse_tilgen('"api_key": "' + "x" * 20 + '"')[0],
              True, "ohne Feldname ist der Zusammenhang verloren"))
    p.append(("Schonfrist 0 gibt alles frei",
              ernte._schonfrist_grenze(["abc", "def"], 0), 2,
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
        p.append(("Tilgung im Transkript greift", n, 1, "Geheimnis in einer alten Zeile"))
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
        p.append(("Kontext kommt aus der usage-Zeile", tok, 150000 == tok,
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
        p.append(("Ablage-Auftrag ueberlebt geschweifte Klammern",
                  "{eigene}" in regelschub.auftrag_text(200000, "x{eigene}y", "e.json"), True,
                  "str.format wuerde hier abstuerzen"))

        konf = os.path.join(tmp, "konf")
        os.makedirs(konf)
        with open(os.path.join(konf, "konfig.json"), "w", encoding="utf-8") as f:
            json.dump({"pfade": {"sitzungen": os.path.join(tmp, "sitzungen"),
                                 "state": os.path.join(tmp, "state"),
                                 "zettelkasten": os.path.join(tmp, "zk")}}, f)
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

    inst, paket = _installer_laden()
    if inst is None:
        p.append(("Installer-Proben (uebersprungen: kein vollstaendiges Paket)", True, True,
                  "in einer Projektinstallation liegt nur ein Teil des Pakets"))
        return p

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
    p.extend(_zettelproben())
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
        if rot:
            soll = not soll
        ok = (bool(ist) == bool(soll))
        if ok:
            bestanden += 1
        else:
            durchgefallen.append(name)
            print("NICHT ERFUELLT  %s\n      -> ist %r, erwartet %r (%s)"
                  % (name, bool(ist), bool(soll), warum))
    print("=" * 72)
    print("Pruefprotokoll maschinell: %d bestanden, %d durchgefallen, %d gesamt"
          % (bestanden, len(durchgefallen), len(ergebnisse)))
    print("STATUS: %s" % ("GRUEN" if not durchgefallen else "ESKALATION"))
    return 1 if durchgefallen else 0


if __name__ == "__main__":
    sys.exit(main())
