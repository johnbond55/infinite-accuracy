# Änderungen

## 2.1.0 — 17.09.2026

### Neu

- **Skill `sprachregel`.** Regeln für jeden Text, den ein Mensch liest —
  Antwort, Dokumentation, Notiz, Commit-Nachricht, Oberflächen-, Mail- und
  Fehlertext. Das Ergebnis steht im ersten Satz, der Beleg danach, am Ende
  keine Zusammenfassung. Gestrichen werden Füllwort, Weichmacher, Werbewort
  ohne Messung, Höflichkeits- und Schlussfloskel, Metagerede über die eigene
  Arbeit und die Ankündigung statt der Sache. Ab drei Größen Tabelle oder
  Aufzählung statt Fließtext, jede Angabe genau einmal.
  Unberührt bleiben Zitat, Programmausgabe, Fehlermeldung, Rechtstext und
  Messwert: dort wäre Glätten eine Fälschung.
- **`skills/sprachregel/pruefe.py`** prüft Text gegen den Katalog und urteilt
  in zwei Stufen. Stufe A ist ein Fund und wird beseitigt; Stufe B ist ein
  Hinweis — Passiv ohne Handelnden, Satzlänge, Absolutwort, Strichhäufung —
  und zählt gegen eine Schwelle (Vorgabe 10 je Datei). Codeblock, Kopfblock,
  Zitatzeile, Inline-Code und Verweisziel werden übersprungen, `--alles` hebt
  das auf. Ausgabe als Text oder `--json`, Exit 1 bei Rot; das Werkzeug liest
  Dateien und keine Standardeingabe.
- **`pruefe.py --liste`** druckt den vollständigen Regelkatalog mit allen
  Wörtern. Die Anleitung verweist darauf, statt ihn ein zweites Mal zu führen.
- **Proben für den Textprüfer** im Prüfstand: Katalog, ausgenommene Zonen,
  Maskierung, Satzmaß, Trennung am Listenzeichen, Schwelle, BOM, Exitcodes.
  Dazu die Probe, dass `SKILL.md` und `doku/sprachregel.md` selbst keinen Fund
  der Stufe A tragen.

## 2.0.4 — 17.09.2026

### Behoben

- **Gedächtnisindex über der Ladegrenze.** Claude Code lädt von `MEMORY.md`
  nur 200 Zeilen bzw. 25.000 Zeichen — unter Windows mit dem Wagenrücklauf
  gezählt — und schneidet den Rest still ab. Im Projekt hatte der Index 236
  Zeilen; ab Zeile 153 fehlten die hinteren „Laufenden Vorhaben" und alle
  Verweise. `gedaechtnis.py --register` baut den Kurzindex jetzt in ein
  Budget (190 Zeilen, 24.000 Zeichen): Regeln und Angaben zum Nutzer zuerst,
  dann das Jüngste. Was nicht mehr als ganze Zeile passt, steht als
  Schlagwort in seiner Rubrik, und der Kopf sagt, wie viele. Passt nicht
  einmal jedes Schlagwort, fehlen die ältesten ganz — auch das steht im Kopf.
- **Dateien mit BOM.** `konfig.json`, `ziele.json`, `regeln.md`,
  `register-texte.json`, `installation.json`, `installiert.json`,
  `settings.json` beim Installieren, die Prüfpunktdatei von `abnahme.py`, die
  `version.json` eines Updates, Gedächtniseinträge, Destillate,
  Rohprotokolle und die Seiten des Zettelkastens werden als `utf-8-sig`
  gelesen. Bisher galten bei einer mit dem Windows-Editor oder PowerShell
  gespeicherten Datei still die Vorgaben, und `abnahme.py` meldete „nicht
  lesbar". Eine Gedächtnisdatei mit BOM stand unter „Sonstiges" und ohne
  Beschreibung. Ein Dossier mit BOM trug im Suchlauf ein unsichtbares Zeichen
  und die Raute im Namen, eine Projektübersicht bekam einen zweiten Kopf, und
  das BOM eines Destillats ging in die Anweisung an die Verdichtung.
- **Prüfstand schrieb in den echten Stand.** Die Kennmarken-Probe legte
  `last-sid-5.json` im State-Ordner des Projekts an, im Repository unter
  `~/.claude/infinite-accuracy/state`. Sie läuft jetzt in einer umgelenkten
  Konfiguration; zwei Proben weisen nach, dass der echte Stand unberührt
  bleibt. Die liegen gebliebene Datei kann gelöscht werden.
- **Proben ohne Wirkung.** `main()` verglich nur `bool(ist) == bool(erwartet)`;
  eine Probe mit der Erwartung `"ok"` bestand bei jeder nichtleeren Antwort.
  Eine Erwartung, die kein Wahrheitswert ist, gilt jetzt als nicht erfüllt;
  die betroffenen Proben vergleichen exakt.

