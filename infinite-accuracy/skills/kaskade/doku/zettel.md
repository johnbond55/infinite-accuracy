# zettel.py — warum es so gebaut ist

Der Zettelkasten des Projekts. Vorbild ist die Ablage der Schreibstube auf
Ferradea (`ablage.py`, `destille.py`, `journal_hausmeister.py`).

---

## Warum überhaupt

Eine Verdichtung behält die Zusammenfassung und die jüngsten Wechsel. Alles
andere ist aus dem Kontext — und wird geraten, wenn es nicht auffindbar abgelegt
ist. Der Zettelkasten macht es auffindbar: Recherche kostet dann eine Suche und
eine gelesene Seite statt eines langen Kontexts.

## Die Schichten

| Schicht | Datei | Rolle |
|---|---|---|
| Journal | `Journal/JJJJ/JJJJ-MM-TT.md` | Strom, append-only; `## HH:MM — Titel`, `Schlagworte:`, `_Quelle:_` |
| Dossiers | `Dossiers/<slug>.md` | Titelseite (Stand, Gesichert, Offen, Ressourcen) und Besuchs-Log |
| Meta-Meta | `Erkenntnis-Index.md` bzw. `Projekte/<slug>/Roadmap.md` | eine Zeile je Einsicht |

Dazu `Schlagwort-Register.md`, `Reflexionen.md` und die Übersichten `Journal.md`,
`Dossiers.md`, `Projekte.md`. Jede Seite muss von ihrer Übersicht aus erreichbar
sein — sonst ist sie für den Hausmeister eine Waise.

---

## Entscheidungen beim Nachbau

| Ferradea | hier | Warum |
|---|---|---|
| Destille, Kurator und Erkenntnis-Automatik rufen ein Modell | kein Modellaufruf; den Inhalt schreibt das Modell im Chat als JSON | das Modell sitzt ohnehin im Chat; ein zweiter Aufruf kostet und erfindet |
| Kreis-Wächter urteilt per Modell | Skript zählt, legt Wortlaut und Texte vor, Urteil im Chat | dito |
| Besuchs-Log beim Ablegen | unverändert; Lesen hinterlässt keinen Vermerk | Festlegung vom 15.09.2026 |
| Hausmeister archiviert per Cron | meldet nur; `--archivieren` auf Zuruf | Verschieben braucht eine Freigabe |
| Suche: Dossiername, dann Register | dazu Volltext als dritte Stufe | ungetaggte Fakten sollen auffindbar bleiben |
| `chown` auf die Dienst-uid, `zoneinfo` Europe/Berlin | entfällt, Ortszeit des Rechners | Windows kennt keine uid; `zoneinfo` braucht dort `tzdata` |
| Termin-Wächter, Links, Schnappschüsse, Matrix | nicht übernommen | Dienste und Gesprächsfunktionen der Schreibstube |
| Kreis-Wortlaut „die Johannes … abgelegt hat" | „die … abgelegt wurde" | öffentliches Paket |

## Windows und Sync-Ordner

- **Seitennamen über `as_posix()`.** `str(Path.relative_to())` liefert unter
  Windows Backslashes; Wikilinks und Register verlören ihre Treffer.
- **Schreiben mit `newline="\n"`.** Sonst entstehen CRLF-Seiten, die die
  Abschnitts-Muster anders lesen.
- **Umschreiben atomar** (`.ia-neu` + `os.replace`). Ein Abbruch mitten im
  Schreiben ließe sonst eine leere Titelseite zurück.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| Besuchs-Log beim Umschreiben des Stands mit überschreiben | die Spur zu den Journal-Tagen ist weg |
| Journal umschreiben statt anhängen | der Strom ist nicht mehr die Wahrheit |
| `_index_link` weglassen | neue Seiten sind Waisen |
| `as_posix()` entfernen | unter Windows findet die Suche nichts mehr |
| `lies` ohne Wurzelprüfung | ein Seitenname wie `../../x` liest Dateien außerhalb |
| Volltext vor Dossier und Register | die präzisen Treffer gehen im Rauschen unter |
| Hausmeister archiviert automatisch | Lebendes verschwindet ohne Freigabe |
