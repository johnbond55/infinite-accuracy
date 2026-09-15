# regelschub.py — warum es so gebaut ist

Schiebt bei jedem Prompt den Regeltext nach, misst die Kontextlast und fordert
die Ablage an.

---

## Warum Regeln nachgeschoben werden

Eine einmal gelesene Regel verblasst mit wachsendem Kontext. Was am Anfang der
Sitzung stand, konkurriert nach 200.000 Token mit allem, was seither kam.

Deshalb steht der Regeltext bei **jedem** Prompt neu da — nicht als Erinnerung,
sondern als Teil der aktuellen Eingabe. Der Preis: Er kostet bei jedem Prompt
Kontext. Darum der Deckel `regeln_max_zeichen`.

---

## `str.replace`, niemals `str.format`

Der Ablage-Auftrag enthält Platzhalter (`{tok}`, `{schwelle}`, `{datum}`,
`{ablage}`, `{eingang}`, `{zettel}`), wird aber mit `replace` gefüllt.

**Der Text kann aus einer Datei des Nutzers kommen** (`destillat.md`). Eine
einzige geschweifte Klammer darin — ein JSON-Beispiel, eine Mengenangabe — und
`format()` wirft. Dann fällt die gesamte Schwellenlogik aus, und niemand merkt
es, weil der Hook seine Fehler schluckt.

---

## Kontext aus der usage-Zeile, nicht aus Zeichen

Bis 1.x zählte der Hook Zeichen im Transkript und teilte durch vier. Gemessen am
11.09.2026 lag das Verhältnis von Dateigröße zu Kontext zwischen 4,5 und 14,5:
das Denken fehlte, Metadaten zählten mit. Jetzt gilt die usage-Zeile der
jüngsten Antwort — `input_tokens + cache_creation_input_tokens +
cache_read_input_tokens`, genau das, was die API berechnet hat. Gelesen werden
nur die letzten 4 MB des Transkripts, von hinten.

## Einmal je Überschreitung

Der Auftrag kommt einmal, wenn `ablage_schwelle_token` überschritten ist. Scharf
wird er wieder, wenn der Kontext unter die Schwelle fällt oder hinter der
jüngsten Antwort eine Verdichtungsmarke steht. Der Stand liegt je Sitzung in
`<state>/last-<sitzung>.json`; dort stehen auch `auftrag_ts` und der Pfad des
angeforderten Destillats — daran misst `ernte.py` den Riegel.

## Immer am Userhalt

UserPromptSubmit ist ein Userhalt: Der Nutzer hat gerade geschrieben, kein
Arbeitsgang läuft. Die Ablage unterbricht also nichts. Was zwischen zwei
Userhalten über die Schwelle springt, fängt der Riegel in `ernte.py` auf.

## Kennmarke nachprüfen

Konnte `wiedervorlage.py` die Kennmarke nach einer Verdichtung nicht prüfen
(Zusammenfassung noch nicht im Transkript), prüft dieser Hook beim nächsten
Prompt nach. Fehlt sie, steht eine Warnung im Kontext. Einzelheiten:
[verdichtung.md](verdichtung.md).

---

## Der vierte Auslöser der Tilgung

Getilgt wird sonst bei SessionEnd, bei PreCompact und im Hintergrundlauf für die
älteren Transkripte. **Ein Endloschat fällt durch alle drei Netze** — und sammelt
derweil weiter. Der Ablage-Auftrag ist der richtige vierte Ort: derselbe
Schwellwert, dieselbe Gelegenheit, immer am Userhalt.

## Keine eigene Tilgung

`tilgen_anstossen()` ruft `ernte.haerten_und_buchen()` auf und baut nichts nach.
**Zwei Fassungen derselben Erkennung driften auseinander, und dann schützt die
schwächere.**

## Im Zweifel stumm

Fällt irgendetwas aus, werden die Regeln trotzdem ausgeliefert — sie sind der
Hauptzweck. Ein Hook, der bei einem Fehler gar nichts zurückgibt, nimmt dem
Modell seine Leitplanken.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| `format()` statt `replace()` | eine geschweifte Klammer in der Nutzerdatei kippt die Schwellenlogik lautlos |
| zurück zur Zeichenzählung | der Auftrag kommt je nach Werkzeugausgaben viel zu früh oder zu spät |
| `gemeldet` nach der Verdichtung nicht zurücksetzen | nach der ersten Verdichtung kommt nie wieder ein Auftrag |
| `auftrag_ts` / `destillat` nicht im Stand | der Riegel sperrt dauerhaft bis `riegel_bis_token` |
| eigene Tilgungsmuster einbauen | zwei Fassungen, die schwächere schützt |
| Deckel entfernen | eine lange Regeldatei kostet bei jedem Prompt Kontext |
| Fehler nicht mehr schlucken | ein Fehler im Zähler nimmt dem Modell die Regeln |
