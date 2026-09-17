---
name: sprachregel
description: Reduziert Text auf das notwendige, leicht lesbare Destillat — Ergebnis zuerst, keine Floskel, keine Wiederholung, kein Schlusssatz. Verwenden, sobald Text für Menschen entsteht oder überarbeitet wird: Antwort, Dokumentation, Notiz, Commit-Nachricht, Oberflächen-, Mail- und Fehlertext. Auch bei den Stichworten Floskel, KI-Sprache, Füllwort, kürzen, straffen, Sprachregel, BLUF, Destillat, Textprüfung.
---

# sprachregel

Ergebnis im ersten Satz, Beleg danach, Schluss ohne Zusammenfassung. Jeden Satz
streichen, der ohne Verlust an Inhalt wegfallen kann.

Begründungen und Fallen: `../kaskade/doku/sprachregel.md`

## Geltung

Für jeden Text, den ein Mensch liest: Antwort im Chat, Dokumentation, Notiz,
Destillat, Commit-Nachricht, Oberflächentext, Fehlermeldung, Mail, Bericht.

**Nicht angetastet** — hier wäre Glätten Fälschung:

| Zone | warum |
|---|---|
| wörtliches Zitat, Fremdtext | fremde Aussage, fremder Wortlaut |
| Programmausgabe, Protokoll, Prüfbefehl und seine Ausgabe | Beweisstück |
| Systemfehlermeldung | muss suchbar bleiben |
| Rechts- und Lizenztext, Formulierung aus einer Vorschrift | amtlicher Wortlaut |
| Code, Bezeichner, Pfade | Funktion |
| Messwert, Tabellenzelle mit Zahl | Datum, nicht Sprache |

## Regeln

### 1 Aufbau

- Erster Satz: Ergebnis, Antwort oder Fehlschlag. Begründung danach.
- Keine Einleitung, keine Wiederholung der Frage, keine Ankündigung des Folgenden.
- Ab drei Größen Tabelle oder Aufzählung statt Fließtext.
- Jede Angabe genau einmal. Was in der Tabelle steht, steht nicht auch im Text.
- Kein Schlusssatz, keine Zusammenfassung, kein Ausblick. Am Ende steht höchstens
  die offene Frage oder der nächste Schritt.
- Antwortlänge an der Frage messen: Entscheidungsfrage wird mit Ja oder Nein
  beantwortet, dann belegt.
- Kein Bericht über die eigene Mühe. Ergebnis und Beweis, nicht der Weg dorthin.

### 2 Wortwahl

- Verb statt Substantivierung: `prüfen`, nicht `eine Prüfung durchführen`.
- Zahl statt Wertung: `drei Fundstellen`, nicht `einige`.
- Kein Werbewort ohne Messung: `nahtlos`, `robust`, `umfassend`, `intuitiv`.
- Kein Füllwort, kein Weichmacher: `eigentlich`, `grundsätzlich`, `im Prinzip`, `letztlich`.
- Keine Höflichkeits- und Chatbot-Floskel, keine Schlussfloskel.
- Keine Wichtigkeitsbehauptung; statt „wichtig" die Folge nennen.
- Ein Ding, ein Wort. Synonymwechsel für dieselbe Sache ist verboten.
- Fachwort des Lesers, nicht das Wort des Systems.

### 3 Satzbau

- Aktiv mit benanntem Handelndem. Passiv nur, wenn der Handelnde unbekannt ist
  oder nicht zur Sache gehört.
- Ein Gedanke je Satz, höchstens ein Nebensatz, unter 25 Wörtern.
- Kein Ding handelt wie ein Mensch: nicht `das System entscheidet`.
- Positiv formulieren statt doppelter Verneinung.
- Kein Absolutwort als Verstärker: `ausnahmslos`, `jederzeit`, `ohne Ausnahme`.
- Satzlängen mischen; keine Reihe gleich gebauter Sätze.

### 4 Muster

| Muster | statt dessen |
|---|---|
| `nicht X, sondern Y` | Y sagen |
| Aufzählung dessen, was etwas **nicht** ist | sagen, was es ist |
| rhetorische Frage als Aufhänger | die Aussage |
| Dreiergruppe um der Figur willen | so viele Punkte, wie es Sachen gibt |
| Kurzsatzkette zur Dramatik | ein vollständiger Satz |
| Ankündigung: `hier ist`, `ich zeige dir` | die Sache selbst |
| Gedankenstrich als Ersatz für Satzbau | Komma oder Punkt; höchstens einer je Absatz |
| Emoji, Fettung ganzer Sätze | Fettung nur für Begriff oder Urteil |
| Überschrift und Aufzählung als Schmuck | Liste nur bei mindestens zwei gleichrangigen Punkten |

## Verfahren

1. Schreiben, Ergebnis zuerst.
2. Streichprobe je Satz: entfernen — fehlt etwas? Nein, dann bleibt er entfernt.
3. Vor dem Absenden die Selbstprüfung.
4. Bei Text mit Bestand — Dokumentation, Notiz, Commit-Nachricht, Oberflächentext —
   `pruefe.py` fahren. Jeder Fund der Stufe A wird beseitigt; ein Hinweis der
   Stufe B wird beseitigt oder er fällt in eine der Zonen oben.

```
python pruefe.py <datei> [...]      Funde je Zeile, Zählwerk, Urteil
python pruefe.py --liste            vollständiger Regelkatalog mit allen Wörtern
python pruefe.py --json <datei>     Funde als JSON
python pruefe.py --schwelle 0 …     erlaubte Hinweise der Stufe B, Vorgabe 10
```

Das Werkzeug liest Dateien, keine Standardeingabe. Ausgenommene Zonen erkennt es
selbst: Codeblock, Zitatzeile, Kopfblock, Verweisziel. `--alles` prüft auch sie.

## Selbstprüfung

1. Steht das Ergebnis im ersten Satz?
2. Wiederholt ein Satz, was daneben schon steht?
3. Steht eine Angabe zweimal, einmal in der Tabelle und einmal im Text?
4. Hat der letzte Absatz eine Zusammenfassung? Dann weg.
5. Gibt es ein Wort, das nichts misst und nichts benennt?
6. Hat jeder Satz einen benannten Handelnden?
7. Trägt jede Aufzählung mindestens zwei gleichrangige Punkte?
8. Was kann noch gestrichen werden, ohne dass Inhalt fehlt?

## Dateien

| Datei | Zweck |
|---|---|
| `pruefe.py` | prüft Text gegen den Katalog, zählt, urteilt; `--liste` druckt den Katalog |
| `../kaskade/doku/sprachregel.md` | warum die Regeln so geschnitten sind |
