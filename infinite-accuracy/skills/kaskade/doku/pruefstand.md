# pruefstand.py — warum es so gebaut ist

Der Prüfstand fährt die Schranken dieses Skills gegen Proben, deren Ausgang
vorher feststeht. Er zählt, er interpretiert nicht — dieselbe Haltung wie
`abnahme.py`, nur nach innen gerichtet.

---

## Zwei Richtungen, beide nötig

| | Bedeutung | Was ein Fehlschlag heißt |
|---|---|---|
| **muss durch** | ein harmloser Fall, der arbeiten können muss | die Schranke ist zu eng und macht das Werkzeug unbrauchbar |
| **muss blocken** | ein gefährlicher Fall | die Schranke ist ein Versprechen ohne Deckung — schlimmer als keine |

Ein Prüfstand, der nur die gefährliche Richtung testet, verleitet dazu, die
Schranke immer enger zu ziehen, bis niemand mehr damit arbeiten kann. Genau das
ist schon passiert: Die Umleitungsprüfung wies `awk '$1 > 100 {print
"ja"}'` ab — die Fehlerrichtung war richtig, das Ergebnis unbrauchbar.

Deshalb stehen dreizehn harmlose Prüfbefehle in der Liste, darunter
`docker compose ps`, `confirm_firmware_version` und `echo 2>&1`. Sie sind keine
Beiwerk, sondern die Hälfte der Prüfung.

---

## `--rot` — die Gegenprobe

Kehrt jede Erwartung um. Der Lauf **muss** fehlschlagen.

**Ein Prüfstand, der immer grün meldet, prüft nichts.** Das kann jederzeit
passieren: ein Importfehler, der abgefangen wird; eine Probenliste, die leer
bleibt; eine Vergleichslogik, die versehentlich immer `True` liefert. `--rot`
weist nach, dass die Proben überhaupt entscheiden.

Erwartete Ausgabe:

```
$ python pruefstand.py           ->  <n> bestanden, 0 durchgefallen   STATUS: GRUEN, Exit 0
$ python pruefstand.py --rot     ->  0 bestanden, <n> durchgefallen   STATUS: ESKALATION, Exit 1
```

---

## Nebenwirkungen nur in eigenen Temp-Ordnern

Die Schranken-Proben rufen reine Funktionen auf. Verdichtung, Zettelkasten und
Installer werden Ende-zu-Ende geprobt — aber ausschließlich in Ordnern aus
`tempfile.mkdtemp()`, die am Ende gelöscht werden. Der Hook-Prozess für
PreCompact bekommt über `IA_KONFIG` eine Probenkonfiguration, deren Ablageorte
im Temp-Ordner liegen. Es wird nichts ins echte Journal eingetragen, keine
Verbindung aufgebaut, kein echter Stand gelesen oder angelegt. Die einzige
Ausnahme liest nur: Im Quell-Repository fragen die Tag-Proben `git` ab
(`rev-parse`, `ls-files`, `check-attr`, `for-each-ref`, `rev-list`, `archive`
nach stdout) — ohne Netz, und das Archiv wird nur in einen eigenen Temp-Ordner
`ia-tagarchiv-…` entpackt. In einer Projektinstallation ruft der Prüfstand
kein `git` auf.

**Das muss so bleiben.** Ein Prüfstand, der ins echte Journal schreibt,
verändert den Zustand, den er prüfen soll; einer, der `ssh` oder das Netz
braucht, läuft offline nicht mehr. Anlass: Eine erste Fassung von
`ernte.stand_pfad()` legte beim bloßen Lesen den State-Ordner an — ein
Probenlauf im Repository erzeugte dadurch `~/.claude/infinite-accuracy/state`.

## Die Installer-Proben brauchen das ganze Paket

Sie installieren eine Kopie des Pakets in ein Temp-Projekt und prüfen dabei
auch die Prüfsummen. In einer Projektinstallation liegt nur ein Teil des Pakets;
dort melden sie sich als übersprungen. Im Repository schlagen sie fehl, solange
`installieren.py --manifest` nach einer Änderung nicht gelaufen ist — gewollt.

Scheitert dabei schon die Erstinstallation, endet die Gruppe mit der roten
Probe „Installer-Folgeproben (abgebrochen: Erstinstallation gescheitert)". Die
Folgeproben schreiben in das installierte Projekt; ohne den Abbruch warf die
erste von ihnen `FileNotFoundError`, und der Lauf endete mit einem Traceback
statt mit einem Urteil (gefunden 16.09.2026 beim Bau der Tag-Proben).

---

## Die Tag-Proben — der Zweig darf dem Tag nicht davonlaufen

`aktualisierung.py` liest die Version vom Zweig, lädt das Paket aber aus dem
Archiv des Tags `v<version>`. Wird eine Paketdatei nach dem Tag geändert und die
Version stehen gelassen, erreicht die Änderung kein Projekt, und die
Update-Prüfung schweigt. Anlass 16.09.2026: Der Lizenzwechsel kam nach `v2.0.1`
in den Zweig und blieb aus, bis 2.0.2 ihn auslieferte.