### Neu

- Die Gedächtnisprüfung meldet „Kurzindex zu lang" (auch beim
  Sitzungsstart; Ausweg `--register`) und „Kurzindex zu klein".
  `--register` nennt Zeilen, Zeichen, Budget und die Zahl der Einträge, die
  nur als Schlagwort stehen.
- Einstellung `index_max_zeilen` (190). `index_max_zeichen` steht jetzt auf
  24.000; beide werden auf die Ladegrenze gedeckelt.
- `register-texte.json` kennt drei weitere Texte: `gekuerzt`, `weggelassen`
  und `schlagworte`.

### Geändert

- Prüfstand: im Quell-Repository 220 Proben vor dem Tag und 223
  danach, in einer Projektinstallation 202 (bisher 185, 188 und 168).
- `doku/gedaechtnis.md`, `doku/konfig.md`, `doku/abnahme.md` und
  `doku/pruefstand.md` beschreiben Ladegrenze, BOM, Umlenkung und die
  strengen Erwartungen.

## 2.0.3 — 17.09.2026

### Neu

- **Schranke gegen Änderungen ohne neue Fassung.** Im Quell-Repository
  vergleicht der Prüfstand den Paketordner Byte für Byte mit dem Archiv des
  Tags `v<version>` (`git archive`, lokal, nur lesend). Wird eine Paketdatei
  nach dem Tag geändert und die Version stehen gelassen, ist er rot. Bisher
  erreichte so eine Änderung kein Projekt, und die Update-Prüfung schwieg —
  so blieb in 2.0.1 der Lizenzwechsel aus.
- Vor dem Tag gilt eine angehobene Version als vorbereitet, die Archiv-Proben
  sind dann übersprungen. **Nach `git tag` läuft der Prüfstand ein zweites
  Mal**, vor dem Push (`doku/aktualisierung.md`). Dabei prüft er auch, dass
  das Archiv des Tags seine eigenen Prüfsummen erfüllt.
- In einer Projektinstallation, in einer Paketkopie ohne Repository und in
  einem fremden Repository ist die Gruppe übersprungen. Liegt das Paket in
  einem Repository und `git` fehlt, ist sie rot.
- **Neu im Paket: `EUPL-1.2-DE.txt`**, die amtliche deutsche Fassung,
  bytegleich mit der Wurzel. Sie wird nach `.claude/infinite-accuracy/paket/`
  installiert; eine Projektinstallation wächst um eine Datei (mit der Ausnahme
  `skills/einrichten` von 40 auf 41, ohne sie von 41 auf 42). Proben prüfen
  den Gleichstand von Wurzel und Paket, die amtliche Prüfsumme und die Ausnahme
  von der Zeilenend-Normalisierung.
- `SKILL.md` und `doku/README.md` nennen die Lizenz und den Ort der
  Lizenztexte im Projekt.

### Behoben

- **Traceback statt Urteil.** Scheiterte im Prüfstand schon die
  Erstinstallation der Installer-Probe — etwa bei veraltetem Manifest —,
  schrieben die Folgeproben in ein nicht installiertes Projekt, und der Lauf
  endete mit `FileNotFoundError`. Jetzt endet die Gruppe mit der roten Probe
  „Installer-Folgeproben (abgebrochen: Erstinstallation gescheitert)".

### Geändert

- Prüfstand: im Quell-Repository 185 Proben vor dem Tag und 188 danach, in
  einer Projektinstallation 168 (bisher 162 und 153). Die Zahl hängt vom
  Zustand des Repositorys ab.
- `doku/pruefstand.md` und `doku/aktualisierung.md` beschreiben die
  Tag-Proben und den neuen Ablauf beim Veröffentlichen.

## 2.0.2 — 16.09.2026

### Geaendert

- Lizenz von **MIT** auf **EUPL-1.2** (European Union Public Licence)
  gewechselt. Grund: die MIT-Lizenz laesst zu, dass Ableitungen geschlossen
  werden; das Werkzeug soll offen bleiben. Die EUPL haelt zugleich den
  Urhebervermerk fest, liegt als verbindlicher deutscher Rechtstext vor und
  ist zu GPL, AGPL, LGPL, MPL, EPL, OSL, CeCILL und LiLiQ kompatibel.
- **Neu im Paket: `LICENSE`.** Der Lizenztext reist jetzt mit und wird nach
  `.claude/infinite-accuracy/paket/LICENSE` installiert; eine
  Projektinstallation waechst damit von 39 auf 40 Dateien.
- **Diese Fassung liefert den Wechsel aus.** In 2.0.1 fehlte er: der Wechsel
  kam erst nach dem Tag `v2.0.1` in den Zweig, und die Update-Routine liest
  die Version vom Zweig, laedt das Archiv aber vom Tag. Ohne neue Fassung
  erreicht ein Lizenzwechsel deshalb kein Projekt.
