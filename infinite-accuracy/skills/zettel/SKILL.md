---
name: zettel
description: Zettelkasten des Projekts — ablegen, sinngemäß suchen, Trefferseiten im Ganzen lesen. Verwenden, bevor über früher Besprochenes, Festlegungen, Pfade, Zahlen oder Entscheidungen geraten wird; beim Ablage-Auftrag von infinite-accuracy; nach einer Verdichtung; bei den Stichworten nachschlagen, Zettel, Dossier, Journal, früher besprochen, was hatten wir festgelegt, Stand zu.
---

# Zettelkasten

Das Gedächtnis über Verdichtungen und Sitzungen hinweg: Der Chat ist flüchtig,
der Zettelkasten nicht. Aufbau nach dem Vorbild der Schreibstube (Ferradea).

Werkzeug: `python "<dieser Ordner>/zettel.py" <befehl>`. Ablage in
`.claude/zettelkasten/` (anderswo: `pfade.zettelkasten` in `konfig.json`).

## Nachschlagen statt raten

1. `zettel.py suche <begriff> [<begriff> …]` — Stufen: Dossier (Name exakt, dann
   Teilwort) → Schlagwort-Register → Volltext. Liefert Seitennamen, kein Material.
2. `zettel.py lies <seite>` — die Trefferseite **im Ganzen**. Mit einem Thema statt
   eines Seitennamens: das Dossier samt verlinkten Journal-Tagen.
3. `zettel.py stand <thema>` — Material für den Wiedereinstieg.

Die Suchbegriffe sinngemäß wählen: Fachwort und Alltagswort, Synonyme, Namen von
Dateien, Diensten und Orten. Kein Treffer ist ein Befund — dann sagen, nicht
erfinden.

## Ablegen

Beim Ablage-Auftrag (oder auf Zuruf) eine JSON-Datei schreiben und ablegen:

```
zettel.py ablegen <datei.json>
```

```json
{
  "quelle": "sitzung-<erste 8 Zeichen der Sitzungs-ID>",
  "projekt": "",
  "eintraege": [
    {
      "titel": "kurz und sprechend",
      "thema": "Dossier, in das der Eintrag gehört",
      "text": "**Ausgangslage:** …\n\n**Weg:** …\n\n**Ergebnis:** …",
      "schlagworte": ["bis", "fünf", "Stichworte"]
    }
  ],
  "dossiers": {
    "Dossiername": {"stand": "Ein Satz vorn, dann Absätze.", "gesichert": "- …", "offen": "- [ ] …"}
  },
  "ressourcen": {"Dossiername": ["[Name](pfad-oder-url) — Einzeiler"]},
  "erkenntnisse": ["höchstens zwei Zeilen"]
}
```

| Regel | Warum |
|---|---|
| 1–6 Einträge, je Thema einer, Anzahl nach Fakten- und Lösungsdichte | ein Zettel je Thema ist später auffindbar |
| Ausgangslage → Weg → Ergebnis | so liest man es in drei Monaten noch |
| **Fakten sind heilig:** Methoden, Orte, Pfade, Werkzeuge, Zahlen, Hashes, Befehle, Entscheidungen wörtlich | sie sind die Suchanker |
| Festlegungen und Freigaben des Nutzers wörtlich, mit Datum | sonst werden sie neu verhandelt |
| Dossier-Stand fortschreiben: der erste Satz ist die Karte; Überholtes mit `[veraltet]` stempeln, nichts löschen | die Titelseite lebt, der Strom bleibt |
| Erkenntnisse nur, wenn neu · selbstbezogen · verallgemeinernd · folgenreich (im Projekt keine) | der Index ist die Spitze der Pyramide |
| Keine Geheimnisse (Schlüssel, Passwörter, Token) | der Zettelkasten reist mit dem Projekt |

`projekt` leer lassen legt in die Wurzel; ein Name legt ins Regal dieses Projekts.

Der Besuchs-Log im Dossier entsteht beim Ablegen von selbst: je Eintrag ein Link
auf den Journal-Tag. Lesen hinterlässt keinen Vermerk.

## Kreis-Prüfung

Meldet `ablegen` eine Kreis-Prüfung, im Chat nach dem mitgelieferten Wortlaut
urteilen: DELTA → nichts sagen; KREIS → dem Nutzer in einem Absatz melden, mit
genau einem Ausweg.

## Weitere Befehle

| Befehl | Wirkung |
|---|---|
| `karte` | je Dossier ein Satz und die jüngsten Erkenntnisse — liegt nach jeder Verdichtung im Kontext |
| `landkarte`, `fortschritt` | Stand und Offenes aller Dossiers bzw. das Gesicherte |
| `projekte`, `--projekt <name>` | eigenes Regal je Projekt (Journal, Dossiers, Roadmap) |
| `portieren <thema> <projekt>` | Journal-Abschnitte wörtlich ins Projekt-Journal |
| `reflexion <JJJJ-MM-TT> <datei>`, `reflexionen` | offene Fragen mit Prüftermin |
| `roh <datei>` | Text 1:1 ins Journal |
| `hausmeister` | verwaiste Seiten melden; `--archivieren` nur mit Freigabe des Nutzers |
| `reindex` | Übersichten und Register neu aufbauen |

## Grenzen

- Kein Modellaufruf im Werkzeug: Inhalt, Dossier-Stand und Kreis-Urteil kommen aus dem Chat.
- Nicht zu verwechseln mit einem Zettelkasten auf einem Server: dieser liegt im Projekt.
- Begründungen und Fallen: `../kaskade/doku/zettel.md`
