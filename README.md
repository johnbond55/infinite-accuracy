# infinite-accuracy

Ein Claude-Code-Paket für lange, der Absicht nach endlose Arbeitssitzungen. Es
steuert die Verdichtung des Kontexts, legt Wissen in einem Zettelkasten ab,
lagert Arbeitsgänge an kleinere Modelle aus, prüft jedes Ergebnis maschinell
nach und hält die Sprache knapp.

## Was es macht

**Der Faden reißt nicht ab.** Ab einer Kontextschwelle fordert das Paket am
Userhalt eine Ablage an: Einträge im Zettelkasten und ein kurzes Destillat. Die
Verdichtung von Claude Code läuft danach von selbst — ein Hook gibt ihr vor, was
erhalten bleibt, schiebt sie auf, solange nichts abgelegt ist, und prüft
hinterher an einer Kennmarke, ob die Anweisung übernommen wurde.

**Früheres wird nachgeschlagen, nicht geraten.** Der Zettelkasten — Journal,
Dossiers mit Besuchs-Log, Erkenntnis-Index, Schlagwort-Register — liegt als
Markdown im Projekt. Gesucht wird über Dossiername, Schlagwort und Volltext;
Trefferseiten werden im Ganzen gelesen.

**Nichts geht verloren.** Bei jedem Sitzungsende und vor jeder Verdichtung
entsteht ein Rohprotokoll, rein mechanisch. Sitzungen ohne gemeldetes Ende
werden im Hintergrund nachgeerntet.

**Geheimnisse werden aus dem Transkript getilgt.** API-Schlüssel, Tokens,
private Schlüssel und Passwortfelder werden durch `<Secret getilgt: art>`
ersetzt. Die letzten rund 30.000 Token bleiben unberührt — das ist der lebende
Chat.

**Regeln verblassen nicht.** Deine Arbeitsregeln stehen in einer Datei und
werden bei jedem Prompt neu eingespeist.

**Der Text bleibt knapp.** Der Skill `sprachregel` setzt das Ergebnis in den
ersten Satz und streicht Füllwort, Werbewort, Floskel und Schlusssatz. Ein
Prüfskript misst jeden Text gegen den Katalog und urteilt in zwei Stufen:
Stufe A wird beseitigt, Stufe B zählt gegen eine Schwelle. Zitat,
Programmausgabe, Fehlermeldung und Rechtstext bleiben unberührt.

**Delegieren mit Abnahme.** Das planende Modell schneidet einen Arbeitsgang zu
und gibt ihn an ein kleineres. Ein Skript führt vorher festgelegte Prüfbefehle
aus und vergleicht die Ausgabe — es zählt, es urteilt nicht. Fällt ein Kriterium
durch, macht das planende Modell den Arbeitsgang selbst.

**Temporäres wird registriert, nicht gesucht.** Arbeitsdateien werden beim
Anlegen eingetragen und später aus dieser Liste gelöscht — kein Suchmuster,
eine Datei je Befehl.

**Updates kommen mit Rückfrage.** Eine Projektinstallation sieht beim
Sitzungsstart nach, ob auf GitHub eine neuere Fassung liegt, und fragt. Installiert
wird mit Prüfsummen, Sicherung und Rückbau.

## Installation

### Als Plugin

```
/plugin marketplace add johnbond55/infinite-accuracy
/plugin install infinite-accuracy@infinite-accuracy
```

### Im Projekt — reist mit dem Projektordner

Archiv oder Klon holen, dann:

```
python infinite-accuracy/installieren.py --projekt <projektordner> --erstinstallation --einstellungen
```

Hooks landen in `.claude/hooks/`, Skills in `.claude/skills/`, Agenten in
`.claude/agents/`. `--einstellungen` ergänzt die Hook-Einträge in
`.claude/settings.json`. Spätere Updates meldet der Sitzungsstart.

## Verdichtung einstellen

In `.claude/settings.json` des Projekts (Vorlage `vorlagen/einstellungen.beispiel.json`):

| Schlüssel | Wert |
|---|---|
| `autoCompactEnabled` | `true` |
| `autoCompactWindow` | `250000` |
| `env.DISABLE_AUTO_COMPACT` | nicht setzen, auch nicht in `~/.claude/settings.json` |

Das Modell der Sitzung — Fable oder Opus — mit `[1m]` wählen; sonst kappt das
200.000-Fenster den Wert. Warum diese Zahlen: `skills/kaskade/doku/verdichtung.md`.

## Einrichtung

Ohne Konfiguration läuft alles lokal und mit eingebauten Vorgaben. Zum Anpassen:

```
/infinite-accuracy:einrichten
```

Von Hand: die Dateien liegen in `<projekt>/.claude/infinite-accuracy/`.

| Datei | Wofür | Vorlage |
|---|---|---|
| `regeln.md` | wird bei jedem Prompt eingespeist | `vorlagen/regeln.beispiel.md` |
| `ziele.json` | Rechner für entfernte Arbeitsgänge | `vorlagen/ziele.beispiel.json` |
| `konfig.json` | Schwellen, Budgets, Schalter, Ablageorte | `vorlagen/konfig.beispiel.json` |
| `destillat.md` | eigener Wortlaut des Ablage-Auftrags | — |
| `register-texte.json` | Überschriften des Gedächtnisindex | `vorlagen/register-texte.beispiel.json` |
| `installation.json` | Teile, die nicht installiert werden | `vorlagen/installation.beispiel.json` |

