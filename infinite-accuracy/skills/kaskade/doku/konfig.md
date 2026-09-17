# konfig.py — warum es so gebaut ist

Der eine Zugang zur Konfiguration. Alles liegt in
`<projekt>/.claude/infinite-accuracy/` (anders: Umgebungsvariable `IA_KONFIG`).

| Datei | Inhalt |
|---|---|
| `ziele.json` | Fernziele für `journal.py` und `abnahme.py` |
| `konfig.json` | Zahlen (`VORGABEN`), Schalter (`ZEICHEN_VORGABEN`), Ablageorte (`pfade`) |
| `regeln.md` | wird bei jedem Prompt eingespeist |
| `destillat.md` | eigener Wortlaut des Ablage-Auftrags; Platzhalter `{tok} {schwelle} {datum} {ablage} {eingang} {zettel}` |
| `register-texte.json` | Überschriften und Kürzungshinweise des Gedächtnisindex; Platzhalter `{kurz} {gesamt} {fehlt}` |
| `installation.json` | Ausnahmen bei der Installation |
| `installiert.json` | vom Installer geschrieben — nicht von Hand ändern |

---

## Unbekannte Namen werfen

`zahl()`, `zeichen()` und `pfad()` werfen bei einem Namen, den es nicht gibt. Ein
Tippfehler im Code darf nicht still eine Vorgabe, eine 0 oder einen falschen Ort
ergeben.

## Ablageorte

`pfade.sitzungen`, `pfade.state`, `pfade.zettelkasten`. Relative Angaben gelten ab
der Projektwurzel, nie ab dem Arbeitsverzeichnis — ein Hook läuft nicht immer
dort, wo man denkt.

## Dateien mit BOM

Was von Hand bearbeitet sein kann, liest das Paket als `utf-8-sig`: Ein
Byte-Order-Mark am Anfang wird überlesen. Der Windows-Editor und PowerShell 5.1
(`Set-Content` oder `Out-File` mit `-Encoding UTF8`) schreiben eines. Mit
`utf-8` warf `json` „Unexpected UTF-8 BOM", und still galten die Vorgaben:
alle Fernziele weg, alle Zahlen zurückgesetzt. `regeln.md` begann mit einem
unsichtbaren Zeichen.

Als `utf-8-sig` gelesen werden:

- alles aus diesem Ordner: `ziele.json`, `konfig.json` und was
  `konfig.text()` und `konfig.tabelle()` lesen (`regeln.md`, `destillat.md`,
  `register-texte.json`)
- `installiert.json`, `installation.json` und `settings.json` beim
  Installieren; `installiert.json` auch für den Update-Hinweis beim
  Sitzungsstart, dazu die `version.json` eines Updates
- die Prüfpunktdatei von `abnahme.py`
- die Gedächtniseinträge beim Bau von Index und Register
  (`gedaechtnis.lesen()`)
- Destillate und Rohprotokolle beim Sitzungsstart, das Destillat in der
  Anweisung an die Verdichtung
- alles, was `zettel.py` liest: die Seiten des Zettelkastens und dessen
  Zähler `kreis_state.json`

Die übrigen Standdateien, `journal.jsonl`, Transkripte und stdin schreiben das
Paket oder Claude Code selbst; sie bleiben `utf-8`. `MEMORY.md` wird nur
gemessen; ein BOM zählt dort als ein Zeichen. Die Suche nach Zugängen liest
alle Gedächtnisdateien als `utf-8`: Ein BOM ist dort ein Zeichen mehr am
Anfang und ändert weder Treffer noch Zeilennummer.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| unbekannte Namen still mit Vorgabe beantworten | Tippfehler bleiben unentdeckt |
| relative Pfade ab `os.getcwd()` | die Ablage landet je nach Startordner woanders |
| Zahlen aus Text annehmen | `"180000"` als Zeichenkette vergleicht falsch |
| Konfiguration nur als `utf-8` lesen | eine mit dem Windows-Editor gespeicherte Datei gilt still als fehlend |