- `.claude-plugin/plugin.json` traegt das Feld `license`.
- Die amtliche deutsche Fassung liegt als `EUPL-1.2-DE.txt` im Repository.
  `.gitattributes` nimmt sie von der LF-Normalisierung aus (`-text`), damit
  der Rechtstext byteweise der Kommissionsfassung entspricht.
- Keine Codeaenderung gegenueber 2.0.1. Hooks, Skills, Agenten, Vorlagen und
  Doku sind unveraendert; nachgezogen wurden `version.json`, `plugin.json`
  und `PRUEFSUMMEN.json`.
- Fassungen bis einschliesslich 2.0.1 bleiben unter MIT verfuegbar.

## 2.0.1 — 16.09.2026

### Behoben

- **Die Kennmarke blieb ungeprüft.** `wiedervorlage.py` prüft sie beim
  Sitzungsstart — dort steht die Zusammenfassung aber oft noch nicht im
  Transkript (Claude Code schreibt sie erst danach), und die Nachprüfung in
  `regelschub.py` hing an `verdichtet`, das nach der ersten Antwort nicht
  mehr anschlägt. Ergebnis: „nicht prüfbar" beim Start, danach nie wieder
  eine Prüfung. Die Nachprüfung läuft jetzt bei jedem Prompt, bis sie ein
  Urteil hat.
- **Fehlalarm bei aufgeschobener Verdichtung.** Hielt der Riegel die
  Verdichtung zurück, verglich die Prüfung die neue Kennmarke mit der
  Zusammenfassung der VORIGEN Verdichtung und hätte „fehlt" gemeldet. Jetzt
  entscheidet der Zeitvergleich: eine ältere Zusammenfassung heißt
  „unprüfbar".

### Geändert

- `ernte.zusammenfassung_mit_zeit()` liefert Text und Zeitstempel der
  jüngsten Zusammenfassung. `letzte_zusammenfassung()` bleibt als Name
  bestehen, `kennmarke_pruefen()` nimmt beide Zeiten optional entgegen —
  alte Aufrufe verhalten sich wie bisher.
- Prüfstand: 162 Proben (vier neue). Die Prozessprobe „Kennmarke wird auch
  nach der ersten Antwort noch geprüft" fällt mit der alten Bedingung durch.

## 2.0.0 — 15.09.2026

### Neu

- **Gesteuerte Verdichtung.** `ernte.py` gibt der Zusammenfassung bei PreCompact
  eine Anweisung mit Kennmarke und schiebt die automatische Verdichtung auf,
  solange in der Sitzung nicht abgelegt wurde (bis `riegel_bis_token`).
  `wiedervorlage.py` prüft die Kennmarke danach.
- **Zettelkasten** `skills/zettel/`: ablegen, sinngemäß suchen (Dossier,
  Schlagwort, Volltext), Trefferseiten im Ganzen lesen, Besuchs-Log beim Ablegen,
  Karte, Projekte-Regal, Reflexionen, Hausmeister. Nach dem Vorbild der
  Schreibstube, ohne Modellaufruf.
- **Update-Routine** `hooks/aktualisierung.py` und `installieren.py`: Hinweis
  beim Sitzungsstart, Installation aus dem Archiv des Tags mit Prüfsummen,
  Sicherung, Abnahme und Rückbau.
- `hooks/haertung.py`: Härtung älterer Transkripte und Nachernte laufen
  abgekoppelt vom Sitzungsstart.
- Agent `ia-leser` (haiku) für Lesearbeit.

### Geändert

- `regelschub.py` misst echte Token aus der usage-Zeile statt Zeichen und
  fordert ab `ablage_schwelle_token` (180.000) die Ablage an, statt `/compact`
  vorzuschlagen. `schwelle_zeichen` entfällt.
- `wiedervorlage.py` hat einen eigenen Zweig nach der Verdichtung (Regeln,
  Destillat dieser Sitzung, Karte) und zeigt Karte und Update-Hinweis beim Start.
- `konfig.py` kennt Schalter (`zeichen()`) und Ablageorte (`pfad()`).
- `marketplace.json` liegt in `.claude-plugin/`, wie die Doku von Claude Code es
  verlangt.
- Zeilenenden sind LF (`.gitattributes`).

### Behoben

- Die Tilgung trennte Transkriptzeilen mit `splitlines()` auch an U+2028 und
  zerbrach dabei das JSON betroffener Zeilen.

## 1.0.0 — 09.09.2026

- Erste Fassung: Kaskade mit Abnahme, Journal für temporäre Dateien, Ernte,
  Tilgung, Regelschub, Wiedervorlage, Gedächtnisindex.
