# wiedervorlage.py — warum es so gebaut ist

Legt beim Sitzungsstart den letzten Stand wieder vor.

---

## Die Reihenfolge ist die Botschaft

1. **Ältere Transkripte härten** — bevor irgendetwas vorgelegt wird.
2. **Destillat** — das gedeutete, kurze.
3. **Rohprotokoll** — nur soweit Budget bleibt.
4. **Hausmeister-Meldungen** — Gedächtnis, liegengebliebene Sicherungen.

Das Destillat kommt zuerst, weil es die Deutung enthält. Das Rohprotokoll ist
der Rückfall, wenn keines geschrieben wurde — und bekommt dann mehr Platz
(`wiedervorlage_roh_allein` statt `wiedervorlage_roh`).

## Warum das Härten hierher gehört

Diese Dateien liegen garantiert niemandem unter den Händen — anders als das
laufende Transkript. Für einen Endloschat, der nie ein SessionEnd sieht, ist
das überhaupt der einzige Weg.

---

## Bei `resume` passiert nichts

Dort ist der Verlauf ohnehin da. Alles vorzulegen wäre Doppelung und kostete
nur Kontext.

---

## Budgets statt Vollständigkeit

`wiedervorlage_gesamt` deckelt die Summe. Wer alles vorlegt, hat den Kontext
schon am Sitzungsstart gefüllt — genau das, was dieses Paket verhindern soll.

Gekürzt wird am Ende, nie am Anfang: Das Rohprotokoll stellt den Schlussstand
bewusst nach vorn, damit er das Kürzen überlebt.

---

## Der Altershinweis

Ist der vorgelegte Stand älter als `veraltet_nach_tagen`, wird er als
möglicherweise überholt markiert. **Ein alter Stand ist ein Hinweis, kein
Zustand** — was er behauptet, muss vor der Planung nachgeprüft werden.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| Härten nach dem Vorlegen | Geheimnisse aus alten Transkripten stehen im neuen Kontext |
| `resume`-Kurzschluss entfernen | der Verlauf wird gedoppelt |
| Budgets entfernen | der Kontext ist am Sitzungsstart schon voll |
| Von vorn kürzen | der Schlussstand fällt weg, also genau die Zusammenfassung |
| Altershinweis entfernen | ein Monate alter Stand liest sich wie der aktuelle |
