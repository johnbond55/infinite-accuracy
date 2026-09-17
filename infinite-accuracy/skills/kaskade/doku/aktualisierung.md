# Aktualisierung und Installation — warum sie so gebaut sind

`aktualisierung.py` fragt nach neuen Fassungen, `installieren.py` setzt sie ein.
Gedacht für Projektinstallationen, die mit dem Projektordner reisen — etwa über
einen Sync-Ordner auf ein zweites Gerät.

---

## Warum nicht nur das Plugin-System

| Plugin-System von Claude Code | Projektinstallation |
|---|---|
| installiert je Rechner nach `~/.claude/plugins/cache` | liegt im Projekt und reist mit |
| erkennt Updates am Commit | erkennt Updates an `version.json` |
| meldet nur bei eingeschaltetem Auto-Update | meldet beim Sitzungsstart und fragt |

Beides bleibt möglich: das Repository ist weiter ein Plugin-Marketplace.

---

## Der Weg eines Updates

1. `wiedervorlage.py` ruft `aktualisierung.hinweis()`: höchstens alle
   `aktualisierung_intervall_stunden` eine Anfrage an
   `raw.githubusercontent.com/<repo>/<zweig>/infinite-accuracy/version.json`,
   Zeitlimit `aktualisierung_zeitlimit_sekunden`. Ohne Netz: still.
2. Ist die Version neuer als `installiert.json`, steht ein Hinweis im Kontext. Das
   Modell fragt den Nutzer — mit Version, Quelle und Größe.
3. Nach dem Ja: `aktualisierung.py --installieren <version>` lädt das Archiv des
   Tags `v<version>` von `codeload.github.com`, entpackt es (keine Pfade mit `..`
   oder Laufwerk) und prüft, dass es die verlangte Version trägt.
4. Die **neue** `installieren.py` aus dem Archiv übernimmt — so gilt immer die
   Zuordnung der neuen Fassung.

## Was `installieren.py` prüft, bevor es schreibt

| Prüfung | bei Fehlschlag |
|---|---|
| Prüfsummen (`PRUEFSUMMEN.json`) aller Paketdateien | Abbruch, nichts geschrieben |
| Update ohne `installiert.json`, Erstinstallation mit | Abbruch |
| neue Version älter als die installierte | Abbruch |
| eine installierte Datei weicht von ihrer aufgezeichneten Prüfsumme ab | Abbruch — lokale Änderungen werden nie still überschrieben |
| eine Zieldatei existiert, stammt aber nicht aus dem Paket (Update) | Abbruch |
| Sperre einer laufenden Installation jünger als 30 min | Abbruch |

Dann: Sicherung nach `.claude/infinite-accuracy/sicherung/vor-<version>-<zeit>/`,
Schreiben über `.ia-neu` + `os.replace`, `installiert.json` neu, Prüfstand im
Projekt und echter Import jedes Hooks. Ist die Abnahme rot, wird die vorige
Fassung zurückgespielt.

Bei der **Erstinstallation** werden vorhandene Zieldateien gesichert und
ersetzt. `settings.json` wird nur mit `--einstellungen` angefasst, und dann nur
ergänzt.

---

## Eine Fassung veröffentlichen

1. **Zuerst** `version.json` und `.claude-plugin/plugin.json` auf dieselbe neue
   Version setzen, **dann** das Paket ändern. Nach dem Tag der alten Fassung
   ist jede Paketänderung rot, bis die Version angehoben ist — gewollt.
2. `aenderungen` füllen, `CHANGELOG.md` nachziehen. `LICENSE` und
   `EUPL-1.2-DE.txt` in Wurzel und Paket gleich halten.
3. `python installieren.py --manifest`
4. `python skills/kaskade/pruefstand.py` → `STATUS: GRUEN`; mit `--rot` → rot.
   Die Version gilt als vorbereitet, die Archiv-Proben sind übersprungen.
5. Commit, dann Tag `v<version>` setzen (`git tag -a`).
6. Prüfstand **erneut** → `STATUS: GRUEN`. Jetzt vergleicht er den Paketordner
   Byte für Byte mit dem Archiv des Tags.
7. Tag und Zweig **gemeinsam** pushen: `git push --atomic origin main v<version>`

Kommt `main` vor dem Tag an, sehen Projekte die neue Version, das Archiv fehlt
aber noch — die Installation bricht mit „Laden gescheitert" ab.

Ist Schritt 6 rot, weicht der Paketordner vom Tag ab. Solange der Tag nicht
gepusht ist, darf er gelöscht und neu gesetzt werden (`git tag -d v<version>`).
Einen gepushten Tag nie verschieben (`git tag -f`, `git push --force`):
Projekte, die die Fassung schon geladen haben, hätten einen anderen Stand als
die nächsten. Die Prüfung läuft nur lokal — ein nicht gepushter oder auf GitHub
verschobener Tag bleibt ihr verborgen.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| Manifest vergessen | Prüfstand rot, Installation bricht ab — gewollt |
| CRLF im Arbeitsbaum | Prüfsummen passen nicht zum Archiv (LF); `.gitattributes` hält LF — außer bei `EUPL-1.2-DE.txt` (`-text`: der amtliche Wortlaut trägt CRLF und BOM) |
| Zip-Pfade nicht prüfen | ein Archiv schreibt außerhalb des Zielordners |
| lokale Änderungen überschreiben | eigene Anpassungen verschwinden beim nächsten Update |
| Update-Prüfung ohne Zeitlimit | ein hängendes Netz blockiert den Sitzungsstart |
| Zweig vor dem Tag pushen | Hinweis erscheint, Installation scheitert |
| Paketdatei nach dem Tag geändert, Version stehen gelassen | die Änderung erreicht kein Projekt, die Update-Prüfung schweigt — der Prüfstand ist rot |
