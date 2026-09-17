# gedaechtnis.py — warum es so gebaut ist

Baut den Kurzindex des Gedächtnisses und meldet, was darin faul ist.

---

## Kurzindex und ausführliches Register getrennt

| Datei | Wird geladen | Inhalt |
|---|---|---|
| `MEMORY.md` | **immer**, aber nur bis zur Ladegrenze | eine Zeile je Eintrag: Stichwort, kein Inhalt; wird es zu lang, die älteren nur als Schlagwort |
| `REGISTER.md` | nur auf Zuruf | Tabelle mit Typ, Größe, Verweisen, vollen Beschreibungen |

Der Kurzindex ist ein **Schlagwort-Register, kein Wissensspeicher**: Wer ein
Stichwort trifft, liest die eine Datei nach, statt zu vermuten. Stünde der
Inhalt schon im Index, würde er bei jedem Sitzungsstart mitbezahlt.

---

## Die Ladegrenze — Budget statt stilles Abschneiden

Claude Code lädt von `MEMORY.md` nur die ersten **200 Zeilen bzw. 25.000
Zeichen**. Die Zeichen zählen so, wie sie auf der Platte stehen — unter
Windows also mit dem Wagenrücklauf jedes Zeilenendes. Was darüber steht, fehlt
ohne Fehler; nur ein Hinweis im Kontext sagt es.

Anlass 17.09.2026: Das Gedächtnis dieses Projekts hatte 236 Zeilen und 38.887
Zeichen mit CRLF. Gemessen: bis Zeile 152 sind es 24.851 Zeichen, bis Zeile 153
25.019 — geschnitten wurde ab Zeile 153. Ohne Wagenrücklauf wären es bei Zeile
153 nur 24.866 gewesen; nach Bytes gezählt wäre schon ab Zeile 148
geschnitten worden (bis Zeile 148: 25.049 Bytes, bis Zeile 152: 25.733). Es
fehlten die hinteren „Laufenden Vorhaben" ab `metabase-einbau…` und **alle
Verweise**.

Seitdem baut `--register` den Kurzindex in ein Budget: `index_max_zeilen` (190)
und `index_max_zeichen` (24.000), mit Wagenrücklauf gezählt und auf die
Ladegrenze gedeckelt. Der Abstand ist Reserve für Nachträge zwischen zwei
Läufen.

1. **Rang.** Regeln (`feedback`) und Angaben zum Nutzer (`user`) zuerst, dann
   das Jüngste — `modified` aus dem Kopf, sonst die Dateizeit.
2. **Schlagworte.** Passt nicht alles, stehen die hinteren Einträge nur mit
   ihrem Dateinamen unter ihrer Rubrik: `- Schlagworte: a · b · c`, auf
   höchstens 200 Zeichen je Zeile umbrochen, Folgezeilen mit zwei Leerzeichen
   eingerückt. Ein Schlagwort kostet nur den Dateinamen, am Gedächtnis dieses
   Projekts rund ein Fünftel einer ganzen Zeile; so bleibt jeder Eintrag
   auffindbar.
3. **Ganze Zeilen.** So viele, wie ins Budget passen, in Rangfolge; innerhalb
   der Rubrik bleibt die alphabetische Ordnung.
4. **Hinweis im Kopf.** Der Kopf sagt, wie viele nur als Schlagwort stehen.
   Passt nicht einmal jedes Schlagwort, fehlen die ältesten ganz; der Kopf sagt
   auch das, und die Prüfung meldet „Kurzindex zu klein".

Wer `MEMORY.md` von Hand über die Ladegrenze verlängert, bekommt beim
Sitzungsstart „Kurzindex zu lang" — der Ausweg ist `gedaechtnis.py --register`.

Die bessere Antwort auf einen vollen Index bleibt inhaltlich: Erledigtes
ausmisten, Verwandtes zusammenlegen. Das Budget sorgt nur dafür, dass bis dahin
nichts still verschwindet.

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
| Budget ohne Wagenrücklauf zählen | unter Windows ist jede Zeile ein Zeichen länger als gezählt — der Schnitt kommt früher |
| Budget gleich der Ladegrenze | der erste Nachtrag von Hand fällt schon wieder hinten heraus |
| Einträge ohne Hinweis weglassen | ein fehlender Eintrag sieht aus wie nie gewesen |
| nach Alphabet statt nach Rang kürzen | Regeln und das Jüngste fallen als Erste auf ein Schlagwort zurück |
| Grenze in Bytes messen | Umlaute zählen doppelt, der Index wird ohne Not gekürzt |