Im Quell-Repository urteilt die Gruppe über den Zustand der Version:

| Zustand | Bedingung | Folge |
|---|---|---|
| getaggt | der Tag `v<version.json>` existiert | Paketordner und Archiv des Tags werden Byte für Byte verglichen; das Archiv muss dieselbe Version tragen und seine eigenen Prüfsummen erfüllen |
| vorbereitet | kein Tag, Version neuer als der jüngste Release-Tag — oder ein Repository mit genau einem Commit und ohne Tags | Archiv-Proben übersprungen; nach `git tag` läuft der Prüfstand ein zweites Mal |
| rot | Version ohne Tag und nicht neuer; Tag nur in anderer Schreibweise (`v2.0.02`); ungültige Version; keine Release-Tags in einem Repository mit mehr als einem Commit | `STATUS: ESKALATION` |

Verglichen wird mit `git archive`, nicht mit `git diff`: `diff` normalisiert die
Zeilenenden und hält eine Datei mit CRLF für unverändert. Das Archiv liefert die
Bytes, die GitHub ausliefert und `installieren.py` prüft, und beachtet
`export-ignore` wie GitHub. Die Dateiauswahl kommt vom Installer
(`paket_dateien` plus `PRUEFSUMMEN.json`) und wird nicht nachgebaut. Eine
unlesbare Datei gilt als Abweichung.

Zur Gruppe gehören die Lizenzproben: `LICENSE` und `EUPL-1.2-DE.txt` liegen in
Wurzel und Paket bytegleich, die deutsche Fassung trägt die amtliche Prüfsumme
(BOM und CRLF gehören zum Wortlaut, `--manifest` nähme jeden Stand hin), und
`.gitattributes` nimmt sie von der Zeilenend-Normalisierung aus. Ohne `-text`
speichert `git add` LF, und das Archiv des Tags verfehlt die Prüfsumme.

Zwei Gegenproben weisen nach, dass der Vergleich entscheidet: Der Paketordner
weicht vom Archiv des Vorgänger-Tags ab (sofern es einen gibt), und das Archiv
eines fehlenden Pfads meldet einen Fehler.

| Lage | Ergebnis |
|---|---|
| Projektinstallation (kein vollständiges Paket) | übersprungen |
| Paketkopie ohne Repository | übersprungen |
| Paket in einem Repository, das es nicht verfolgt | übersprungen |
| über dem Paket liegt `.git`, `git` ist aber nicht aufrufbar | rot — im Repository wird nie still übersprungen |

Die Zahl der Proben hängt deshalb vom Zustand ab.

Grenzen:

- Es zählen nur **lokale** Tags. Ein nicht gepushter oder auf GitHub
  verschobener Tag bleibt unbemerkt. Ein Klon ohne Tags ist rot
  (`git fetch --tags`); fehlt nur der jüngste Tag, gilt die schon getaggte
  Version als vorbereitet.
- Ein lokal verschobener Tag (`git tag -f`) gilt als der Tag.
- Tags mit Zusatz (`v2.0.3-rc1`) zählen nicht als Release.
- Kein pre-commit-Hook: Die Schranke greift nur, wenn der Prüfstand läuft.
- Das erste Release eines Repositorys mit mehr als einem Commit ist bis zum Tag
  rot — erst taggen, dann prüfen, dann pushen.

---

## Warum die Proben wörtlich dastehen

Jede Probe nennt ihren Fall im Klartext (`"Serverpfad mit Semikolon wird
abgewiesen"`) statt ihn zu berechnen. Bei einem Fehlschlag steht damit in der
Ausgabe, **was** nicht mehr stimmt — ohne dass jemand den Prüfstand lesen muss.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| nur noch „muss blocken"-Proben | die Schranke wird immer enger, bis legitime Prüfbefehle abgewiesen werden |
| `--rot` entfernen | ein kaputter Prüfstand meldet grün und niemand merkt es |
| Nebenwirkungen einbauen | der Prüfstand verändert, was er prüft |
| Probennamen berechnen statt ausschreiben | die Fehlermeldung sagt nicht mehr, was gebrochen ist |
| Tag-Vergleich über `git diff` statt Archivbytes | eine Datei mit CRLF gilt als unverändert, das Update scheitert an den Prüfsummen |
| fehlendes `git` im Repository still überspringen | die Schranke fällt unbemerkt aus |
| leere Tagliste als „vorbereitet" werten | ein Klon ohne Tags lässt jede Änderung durch |
| Abbruch der Installer-Folgeproben entfernen | die Folgeproben schreiben in ein nicht installiertes Projekt, der Lauf endet mit `FileNotFoundError` statt mit einem Urteil |
