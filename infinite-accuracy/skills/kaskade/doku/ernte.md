# ernte.py — warum es so gebaut ist

Erntet bei SessionEnd und PreCompact ein Rohprotokoll aus dem Transkript und
tilgt Geheimnisse daraus.

---

## Kein Modellaufruf

Die Ernte ist rein mechanisch: Titel, Prompts, angefasste Dateien, ausgeführte
Kommandos, letzte Antwort. Nie klug, aber immer da und immer wahr.

**Ein Hook unter Zeitdruck darf nicht am Timeout scheitern und dann gar nichts
hinterlassen.** Ein Transkript kann mehrere Megabyte groß sein; ein
Modellaufruf darauf braucht Minuten, die der Hook nicht hat.

Das gedeutete Destillat entsteht woanders — `regelschub.py` fordert es bei
erreichter Kontextschwelle an, und zwar immer am Userhalt.

---

## In dieselbe Inode schreiben, nicht tauschen

`transkript_haerten()` öffnet die Datei mit `r+`, schreibt, `truncate()`,
`fsync()`. **Kein `os.replace`.**

Ein Dateitausch hängt einen offenen Append-Handle an die alte Inode ab — und
alles, was danach geschrieben wird, wäre verloren. Weil hier in dieselbe Datei
geschrieben wird, darf auch bei PreCompact getilgt werden, während die Sitzung
noch läuft.

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

Die letzten `schonfrist_zeichen` (Vorgabe 120.000, rund 30.000 Tokens) bleiben
unberührt — das ist der lebende Chat.

**Gemessen in Zeichen, nicht in Nachrichten.** 20 Nachrichten sind mal 2.000 und
mal 200.000 Zeichen; der größte Teil der Last stammt aus Werkzeug-Ergebnissen,
nicht aus dem Gespräch. Eine Zählung nach Nachrichten wäre Zufall.

`alte_transkripte_haerten()` setzt die Schonfrist auf 0: In fremden, nicht
laufenden Transkripten gibt es nichts zu schonen. Dateien, die jünger als
`nachlese_mindestalter_sekunden` sind, bleiben in Ruhe — dort schreibt
vielleicht noch jemand.

---

## Volltreffer und Feldtreffer

| | Was fällt weg | Warum |
|---|---|---|
| **VOLLTREFFER** | das ganze Match | Muster mit eindeutigem Präfix (AWS, GitHub, Slack, Google, PEM, JWT, age, `sk-`) — ein Fehlalarm ist praktisch ausgeschlossen |
| **FELDTREFFER** | nur der Wert, der Feldname bleibt | ohne Feldname ist der Zusammenhang verloren; greift nur bei Zuweisungen, nicht im Fließtext |

„Das Passwort steht in der .env" bleibt deshalb unberührt.

Die Längen sind bewusst offen (`{30,}` statt fester Länge mit Wortgrenze): Ein
Muster mit fester Länge greift bei jeder Abweichung nicht mehr.

Der Ersatztext `<Secret getilgt: art>` enthält keine Anführungszeichen und
keine Backslashes — er muss in einem JSON-String unfallfrei stehen können.

---

## `haerten_und_buchen()` — eine Tür für alle

Tilgen und Protokollieren stehen zusammen in einer Funktion, weil sie aus drei
Richtungen aufgerufen werden: SessionEnd, PreCompact und der Kontextzähler in
`regelschub.py`. Stünde das Buchen nur im SessionEnd-Zweig, hinterließe die
häufigste Tilgung keine Spur — genau dort, wo sie am wichtigsten ist.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| `os.replace` statt `r+` | ein offener Append-Handle schreibt ins Leere, das Transkript verliert alles Folgende |
| Zeilenzahl-Invariante entfernen | eine verschluckte Zeile fällt niemandem auf |
| Sicherungskopie behalten | die Geheimnisse bleiben in der Kopie stehen |
| Feste Längen in den Mustern | ein Token mit abweichender Länge wird nicht mehr erkannt |
| Feldtreffer auf Fließtext ausweiten | jeder Satz über Passwörter wird zerhackt |
| Ernte mit Modellaufruf | Timeout, und dann bleibt gar kein Protokoll |
