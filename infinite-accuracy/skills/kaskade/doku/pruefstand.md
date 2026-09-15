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
Verbindung aufgebaut, kein echter Stand gelesen oder angelegt.

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
