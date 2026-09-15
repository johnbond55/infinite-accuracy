# Änderungen

## 2.0.0 — 15.09.2026

### Neu

- **Gesteuerte Verdichtung.** `ernte.py` gibt der Zusammenfassung bei PreCompact
  eine Anweisung mit Kennmarke und schiebt die automatische Verdichtung auf,
  solange in der Sitzung nicht abgelegt wurde (bis `riegel_bis_token`).
  `wiedervorlage.py` prüft die Kennmarke danach.
- **Zettelkasten** `skills/zettel/`: ablegen, sinngemäß suchen (Dossier,
  Schlagwort, Volltext), Trefferseiten im Ganzen lesen, Besuchs-Log beim Ablegen,
  Karte, Projekte-Regal, Reflexionen, Hausmeister. Nach dem Vorbild der
  Schreibstube, ohne Modellaufruf.
- **Update-Routine** `hooks/aktualisierung.py` und `installieren.py`: Hinweis
  beim Sitzungsstart, Installation aus dem Archiv des Tags mit Prüfsummen,
  Sicherung, Abnahme und Rückbau.
- `hooks/haertung.py`: Härtung älterer Transkripte und Nachernte laufen
  abgekoppelt vom Sitzungsstart.
- Agent `ia-leser` (haiku) für Lesearbeit.

### Geändert

- `regelschub.py` misst echte Token aus der usage-Zeile statt Zeichen und
  fordert ab `ablage_schwelle_token` (180.000) die Ablage an, statt `/compact`
  vorzuschlagen. `schwelle_zeichen` entfällt.
- `wiedervorlage.py` hat einen eigenen Zweig nach der Verdichtung (Regeln,
  Destillat dieser Sitzung, Karte) und zeigt Karte und Update-Hinweis beim Start.
- `konfig.py` kennt Schalter (`zeichen()`) und Ablageorte (`pfad()`).
- `marketplace.json` liegt in `.claude-plugin/`, wie die Doku von Claude Code es
  verlangt.
- Zeilenenden sind LF (`.gitattributes`).

### Behoben

- Die Tilgung trennte Transkriptzeilen mit `splitlines()` auch an U+2028 und
  zerbrach dabei das JSON betroffener Zeilen.

## 1.0.0 — 09.09.2026

- Erste Fassung: Kaskade mit Abnahme, Journal für temporäre Dateien, Ernte,
  Tilgung, Regelschub, Wiedervorlage, Gedächtnisindex.
