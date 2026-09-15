# wiedervorlage.py — warum es so gebaut ist

Legt beim Sitzungsstart und nach jeder Verdichtung den Stand vor.

---

## Zwei Wege je nach Quelle

| Quelle | Vorgelegt |
|---|---|
| `resume` | nichts — der Verlauf ist da |
| `compact` | Kennmarken-Prüfung, Regeln, Destillat **dieser** Sitzung, Karte des Zettelkastens, Hinweis zum Weiterarbeiten |
| `startup`, `clear` | jüngstes Destillat, jüngstes Rohprotokoll (soweit Budget), Karte, Hausmeister-Meldungen, Update-Hinweis |

Nach einer Verdichtung zählt das Destillat der eigenen Sitzung, nicht das
jüngste im Ordner: Arbeiten zwei Sitzungen parallel, gehörte das jüngste sonst
womöglich der anderen. Den Pfad hat `regelschub.py` beim Ablage-Auftrag im Stand
der Sitzung vermerkt.

Die Regeln kommen nach einer Verdichtung hier mit, weil eine automatische
Verdichtung mitten in einem Arbeitsgang läuft — bis zum nächsten Prompt schöbe
sie sonst niemand nach.

---

## Härten und Nachernte laufen abgekoppelt

Bis 1.x härtete der Hook beim Start alle älteren Transkripte selbst. Bei 74
Transkripten (425 MB) brach Claude Code ihn nach 20 Sekunden ab — und dann fehlte
auch die Wiedervorlage. Jetzt startet der Hook `haertung.py` als eigenen Prozess
mit eigenen Standard-Handles und kehrt sofort zurück. `haertung.py` arbeitet
inkrementell (nur veränderte Dateien), mit einer Sperre gegen Doppelstart.

Die **Nachernte** gehört dazu: Manche Oberflächen melden nie ein Sitzungsende.
Transkripte, die länger als `nachernte_ruhe_sekunden` ruhen und seit der letzten
Ernte gewachsen sind, bekommen ein Rohprotokoll mit dem Zeitstempel ihrer
letzten Aktivität.

---

## Budgets statt Vollständigkeit

`wiedervorlage_gesamt` deckelt Destillat und Rohprotokoll zusammen. Wer alles
vorlegt, hat den Kontext schon am Sitzungsstart gefüllt.

Gekürzt wird am Ende, nie am Anfang: Das Rohprotokoll stellt den Schlussstand
bewusst nach vorn, damit er das Kürzen überlebt.

## Der Altershinweis

Ist der vorgelegte Stand älter als `veraltet_nach_tagen`, wird er als
möglicherweise überholt markiert. **Ein alter Stand ist ein Hinweis, kein
Zustand.**

## Der Update-Hinweis

Steht am Ende, weil er nichts mit der laufenden Arbeit zu tun hat. Er kostet
höchstens `aktualisierung_zeitlimit_sekunden` und nur alle
`aktualisierung_intervall_stunden` eine Netzanfrage. Einzelheiten:
[aktualisierung.md](aktualisierung.md).

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| wieder synchron härten | Timeout beim Start, keine Wiedervorlage |
| `resume`-Kurzschluss entfernen | der Verlauf wird gedoppelt |
| nach Verdichtung das jüngste statt des eigenen Destillats | parallele Sitzungen tauschen ihre Stände |
| Regeln im `compact`-Zweig weglassen | bis zum nächsten Prompt fehlen die Leitplanken |
| Budgets entfernen | der Kontext ist am Sitzungsstart schon voll |
| von vorn kürzen | der Schlussstand fällt weg, also genau die Zusammenfassung |
| Update-Prüfung ohne Zeitlimit | ein hängendes Netz blockiert den Start |
