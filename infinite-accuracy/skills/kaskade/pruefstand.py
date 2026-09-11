#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefstand.py — Proben gegen die eigenen Schranken.

Faehrt die Schranken dieses Skills gegen Proben, deren Ausgang vorher
feststeht — in beiden Richtungen: was durchgehen muss und was blocken muss.

Begruendungen und Fallen: doku/pruefstand.md

Aufruf:  pruefstand.py          alle Proben
         pruefstand.py --rot    Gegenprobe, kehrt jede Erwartung um;
                                dieser Lauf muss fehlschlagen
Exit:    0 = alle bestanden · 1 = mindestens eine Probe durchgefallen
"""
import json
import os
import sys
import tempfile

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


def _hooks_laden():
    """ernte.py und regelschub.py, falls sie neben dem Skill liegen."""
    for kandidat in (os.path.join(os.path.dirname(os.path.dirname(HIER)), "hooks"),
                     os.path.join(os.path.dirname(HIER), "hooks")):
        if os.path.isfile(os.path.join(kandidat, "ernte.py")):
            if kandidat not in sys.path:
                sys.path.insert(0, kandidat)
            try:
                import ernte
                import regelschub
                import gedaechtnis
                return ernte, regelschub, gedaechtnis
            except Exception:                                     # noqa: BLE001
                return None, None, None
    return None, None, None


def _konfigproben():
    """Proben fuer den Konfigurationszugang."""
    p = []
    p.append(("unbekannter Konfigurationswert wirft",
              _wirft(lambda: konfig.zahl("gibtsnicht")), True,
              "ein Tippfehler im Namen darf nicht still eine 0 ergeben"))
    p.append(("bekannter Wert kommt aus der Vorgabe",
              konfig.zahl("schwelle_zeichen") == konfig.VORGABEN["schwelle_zeichen"],
              True, "ohne konfig.json gelten die eingebauten Werte"))
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
    """Proben fuer die Hooks — nur wenn sie neben dem Skill liegen."""
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
    zeile = json.dumps({"message": {"content": [
        {"type": "text", "text": "x" * 10},
        {"type": "thinking", "thinking": "y" * 5}]}})
    p.append(("Kontextzaehler zaehlt Text und Denken",
              regelschub._zeichen_der_zeile(zeile), 15,
              "Denken landet im Fenster und muss mitgezaehlt werden"))
    p.append(("Kontextzaehler vertraegt Schrott",
              regelschub._zeichen_der_zeile("kein json"), 0,
              "eine kaputte Zeile darf den Zaehler nicht kippen"))
    p.append(("Destillatauftrag ueberlebt geschweifte Klammern",
              "{eigene}" in regelschub.destillat_auftrag(4, "x{eigene}y"), True,
              "str.format wuerde hier abstuerzen — deshalb replace"))
    for ph in ["{env:KEY}", "$MEINVAR", "<dein-token>", "changeme", "xxxxx"]:
        p.append(("Platzhalter loest keinen Alarm aus: %s" % ph,
                  bool(ged.PLATZHALTER.match(ph)), True,
                  "eine Warnung, die nie stimmt, wird ignoriert"))
    p.append(("echter Wert gilt nicht als Platzhalter",
              bool(ged.PLATZHALTER.match("A7f3K9x2Lm4Qp8Zw")), False,
              "sonst uebersieht die Meldung genau das, was sie finden soll"))
    return p


def _wirft(f):
    try:
        f()
        return False
    except Exception:                                             # noqa: BLE001
        return True


def proben():
    """Liste von (name, ist_wahr, erwartet, warum). Keine Nebenwirkungen."""
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
