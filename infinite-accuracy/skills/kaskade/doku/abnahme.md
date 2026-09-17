# abnahme.py — warum es so gebaut ist

Der Code sagt, **was** geprüft wird. Hier steht, **warum** die Prüfung so
aussieht — und welche Vereinfachung sie kaputtmacht.

---

## Wozu das Ganze

**Eine Behauptung lässt sich nicht widerlegen, ein Prüfbefehl schon.**

Ein Subagent kann behaupten, eine Datei gelesen oder geschrieben zu haben, ohne
es getan zu haben. Das ist kein Verdacht, sondern ein dokumentiertes
Fehlermuster (`anthropics/claude-code#40339`, „vorgetäuschte Gründlichkeit"):
Das Modell schließt aus Dateinamen statt aus Inhalt und berichtet das als
Ergebnis.

Dagegen hilft kein besserer Prompt, sondern ein Zähler, der ausführt und
vergleicht.

**Der Zähler zählt, er interpretiert nicht** — genau das ist der Unterschied
zwischen einer Prüfung und einem „passt schon".

---

## Der Wortlaut der Schlusszeile ist gebunden

```
Pruefprotokoll maschinell: %d bestanden, %d durchgefallen, %d gesamt
STATUS: GRUEN | ESKALATION
```

Nicht verschlimmbessern. Zwei Gründe:

1. Der Wortlaut ist eine Schnittstelle: Wer mehrere Werkzeuge oder Maschinen
   betreibt, hält sie damit auf derselben Sprache.
2. `ia-pruefer.md` verlangt vom prüfenden Modell, diese Ausgabe **wörtlich**
   weiterzureichen, und der Auftraggeber liest den `STATUS:`-Marker. Wer den
   Text ändert, bricht die Kette, ohne dass jemand einen Fehler sieht.

---

## Die Read-only-Sperre ist eine Heuristik

**Das ist wichtig und muss so gesagt werden.** Sie kennt benannte Verben und
Umleitungen, aber keine Aliase, keine Skripte, die ihrerseits etwas ändern, und
kein selbstgebautes Programm. **Sie fängt den Unfall, nicht den Vorsatz.**

Wer ihr mehr zutraut, als sie leistet, hat eine Sperre, die nur behauptet — und
das ist schlechter als gar keine. Eine frühere Fassung behauptete „Pruefbefehle sind READ-ONLY" — das war die
falsche Zusage.

### Zwei Prüflagen, unterschiedlich streng

| | Wo gesucht wird | Warum |
|---|---|---|
| **Verben** | auf dem **ganzen** Befehl, auch innerhalb von Anführungszeichen | sonst schlüpfte `sh -c "rm -rf /"` durch |
| **Umleitungen** | nur **außerhalb** von Anführungszeichen | sonst gilt `awk '$1 > 100 {print "ja"}'` als Umleitung |

Der zweite Fall ist gemessen: Eine frühere Fassung wies genau diesen völlig
harmlosen Prüfbefehl ab. Die
Fehlerrichtung war richtig (im Zweifel gilt ein Punkt als **nicht** erfüllt),
aber sie machte legitime Vergleiche unbrauchbar.

### Der Vorspann ist ein negativer Lookbehind, keine Zeichenklasse

```
(?<![A-Za-z0-9_-])
```

Mit einer Zeichenklasse (etwa „Leerzeichen oder Zeilenanfang") rutschte
`sh -c "rm -rf /"` durch, weil vor dem `rm` ein Anführungszeichen steht und kein
Leerzeichen. Ausgeschlossen sind nur Wortzeichen, damit `firmware` und `confirm`
nicht anschlagen — ein `/usr/bin/rm` dagegen schon.

*Im Sperrentest gemessen.*

---

## Die Verbliste

Gruppiert nach Wirkung:

| Gruppe | Verben |
|---|---|
| Dateien anlegen, verschieben, löschen, umbiegen | `rm mv cp dd truncate shred unlink rmdir mkdir touch ln chmod chown chgrp mkfs sed -i tee` |
| holt etwas von außen und legt es ab | `curl wget scp rsync` |
| ändert einen Arbeitsbaum | `git reset\|checkout\|clean\|revert\|rebase\|merge\|pull\|push\|commit\|apply` |
| greift in laufende Prozesse und Dienste ein | `kill pkill killall systemctl start\|stop\|restart\|enable\|disable\|mask` |
| Container | `docker rm\|rmi\|stop\|restart\|kill\|run\|exec\|build\|pull\|push`, `docker compose up\|down\|start\|stop\|restart\|rm\|kill\|build\|pull\|create` |
| Pakete und Bauvorgänge | `apt install\|remove\|purge`, `pip install`, `npm install\|ci`, `make` |
| führt für jede Zeile einen weiteren Befehl aus | `xargs` |

**`docker compose` darf nicht blank in der Liste stehen.** Es traf sonst auch
`docker compose ps` — einen völlig harmlosen Prüfbefehl, der zur Abnahme
gebraucht wird. Nur die verändernden Unterbefehle gehören hinein.

**`find` ist erlaubt und oft nötig**, aber nicht mit löschenden oder
ausführenden Aktionen (`-delete`, `-exec`, `-execdir`, `-ok`, `-okdir`). Die
stehen als Option **hinter** dem Pfad, weshalb die Verbliste sie nicht greift —
deshalb die eigene Regel `FIND_AKTION`.

*Liste nachträglich erweitert; vorher fehlten fünfzehn Verben, und
`docker compose ps` schlug falsch an.*

---

## `_ohne_quotes()`

Ersetzt alles innerhalb von `'…'` und `"…"` durch Leerzeichen, damit die
Umleitungsprüfung nur die Shell-Ebene sieht.

Ein **unpaariges** Anführungszeichen lässt den Rest als Quote gelten. Das ist
die sichere Richtung: Ein solcher Befehl ist ohnehin fehlerhaft.

---

## Die Vergleichsarten

| Art | Regel |
|---|---|
| `exakt` | Ausgabe == Erwartung, beide getrimmt |
| `enthaelt` | Erwartung kommt in der Ausgabe vor |
| `zahl` | numerischer Vergleich, damit `9` und `9.0` gleich sind |
| `leer` | **kein stdout, kein stderr, Exit 0** |
| `nichtleer` | irgendeine Ausgabe |

**`leer` ist für Import-Tests gebaut.** `py_compile` ist keine Abnahme — es
prüft nur die Syntax. Ein fehlender Import fällt erst auf, wenn die Modulebene
läuft (`class X(threading.Thread)` löst den Namen erst zur Laufzeit auf). Bei
`Restart=always` gibt das eine Crash-Schleife, die einen Server unerreichbar
machen kann. Deshalb prüft `leer` streng: auch stderr muss stumm sein.

`vergleichen()` kennt kein Ermessen. Wenn hier jemals eine Toleranz eingebaut
wird, ist der Zähler wertlos — Nachträge gehören in den `ia-pruefer`, wo sie als
`NACHTRAG` gekennzeichnet werden.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| Schlusszeile umformulieren | `ia-pruefer` reicht sie wörtlich weiter, der Auftraggeber liest `STATUS:` — die Kette bricht lautlos |
| Lookbehind zu Zeichenklasse | `sh -c "rm -rf /"` rutscht durch |
| Umleitungsprüfung auf den ganzen Befehl | jedes `awk '{print "x"}'` wird abgewiesen |
| `docker\s+compose` ohne Unterbefehle | `docker compose ps` unbrauchbar |
| Toleranz in `vergleichen()` | der Zähler interpretiert wieder, statt zu zählen |
| „Heuristik" im Docstring zu „READ-ONLY" | eine Zusage ohne Deckung |
| Prüfpunktdatei nur als `utf-8` lesen | eine mit PowerShell gespeicherte Datei (BOM) gilt als „nicht lesbar" |