Prüfen, was erkannt wurde: `python infinite-accuracy/skills/kaskade/konfig.py`

## Was das Paket auf deinem Rechner ändert

- Es legt `<projekt>/.claude/infinite-accuracy/` und `<projekt>/.claude/zettelkasten/`
  an — Konfiguration, Sitzungsprotokolle, Standdateien, Zettelkasten.
- **Es schreibt in die Transkriptdatei der Sitzung**, um Geheimnisse zu tilgen —
  in dieselbe Datei, mit Gegenprobe je Zeile, gleichbleibender Zeilenzahl,
  Kopie vor dem Schreiben und Rollback bei Fehler.
- Es registriert Hooks an SessionStart, UserPromptSubmit, PreCompact und
  SessionEnd. Der PreCompact-Hook kann eine automatische Verdichtung aufschieben
  (Exit 2) und gibt ihr eine Anweisung mit. Diese Wirkung ist in Claude Code
  beobachtet, nicht dokumentiert — die Kennmarke meldet, wenn sie ausbleibt.
- Es führt **Prüfbefehle wirklich aus** — lokal in einer Shell, auf
  konfigurierten Zielsystemen über SSH. Verändernde Befehle werden abgewiesen;
  diese Prüfung ist eine Heuristik und kein Beweis.
- Eine Projektinstallation fragt höchstens alle 12 Stunden
  `raw.githubusercontent.com` nach `version.json` (abschaltbar mit
  `"aktualisierung": "aus"` in `konfig.json`) und lädt ein Archiv nur nach deiner
  Zustimmung.

Sonst sendet es nichts nach außen, liest keine Zugangsdaten und verändert keine
Dateien außerhalb der genannten Orte.

## Selbstprüfung

```
python infinite-accuracy/skills/kaskade/pruefstand.py         # STATUS: GRUEN
python infinite-accuracy/skills/kaskade/pruefstand.py --rot   # muss fehlschlagen
```

Der zweite Lauf kehrt jede Erwartung um. Er weist nach, dass der erste
überhaupt etwas entscheidet.

## Inhalt

```
installieren.py       installiert und ersetzt das Paket in einem Projekt
version.json          Version und Änderungen — daran misst die Update-Prüfung
PRUEFSUMMEN.json      Prüfsummen aller Paketdateien
LICENSE               EUPL-1.2 — reist mit dem Paket und wird mitinstalliert
EUPL-1.2-DE.txt       amtliche deutsche Fassung der EUPL — reist mit und wird mitinstalliert
skills/kaskade/       SKILL.md, abnahme.py, journal.py, konfig.py, pruefstand.py
skills/kaskade/doku/  warum jeder Baustein so gebaut ist
skills/zettel/        Zettelkasten: SKILL.md, zettel.py
skills/sprachregel/   Sprachregeln und Textprüfer: SKILL.md, pruefe.py
skills/einrichten/    Einrichtungsdialog
agents/               ia-ausfuehrer (führt aus), ia-leser (liest), ia-pruefer (nimmt ab)
hooks/                regelschub, ernte, wiedervorlage, haertung, nachlauf, gedaechtnis, aktualisierung
vorlagen/             Beispielkonfigurationen
```

| Hook | Ereignis | Aufgabe |
|---|---|---|
| `regelschub.py` | UserPromptSubmit | Regeln einspeisen, Kontextlast messen, Ablage anfordern |
| `ernte.py` | PreCompact, SessionEnd | Riegel, Anweisung mit Kennmarke, Rohprotokoll, Tilgung |
| `wiedervorlage.py` | SessionStart | Stand vorlegen — beim Start und nach jeder Verdichtung |
| `haertung.py` | — (von wiedervorlage gestartet) | ältere Transkripte härten, nachernten, Zettel-Waisen zählen |
| `nachlauf.py` | SessionEnd | verwaiste Arbeitsdateien löschen |
| `gedaechtnis.py` | — (CLI) | Kurzindex bauen, Auffälligkeiten melden |
| `aktualisierung.py` | — (von wiedervorlage) | nach Updates fragen, Installation anstoßen |

Sprache: Deutsch, durchgängig. Python 3.8 oder neuer, nur Standardbibliothek.

## Lizenz

Copyright (c) 2026 Johannes Volmer

Licensed under the EUPL — European Union Public Licence, Version 1.2,
siehe [LICENSE](LICENSE). SPDX-Kennung: `EUPL-1.2`.

Die EUPL gilt in 23 Sprachfassungen gleichwertig. Die deutsche liegt als
[EUPL-1.2-DE.txt](EUPL-1.2-DE.txt) bei — unveraendert von der Europaeischen
Kommission uebernommen — und steht im Amtsblatt der Europaeischen Union
(CELEX 32017D0863).

Was das heisst: **Verwenden** darf das Werkzeug jeder, auch im Betrieb und
auch kommerziell, ohne jede Pflicht. Wer eine **veraenderte Fassung
weitergibt**, muss sie wieder unter der EUPL oder einer der im Anhang
genannten Lizenzen offenlegen. Was du **mit** dem Werkzeug erarbeitest,
gehoert dir — mit einer Ausnahme: die Dateien, die dieses Paket selbst
mitbringt und die die Installation nach `.claude/` kopiert, bleiben unter
dieser Lizenz.

Fassungen bis einschliesslich 2.0.1 wurden unter der MIT-Lizenz
veroeffentlicht und bleiben unter dieser Lizenz verfuegbar.
