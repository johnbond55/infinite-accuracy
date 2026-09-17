# sprachregel

`../sprachregel/SKILL.md` trägt die Regeln, `../sprachregel/pruefe.py` prüft
Text gegen sie. Diese Datei sagt, warum beides so geschnitten ist.

## Wozu

Ein Sprachmodell füllt Text mit Mustern, die niemand gelesen haben will:
Einleitung vor der Antwort, Wiederholung der Frage, Werbewörter, Zusammenfassung
am Ende. Wer diese Muster einzeln im Gespräch rügt, bekommt sie in der nächsten
Sitzung zurück. Ein Regeltext mit maschineller Probe hält länger als eine
Ermahnung.

## Warum eine Regel und kein Stilwunsch

„Fass dich kurz" ist keine Anweisung, sondern eine Stimmung. Die Regeln des
Skills nennen deshalb je Fall das Ziel und den Ersatz: welches Wort weg muss,
was an seine Stelle tritt, welche Stelle im Text welche Aufgabe hat. Eine Regel,
die keinen Ersatz nennt, führt zu Text, der an anderer Stelle wieder ausufert.

## Warum das Ergebnis im ersten Satz steht

Der Leser entscheidet nach dem ersten Satz, ob er weiterliest. Steht dort eine
Einleitung, muss er suchen. Die Begründung nach dem Ergebnis kostet ihn nichts:
Wer dem Ergebnis glaubt, hört auf zu lesen; wer zweifelt, liest weiter. Die
umgekehrte Reihenfolge zwingt jeden Leser durch den ganzen Text.

## Warum es zwei Stufen gibt

| Stufe | Bedeutung | Folge |
|---|---|---|
| A | ein Wort oder Muster, das in keinem Fachtext etwas beiträgt | jeder Fund wird beseitigt |
| B | ein Hinweis, der im Einzelfall richtig sein kann — Passiv, Satzlänge, Absolutwort | zählt gegen eine Schwelle |

Eine einzige Stufe hätte zwei Fehler: Mit harter Schwelle für alles wird ein
langer Fachtext rot, obwohl er in Ordnung ist. Ohne Schwelle wird jede Meldung
zur Meinung, und niemand beseitigt mehr etwas. Die Trennung hält den Prüfer
entscheidungsfähig: Stufe A ist ein Urteil, Stufe B ist eine Frage an den
Schreibenden.

## Warum Zonen ausgenommen sind

Ein Prüfer, der Zitate, Programmausgaben, Fehlermeldungen und Lizenztexte
mitglättet, fälscht Beweismittel. Deshalb erkennt `pruefe.py` Codeblock,
Kopfblock, Zitatzeile und Verweisziel selbst und lässt sie liegen. Die übrigen
Ausnahmen — Fremdtext, Vorschrift, Messwert — stehen als Tabelle im Skill und
werden vom Schreibenden angewandt; eine Maschine erkennt sie nicht zuverlässig.

Inline-Code wird vor der Prüfung durch Leerzeichen ersetzt, nicht entfernt. Nur
so bleiben die Spaltenpositionen erhalten, und ein in Rückwärtsschrägstriche
gesetztes Wort kann im Regeltext genannt werden, ohne sich selbst auszulösen.

## Warum jeder Aufzählungspunkt ein eigener Absatz ist

Aufzählungspunkte enden selten mit einem Punkt. Werden sie zu einem Absatz
verbunden, hält die Satzerkennung eine ganze Liste für einen einzigen Satz und
meldet Überlänge und eine Häufung von Gedankenstrichen, wo beides nicht
vorliegt. Die Trennung am Listenzeichen beseitigt diese Fehlmeldung.

## Warum das Werkzeug keine Standardeingabe liest

In der Werkzeugkette von Claude Code hat kein Kommando eine Standardeingabe.
Ein Aufruf, der darauf wartet, hängt bis zum Zeitablauf. `pruefe.py` nimmt
deshalb nur Dateinamen.

## Warum der Katalog im Programm steht

Die Wortlisten sind die Regel, nicht ihre Erläuterung. Stünden sie zusätzlich
als Textdatei daneben, gäbe es zwei Fassungen, und die eine würde still
veralten. `--liste` druckt den Katalog, damit die Anleitung ihn nicht
abschreiben muss.

## Grenzen

Die Prüfung ist eine Heuristik, kein Beweis. Sie misst Wortlaut und Form, nicht
Wahrheit, Vollständigkeit oder Angemessenheit. Ein Text ohne Fund kann falsch
sein; ein Text mit Funden kann richtig sein. Passiv, Absolutwort und Satzlänge
erkennt sie mit Fehlern in beide Richtungen.

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| ein häufiges Alltagswort in Stufe A aufnehmen (`immer`, `alle`, `wichtig`) | jeder Fachtext wird rot, das Werkzeug wird abgeschaltet |
| Zonenerkennung entfernen, weil sie „nur Markdown kennt" | Zitate und Programmausgaben werden mitgeprüft, Beweismittel geglättet |
| Maskierung von Inline-Code durch Löschen statt Leerzeichen ersetzen | Zeilenpositionen verschieben sich, Fundstellen zeigen auf die falsche Spalte |
| Standardeingabe nachrüsten | Aufrufe ohne Eingabe hängen bis zum Zeitablauf |
| Trennung am Listenzeichen aufheben | jede Aufzählung meldet Überlänge und Strichhäufung |
| Stufen zusammenlegen | entweder wird jeder lange Text rot oder kein Fund mehr beseitigt |
| Wortliste zusätzlich als Textdatei führen | zwei Fassungen, eine veraltet still |
| Schwelle als Vorgabe auf 0 setzen | Stufe B wird zur Pflicht, obwohl sie Einzelfallentscheidungen enthält |
