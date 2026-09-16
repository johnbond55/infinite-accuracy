# Änderungen

## Lizenzwechsel — 16.09.2026

- Lizenz von **MIT** auf **EUPL-1.2** (European Union Public Licence)
  gewechselt. Grund: die MIT-Lizenz laesst zu, dass Ableitungen geschlossen
  werden; das Werkzeug soll offen bleiben. Die EUPL haelt zugleich den
  Urhebervermerk fest, liegt als verbindlicher deutscher Rechtstext vor und
  ist zu GPL, AGPL, LGPL, MPL, EPL, OSL, CeCILL und LiLiQ kompatibel.
- Keine Codeaenderung, keine neue Paketfassung: `version.json`,
  `plugin.json` und `PRUEFSUMMEN.json` sind unberuehrt.
- Fassungen bis einschliesslich 2.0.1 bleiben unter MIT verfuegbar.

## 2.0.1 — 16.09.2026

### Behoben

- **Die Kennmarke blieb ungeprüft.** `wiedervorlage.py` prüft sie beim
  Sitzungsstart — dort steht die Zusammenfassung aber oft noch nicht im
  Transkript (Claude Code schreibt sie erst danach), und die Nachprüfung in
  `regelschub.py` hing an `verdichtet`, das nach der ersten Antwort nicht
  mehr anschlägt. Ergebnis: „nicht prüfbar" beim Start, danach nie wieder
  eine Prüfung. Die Nachprüfung läuft jetzt bei jedem Prompt, bis sie ein
  Urteil hat.
- **Fehlalarm bei aufgeschobener Verdichtung.** Hielt der Riegel die
  Verdichtung zurück, verglich die Prüfung die neue Kennmarke mit der
  Zusammenfassung der VORIGEN Verdichtung und hätte „fehlt" gemeldet. Jetzt
  entscheidet der Zeitvergleich: eine ältere Zusammenfassung heißt
  „unprüfbar".

### Geändert

- `ernte.zusammenfassung_mit_zeit()` liefert Text und Zeitstempel der
  jüngsten Zusammenfassung. `letzte_zusammenfassung()` bleibt als Name
  bestehen, `kennmarke_pruefen()` nimmt beide Zeiten optional entgegen —
  alte Aufrufe verhalten sich wie bisher.
- Prüfstand: 162 Proben (vier neue). Die Prozessprobe „Kennmarke wird auch
  nach der ersten Antwort noch geprüft" fällt mit der alten Bedingung durch.

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
