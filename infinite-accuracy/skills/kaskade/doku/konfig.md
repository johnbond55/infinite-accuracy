# konfig.py — warum es so gebaut ist

Der eine Zugang zur Konfiguration. Alles liegt in
`<projekt>/.claude/infinite-accuracy/` (anders: Umgebungsvariable `IA_KONFIG`).

| Datei | Inhalt |
|---|---|
| `ziele.json` | Fernziele für `journal.py` und `abnahme.py` |
| `konfig.json` | Zahlen (`VORGABEN`), Schalter (`ZEICHEN_VORGABEN`), Ablageorte (`pfade`) |
| `regeln.md` | wird bei jedem Prompt eingespeist |
| `destillat.md` | eigener Wortlaut des Ablage-Auftrags; Platzhalter `{tok} {schwelle} {datum} {ablage} {eingang} {zettel}` |
| `register-texte.json` | Überschriften des Gedächtnisindex |
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

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| unbekannte Namen still mit Vorgabe beantworten | Tippfehler bleiben unentdeckt |
| relative Pfade ab `os.getcwd()` | die Ablage landet je nach Startordner woanders |
| Zahlen aus Text annehmen | `"180000"` als Zeichenkette vergleicht falsch |
