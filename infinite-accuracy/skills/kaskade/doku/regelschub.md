# regelschub.py — warum es so gebaut ist

Schiebt bei jedem Prompt den Regeltext nach und misst die Kontextlast.

---

## Warum Regeln nachgeschoben werden

Eine einmal gelesene Regel verblasst mit wachsendem Kontext. Was am Anfang der
Sitzung stand, konkurriert nach 200.000 Zeichen mit allem, was seither kam.

Deshalb steht der Regeltext bei **jedem** Prompt neu da — nicht als Erinnerung,
sondern als Teil der aktuellen Eingabe.

Der Preis: Er kostet bei jedem Prompt Kontext. Darum der Deckel
`regeln_max_zeichen`.

---

## `str.replace`, niemals `str.format`

Der Destillatauftrag enthält Platzhalter (`{tok}`, `{datum}`, `{ablage}`), wird
aber mit `replace` gefüllt.

**Der Text kommt aus einer Datei des Nutzers.** Eine einzige geschweifte Klammer
darin — ein JSON-Beispiel, eine Mengenangabe — und `format()` wirft eine
Ausnahme. Dann fällt die gesamte Schwellenlogik aus, und niemand merkt es, weil
der Hook seine Fehler schluckt.

---

## Der Zähler zählt fortlaufend

`kontextlast()` merkt sich die Byte-Position im Transkript und liest nur, was
seit dem letzten Prompt dazugekommen ist. Bei jedem Prompt die ganze Datei zu
parsen wäre Verschwendung.

Gezählt wird, was wirklich im Fenster landet: Text, Denken, Werkzeug-Ein- und
-Ausgaben — nicht die Metadaten drumherum.

**Schrumpft die Datei** (weil getilgt wurde), fängt der Zähler bei 0 an. Ohne
diese Prüfung zeigte die gemerkte Position hinter das Dateiende.

---

## Reihenfolge bei erreichter Schwelle

1. Destillatauftrag an den Text hängen
2. **erst tilgen**
3. **dann den Zähler zurücksetzen**

Andersherum zeigte die gemerkte Byte-Position hinter das Ende der geschrumpften
Datei.

## Der vierte Auslöser

Getilgt wird sonst bei SessionEnd, bei PreCompact und beim SessionStart für die
älteren Transkripte. **Ein Endloschat fällt durch alle drei Netze** — und
sammelt derweil weiter. Der Kontextzähler ist der richtige vierte Ort:
derselbe Schwellwert, dieselbe Gelegenheit, und immer am Userhalt, nie mitten
in einem Arbeitsgang.

---

## Keine eigene Tilgung

`tilgen_anstossen()` ruft `ernte.haerten_und_buchen()` auf und baut nichts nach.
**Zwei Fassungen derselben Erkennung driften auseinander, und dann schützt die
schwächere.**

---

## Im Zweifel stumm

Fällt irgendetwas aus, werden die Regeln trotzdem ausgeliefert — sie sind der
Hauptzweck. Ein Hook, der bei einem Fehler gar nichts zurückgibt, nimmt dem
Modell seine Leitplanken.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| `format()` statt `replace()` | eine geschweifte Klammer in der Nutzerdatei kippt die Schwellenlogik lautlos |
| Zähler nach dem Tilgen nicht zurücksetzen | der Auftrag steht bei jedem weiteren Prompt erneut da |
| Zurücksetzen vor dem Tilgen | die Byte-Position zeigt hinter das Dateiende |
| Eigene Tilgungsmuster einbauen | zwei Fassungen, die schwächere schützt |
| Deckel entfernen | eine lange Regeldatei kostet bei jedem Prompt Kontext |
| Fehler nicht mehr schlucken | ein Fehler im Zähler nimmt dem Modell die Regeln |
