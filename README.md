# infinite-accuracy

Ein Claude-Code-Plugin für lange Sitzungen. Es hält den Kontext klein, legt beim
Neustart den letzten Stand wieder vor, lagert Arbeitsgänge an kleinere Modelle
aus und prüft jedes Ergebnis maschinell nach.

## Was es macht

**Der Kontext bleibt klein.** Bei jedem Prompt wird mitgezählt, wie viel Kontext
die Sitzung wirklich kostet. Ist die Schwelle erreicht, fordert das Plugin ein
kurzes Destillat an und schlägt `/compact` vor — der Gesprächsfaden bleibt, nur
der Ballast geht.

**Nichts geht verloren.** Bei jedem Sitzungsende und vor jeder Komprimierung
entsteht ein Rohprotokoll: Titel, was verlangt wurde, angefasste Dateien,
ausgeführte Kommandos, letzte Antwort. Rein mechanisch, ohne Modellaufruf. Beim
nächsten Start wird der jüngste Stand wieder vorgelegt.

**Geheimnisse werden aus dem Transkript getilgt.** API-Schlüssel, Tokens,
private Schlüssel und Passwortfelder werden durch `<Secret getilgt: art>`
ersetzt. Die letzten rund 30.000 Tokens bleiben unberührt — das ist der lebende
Chat.

**Regeln verblassen nicht.** Deine Arbeitsregeln stehen in einer Datei und
werden bei jedem Prompt neu eingespeist, statt am Sitzungsanfang zu verpuffen.

**Delegieren mit Abnahme.** Das planende Modell schneidet einen Arbeitsgang zu
und gibt ihn an ein kleineres. Ein Skript führt vorher festgelegte Prüfbefehle
aus und vergleicht die Ausgabe — es zählt, es urteilt nicht. Fällt ein Kriterium
durch, macht das planende Modell den Arbeitsgang selbst.

**Temporäres wird registriert, nicht gesucht.** Arbeitsdateien werden beim
Anlegen eingetragen und später aus dieser Liste gelöscht — kein Suchmuster,
eine Datei je Befehl.

## Installation

```
/plugin marketplace add <konto>/infinite-accuracy
/plugin install infinite-accuracy@infinite-accuracy
```

Danach sind verfügbar: der Skill `/infinite-accuracy:kaskade`, die Agenten
`ia-ausfuehrer` und `ia-pruefer` und vier Hooks.

## Einrichtung

Ohne Konfiguration läuft alles lokal und mit eingebauten Vorgaben. Zum Anpassen:

```
/infinite-accuracy:einrichten
```

Claude fragt nach den Zielsystemen und legt die Konfiguration an. Von Hand geht
es auch — die Dateien liegen in `<projekt>/.claude/infinite-accuracy/`:

| Datei | Wofür | Vorlage |
|---|---|---|
| `regeln.md` | wird bei jedem Prompt eingespeist | `vorlagen/regeln.beispiel.md` |
| `ziele.json` | Rechner für entfernte Arbeitsgänge | `vorlagen/ziele.beispiel.json` |
| `konfig.json` | Schwellen, Budgets, Fristen | `vorlagen/konfig.beispiel.json` |
| `destillat.md` | Wortlaut des Schnittauftrags | — |
| `register-texte.json` | Überschriften des Gedächtnisindex | `vorlagen/register-texte.beispiel.json` |

Prüfen, was erkannt wurde:

```
python infinite-accuracy/skills/kaskade/konfig.py
```

## Was das Plugin auf deinem Rechner ändert

- Es legt `<projekt>/.claude/infinite-accuracy/` an — dort liegen deine
  Konfiguration, die Sitzungsprotokolle und das Aufräum-Journal.
- **Es schreibt in die Transkriptdatei der Sitzung**, um Geheimnisse zu tilgen.
  Das geschieht in dieselbe Datei (nicht durch Tausch), mit vier Sicherungen:
  Gegenprobe auf gültiges JSON je Zeile, gleichbleibende Zeilenzahl, Kopie vor
  dem Schreiben, Rollback bei Fehler. Abschaltbar über `konfig.json`.
- Es registriert Hooks an SessionStart, UserPromptSubmit, PreCompact und
  SessionEnd.
- Es führt **Prüfbefehle wirklich aus** — lokal in einer Shell, auf
  konfigurierten Zielsystemen über SSH. Verändernde Befehle werden abgewiesen;
  diese Prüfung ist eine Heuristik und kein Beweis.

Es sendet nichts nach außen, liest keine Zugangsdaten und verändert keine
Dateien außerhalb der genannten Orte.

## Selbstprüfung

```
python infinite-accuracy/skills/kaskade/pruefstand.py         # 103 bestanden, 0 durchgefallen
python infinite-accuracy/skills/kaskade/pruefstand.py --rot   # muss fehlschlagen
```

Der zweite Lauf kehrt jede Erwartung um. Er weist nach, dass der erste
überhaupt etwas entscheidet.

## Inhalt

```
skills/kaskade/       SKILL.md, abnahme.py, journal.py, konfig.py, pruefstand.py
skills/kaskade/doku/  warum jeder Baustein so gebaut ist — für Weiterentwicklung
skills/einrichten/    Einrichtungsdialog
agents/               ia-ausfuehrer (führt aus), ia-pruefer (nimmt ab)
hooks/                ernte, regelschub, wiedervorlage, gedaechtnis, nachlauf
vorlagen/             Beispielkonfigurationen
```

| Hook | Ereignis | Aufgabe |
|---|---|---|
| `wiedervorlage.py` | SessionStart | letzten Stand vorlegen, alte Transkripte härten |
| `regelschub.py` | UserPromptSubmit | Regeln einspeisen, Kontextlast messen, Schnitt anfordern |
| `ernte.py` | PreCompact, SessionEnd | Rohprotokoll erzeugen, Transkript härten |
| `nachlauf.py` | SessionEnd | verwaiste Arbeitsdateien löschen |
| `gedaechtnis.py` | — (CLI) | Kurzindex bauen, Auffälligkeiten melden |

Sprache: Deutsch, durchgängig. Python 3, nur Standardbibliothek.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
