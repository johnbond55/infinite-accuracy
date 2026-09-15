# ernte.py — warum es so gebaut ist

Erntet bei SessionEnd und PreCompact ein Rohprotokoll aus dem Transkript, tilgt
Geheimnisse daraus und steuert vor der Verdichtung, was erhalten bleibt.

---

## Kein Modellaufruf

Die Ernte ist rein mechanisch: Titel, Prompts, angefasste Dateien, ausgeführte
Kommandos, letzte Antwort. Nie klug, aber immer da und immer wahr.

**Ein Hook unter Zeitdruck darf nicht am Timeout scheitern und dann gar nichts
hinterlassen.** Ein Transkript kann mehrere Megabyte groß sein; ein Modellaufruf
darauf braucht Minuten, die der Hook nicht hat.

Das gedeutete Destillat entsteht woanders — `regelschub.py` fordert es bei
erreichter Kontextschwelle an, immer am Userhalt.

---

## Vor der Verdichtung: Riegel und Anweisung

Bei PreCompact prüft der Hook zuerst den Riegel: automatische Verdichtung,
Kontext unter `riegel_bis_token`, kein frisches Destillat → Exit 2, die
Verdichtung wartet. Sonst erntet er, tilgt und gibt auf der Standardausgabe die
Anweisung an die Zusammenfassung aus, mit Kennmarke und Destillat.

Der Riegel steht **vor** der Ernte: Eine aufgeschobene Verdichtung wird bei
jedem Turn erneut versucht, und jedes Mal ein Rohprotokoll zu schreiben, füllte
die Ablage mit Dubletten. Warum das alles so ist: [verdichtung.md](verdichtung.md).

---

## In dieselbe Inode schreiben, nicht tauschen

`transkript_haerten()` öffnet die Datei mit `r+`, schreibt, `truncate()`,
`fsync()`. **Kein `os.replace`.**

Ein Dateitausch hängt einen offenen Append-Handle an die alte Inode ab — und
alles, was danach geschrieben wird, wäre verloren. Weil hier in dieselbe Datei
geschrieben wird, darf auch bei PreCompact getilgt werden, während die Sitzung
noch läuft.

## Zeilen am Umbruch trennen, nicht mit `splitlines()`

`str.splitlines()` trennt auch an U+2028, U+2029, `\x0b`, `\x0c`, `\x1c`–`\x1e`
und `\x85`. Solche Zeichen stehen roh in JSON-Strings eines Transkripts. Bis 2.0
wurde an ihnen getrennt und mit `\n` wieder zusammengefügt — die betroffene
Zeile zerfiel in zwei ungültige JSON-Hälften, sobald in derselben Datei etwas
getilgt wurde. Getrennt wird jetzt nur an `\n`.

## Vier Sicherungsnetze

Es ist die Datei des Harness, nicht unsere:

1. Erst vollständig im Speicher aufbauen, dann in einem Zug schreiben.
2. Jede geänderte Zeile muss wieder gültiges JSON ergeben — Gegenprobe mit
   `json.loads`, sonst bleibt die Originalzeile stehen.
3. Die Zeilenzahl muss gleich bleiben, sonst wird gar nichts geschrieben.
4. Vor dem Schreiben eine Kopie, bei Fehler Rollback.

Die Kopie wird nach Erfolg **gelöscht**. Das ist kein Versehen: Eine Sicherung,
die die Geheimnisse behält, wäre das Gegenteil des Zwecks.

---

## Die Schonfrist wird in Zeichen gemessen

Die letzten `schonfrist_zeichen` (Vorgabe 120.000, rund 30.000 Token) bleiben
unberührt — das ist der lebende Chat.

**Gemessen in Zeichen, nicht in Nachrichten.** 20 Nachrichten sind mal 2.000 und
mal 200.000 Zeichen; der größte Teil der Last stammt aus Werkzeug-Ergebnissen.

`alte_transkripte_haerten()` setzt die Schonfrist auf 0: In fremden, nicht
laufenden Transkripten gibt es nichts zu schonen. Dateien, die jünger als
`nachlese_mindestalter_sekunden` sind, bleiben in Ruhe.

---

## Volltreffer und Feldtreffer

| | Was fällt weg | Warum |
|---|---|---|
| **VOLLTREFFER** | das ganze Match | Muster mit eindeutigem Präfix (AWS, GitHub, Slack, Google, PEM, JWT, age, `sk-`) — ein Fehlalarm ist praktisch ausgeschlossen |
| **FELDTREFFER** | nur der Wert, der Feldname bleibt | ohne Feldname ist der Zusammenhang verloren; greift nur bei Zuweisungen, nicht im Fließtext |

„Das Passwort steht in der .env" bleibt deshalb unberührt. Die Längen sind
bewusst offen (`{30,}`); der Ersatztext `<Secret getilgt: art>` enthält keine
Anführungszeichen und keine Backslashes.

---

## `haerten_und_buchen()` — eine Tür für alle

Tilgen und Protokollieren stehen zusammen, weil sie aus mehreren Richtungen
aufgerufen werden: SessionEnd, PreCompact, der Ablage-Auftrag in `regelschub.py`
und der Hintergrundlauf. Stünde das Buchen nur an einer Stelle, hinterließe die
häufigste Tilgung keine Spur.

## `ernte_vermerken()`

Vermerkt die geerntete Größe eines Transkripts in `<state>/haertung.json`. Ohne
den Vermerk erntete `haertung.py` dieselbe Sitzung ein zweites Mal nach.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| `os.replace` statt `r+` | ein offener Append-Handle schreibt ins Leere, das Transkript verliert alles Folgende |
| zurück zu `splitlines()` | Transkriptzeilen mit U+2028 zerfallen beim Tilgen |
| Zeilenzahl-Invariante entfernen | eine verschluckte Zeile fällt niemandem auf |
| Sicherungskopie behalten | die Geheimnisse bleiben in der Kopie stehen |
| Riegel nach der Ernte | ein Rohprotokoll je aufgeschobenem Versuch |
| Standardausgabe bei SessionEnd | harmlos, aber Rauschen |
| Ernte mit Modellaufruf | Timeout, und dann bleibt gar kein Protokoll |
