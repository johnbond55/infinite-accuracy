# gedaechtnis.py — warum es so gebaut ist

Baut den Kurzindex des Gedächtnisses und meldet, was darin faul ist.

---

## Kurzindex und ausführliches Register getrennt

| Datei | Wird geladen | Inhalt |
|---|---|---|
| `MEMORY.md` | **immer** | eine Zeile je Eintrag: Stichwort, kein Inhalt |
| `REGISTER.md` | nur auf Zuruf | Tabelle mit Typ, Größe, Verweisen, vollen Beschreibungen |

Der Kurzindex ist ein **Schlagwort-Register, kein Wissensspeicher**: Wer ein
Stichwort trifft, liest die eine Datei nach, statt zu vermuten. Stünde der
Inhalt schon im Index, würde er bei jedem Sitzungsstart mitbezahlt.

---

## Melden statt tilgen

`geheimnisse_finden()` ändert **nichts**. Drei Unterschiede zum Transkript:

1. **Melden statt tilgen.** Das Gedächtnis ist von Hand gepflegter Inhalt; ein
   Fehlalarm, der hier Text zerstört, kostet mehr als der Fund einbringt.
2. **Fundort ohne Wert.** Datei, Zeile, Art — nie der Wert selbst. Sonst stünde
   das Geheimnis durch die Warnung wieder im Kontext.
3. **Platzhalter zählen nicht.** `{env:…}`, `$VAR`, `<dein-token>` lösen keinen
   Alarm aus.

Beim Tilgen ist Übererkennung gewollt; bei einer Warnung, die bei jedem
Sitzungsstart erscheint, ist sie schädlich — **eine Warnung, die nie stimmt,
wird nach dem dritten Mal ignoriert.** Wie viele übergangen wurden, steht
trotzdem im Bericht: Eine stille Unterdrückung liest sich wie „nichts
gefunden".

Die Muster kommen aus `ernte.py` und werden nicht nachgebaut.

---

## Nur slug-förmige Verweise zählen

`[[abc-def]]` ist ein Verweis. `[[ZETTEL: thema]]`, `[["RemoveTable","X"]]` oder
`[[Großes Wort]]` sind etwas anderes und dürfen keinen Fehlalarm auslösen.

---

## Waisen als Sammelmeldung

Einträge ohne eingehenden Verweis werden gezählt, nicht einzeln aufgelistet.
Fünfzehn Einzelzeilen wären Rauschen — und unvernetzt heißt nicht wertlos.
Gemeldet wird erst, wenn mehr als ein Viertel betroffen ist.

---

## `--register` überschreibt vollständig

`MEMORY.md` und `REGISTER.md` werden neu gebaut, nicht ergänzt. Handgeschriebene
Zusätze darin gehen verloren. Deshalb bleibt `--register` ein Aufruf von Hand
und läuft nie in einem Hook; am Sitzungsstart läuft nur die meldende
`kurzmeldung()`.

---

## Der Fundort des Gedächtnisses

`memory_dir()` sucht in dieser Reihenfolge: ausdrückliche Vorgabe,
`<projekt>/.claude/memory`, dann `~/.claude/projects/<slug>/memory`. Der
`slug()` bildet den Projektpfad so ab, wie Claude Code seine Ordner benennt —
er wird nie geglaubt, sondern nur als Kandidat geprüft.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| Tilgen statt melden | ein Fehlalarm zerstört handgepflegten Inhalt |
| Wert in die Meldung aufnehmen | das Geheimnis steht durch die Warnung wieder im Kontext |
| Platzhalter-Filter entfernen | die Startmeldung warnt bei jedem Start falsch und wird ignoriert |
| Übergangene nicht melden | stille Unterdrückung liest sich wie „nichts gefunden" |
| Eigene Muster statt Import aus `ernte.py` | zwei Fassungen, die schwächere schützt |
| `--register` in einen Hook hängen | handgeschriebene Zusätze werden bei jedem Start überschrieben |
| Inhalt in den Kurzindex schreiben | er wird bei jedem Sitzungsstart mitbezahlt |
