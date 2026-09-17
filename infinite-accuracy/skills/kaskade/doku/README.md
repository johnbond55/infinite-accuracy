# Doku zu infinite-accuracy

**Der Code trägt die Mechanik, diese Doku trägt das Warum.**

In den Python-Dateien steht kein erklärender Kommentar — weder die Begründung,
warum eine Zeile so aussieht, noch die Geschichte, die dazu geführt hat. Beides
steht hier. Wer eine Zeile ändert, liest vorher den zugehörigen Abschnitt.

## Wo was steht

| Datei | Doku | Inhalt |
|---|---|---|
| `journal.py` | [journal.md](journal.md) | die vier Schranken, Metazeichen, `shlex.quote`, Verzeichnisgrenze, MSYS-Falle |
| `abnahme.py` | [abnahme.md](abnahme.md) | Read-only-Heuristik, Lookbehind, Verbliste, Vergleichsarten, gebundener Wortlaut |
| `konfig.py` | [konfig.md](konfig.md) | Zahlen, Schalter, Ablageorte, unbekannte Namen |
| `pruefstand.py` | [pruefstand.md](pruefstand.md) | beide Prüfrichtungen, `--rot`, Nebenwirkungen nur in Temp-Ordnern, Tag-Proben |
| `../../hooks/regelschub.py` | [regelschub.md](regelschub.md) | replace statt format, usage-Zeile statt Zeichen, Ablage-Auftrag |
| `../../hooks/ernte.py` | [ernte.md](ernte.md) | Riegel und Anweisung, Inode statt Tausch, Zeilentrennung, Tilgungsmuster |
| `../../hooks/wiedervorlage.py`, `haertung.py` | [wiedervorlage.md](wiedervorlage.md) | zwei Wege je Quelle, abgekoppelte Härtung, Nachernte, Budgets |
| `../../hooks/gedaechtnis.py` | [gedaechtnis.md](gedaechtnis.md) | Kurzindex vs. Register, melden statt tilgen, Platzhalterfilter |
| `../../hooks/aktualisierung.py`, `../../installieren.py` | [aktualisierung.md](aktualisierung.md) | Update-Weg, Prüfungen vor dem Schreiben, Rückbau, Veröffentlichen |
| `../zettel/zettel.py` | [zettel.md](zettel.md) | Schichten, Entscheidungen beim Nachbau, Windows |
| `../sprachregel/pruefe.py` | [sprachregel.md](sprachregel.md) | zwei Stufen, ausgenommene Zonen, Maskierung, Listentrennung, Grenzen |
| — | [verdichtung.md](verdichtung.md) | wie die Verdichtung gesteuert wird und worauf das beruht |
| — | [hintergrund.md](hintergrund.md) | warum delegiert und maschinell abgenommen wird |
| `SKILL.md` | — | trägt seine Erklärung selbst; es ist Anleitung, nicht Code |
| `LICENSE`, `EUPL-1.2-DE.txt` | — | Lizenz EUPL-1.2, englische und amtliche deutsche Fassung, gleichwertig (Art. 13); im Projekt unter `.claude/infinite-accuracy/paket/` |

Die Agenten `ia-ausfuehrer`, `ia-leser` und `ia-pruefer` sind Prompts, kein
Programm, und erklären sich selbst.

## Aufbau jeder Doku-Datei

1. **Wozu** die Datei da ist
2. **Je Baustein:** warum es so gebaut ist, mit Anlass
3. **Was beim Ändern schiefgehen kann** — eine Tabelle am Ende

Der letzte Abschnitt ist der wichtigste. Er nennt die Vereinfachungen, die
naheliegend aussehen und einen Fehler wieder einbauen.

## Selbstprüfung

```
python pruefstand.py          ->  STATUS: GRUEN, 0 durchgefallen
python pruefstand.py --rot    ->  STATUS: ESKALATION
```

Beide Läufe gehören zusammen. Der zweite weist nach, dass der erste überhaupt
etwas entscheidet.
