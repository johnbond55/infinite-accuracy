# Doku zu infinite-accuracy

**Der Code trägt die Mechanik, diese Doku trägt das Warum.**

In den Python-Dateien steht kein erklärender Kommentar mehr — weder die
Begründung, warum eine Zeile so aussieht, noch die Geschichte, die dazu geführt
hat. Beides steht hier. Wer eine Zeile ändert, liest vorher den zugehörigen
Abschnitt.

Diese Trennung ist eine Entscheidung, keine Nachlässigkeit: Code soll ohne Beiwerk lesbar und lauffähig sein; Begründungen
gehören dorthin, wo man sie am Stück liest und pflegen kann.

## Wo was steht

| Datei | Doku | Inhalt |
|---|---|---|
| `journal.py` | [journal.md](journal.md) | die vier Schranken, Metazeichen, `shlex.quote`, Verzeichnisgrenze, MSYS-Falle |
| `abnahme.py` | [abnahme.md](abnahme.md) | Read-only-Heuristik, Lookbehind, Verbliste, Vergleichsarten, gebundener Wortlaut |
| `pruefstand.py` | [pruefstand.md](pruefstand.md) | beide Prüfrichtungen, `--rot`, Nebenwirkungsfreiheit |
| `../../hooks/ernte.py` | [ernte.md](ernte.md) | Inode statt Tausch, vier Sicherungsnetze, Schonfrist, Tilgungsmuster |
| `../../hooks/regelschub.py` | [regelschub.md](regelschub.md) | replace statt format, fortlaufender Zähler, der vierte Auslöser |
| `../../hooks/wiedervorlage.py` | [wiedervorlage.md](wiedervorlage.md) | Reihenfolge, Budgets, Altershinweis |
| `../../hooks/gedaechtnis.py` | [gedaechtnis.md](gedaechtnis.md) | Kurzindex vs. Register, melden statt tilgen, Platzhalterfilter |
| — | [hintergrund.md](hintergrund.md) | warum delegiert und maschinell abgenommen wird |
| `SKILL.md` | — | trägt seine Erklärung selbst; es ist Anleitung, nicht Code |

Die Agenten `ia-ausfuehrer` und `ia-pruefer` liegen in `.claude/agents/` und
sind ebenfalls selbsterklärend — sie sind Prompts, kein Programm.

## Aufbau jeder Doku-Datei

1. **Wozu** die Datei da ist
2. **Je Symbol** (Funktion, Konstante): warum es so gebaut ist, mit Anlass
3. **Was beim Ändern schiefgehen kann** — eine Tabelle am Ende

Der letzte Abschnitt ist der wichtigste. Er nennt die Vereinfachungen, die
naheliegend aussehen und einen Fehler wieder einbauen.

## Selbstprüfung

```
python pruefstand.py          ->  62 bestanden, 0 durchgefallen   STATUS: GRUEN
python pruefstand.py --rot    ->  0 bestanden, 62 durchgefallen   STATUS: ESKALATION
```

Beide Läufe gehören zusammen. Der zweite weist nach, dass der erste überhaupt
etwas entscheidet.
