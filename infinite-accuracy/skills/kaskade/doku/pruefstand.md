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
$ python pruefstand.py           ->  62 bestanden, 0 durchgefallen   Exit 0
$ python pruefstand.py --rot     ->  0 bestanden, 62 durchgefallen   Exit 1
```

---

## Keine Nebenwirkungen

`proben()` ruft ausschließlich `pfad_erlaubt()` und `ist_veraendernd()` auf —
beides reine Funktionen. Es wird nichts eingetragen, nichts gelöscht, keine
Verbindung aufgebaut.

**Das muss so bleiben.** Ein Prüfstand, der ins echte Journal schreibt,
verändert den Zustand, den er prüfen soll; einer, der `ssh` aufruft, läuft ohne
Netz nicht mehr. Wer eine Probe braucht, die Dateien anfasst, schreibt sie
gegen einen eigenen Temp-Ort und räumt selbst auf.

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
