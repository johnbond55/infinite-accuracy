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

1. `version.json` und `.claude-plugin/plugin.json` auf dieselbe Version setzen,
   `aenderungen` füllen, `CHANGELOG.md` nachziehen.
2. `python installieren.py --manifest`
3. `python skills/kaskade/pruefstand.py` → `STATUS: GRUEN`; mit `--rot` → rot.
4. Commit, Tag `v<version>`, dann Tag und Zweig **gemeinsam** pushen:
   `git push --atomic origin main v<version>`

Kommt `main` vor dem Tag an, sehen Projekte die neue Version, das Archiv fehlt
aber noch — die Installation bricht mit „Laden gescheitert" ab.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| Manifest vergessen | Prüfstand rot, Installation bricht ab — gewollt |
| CRLF im Arbeitsbaum | Prüfsummen passen nicht zum Archiv (LF); `.gitattributes` hält LF |
| Zip-Pfade nicht prüfen | ein Archiv schreibt außerhalb des Zielordners |
| lokale Änderungen überschreiben | eigene Anpassungen verschwinden beim nächsten Update |
| Update-Prüfung ohne Zeitlimit | ein hängendes Netz blockiert den Sitzungsstart |
| Zweig vor dem Tag pushen | Hinweis erscheint, Installation scheitert |
