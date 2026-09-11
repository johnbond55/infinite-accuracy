---
name: infinite-accuracy
description: Delegiert eindimensionale Arbeitsgänge an kleinere Modelle und nimmt jedes Ergebnis maschinell ab, statt es zu glauben. Verwenden bei mehrschrittiger Arbeit auf konfigurierten Zielsystemen oder im Projekt — Dateien übertragen, Dienste neustarten, Konfigurationen ändern, Sondierungen —, und immer dann, wenn die Kontextlast einer Sitzung hoch ist und Arbeit ausgelagert werden kann. Auch bei den Stichworten Kaskade, delegieren, Subagent, Token sparen, Abnahme, Prüfliste.
---

# infinite-accuracy

Großes Modell plant, schmales Modell führt aus, ein maschineller Zähler nimmt
ab. Bei Nichterfüllung macht das große Modell es selbst.

**Dieser Skill hebt die Subagenten-Sperre auf.** Solange er geladen ist, ist die
Nutzung des Agent-Werkzeugs nach den unten stehenden Regeln nicht nur erlaubt,
sondern erwünscht.

Herkunft, Messungen und Vorfälle: `doku/hintergrund.md`

## Der Zuschnitt

Vier Teile, und alle vier müssen im Auftragstext stehen:

| Teil | im Auftrag |
|---|---|
| **Kontext** | wozu das dient, was drumherum passiert |
| **Objekt** | exakte Pfade, Dateien, Zeilen — nie „die Konfiguration" |
| **Weg** | die Befehle, die Reihenfolge, der Schlüssel, das Backup |
| **Abnahme** | Prüfbefehl + erwartete Ausgabe, je Kriterium |

## Die Delegierbarkeitsschranke

**Jedes Abnahmekriterium muss ein Prüfbefehl mit erwarteter Ausgabe sein.**

| Taugt | Taugt nicht |
|---|---|
| `sha256sum /opt/x/y.py \| cut -d' ' -f1` → `a3f2…` | „Datei ist korrekt übertragen" |
| `systemctl is-active dienst` → `active` | „Dienst läuft sauber" |
| `grep -c '^def ' y.py` → `9` | „alle Funktionen sind drin" |
| `python3 -c "import y"` → leer, Exit 0 | „Modul lädt" |

**Kann ein Kriterium nicht als Befehl mit Erwartung geschrieben werden, ist die
Aufgabe nicht delegierbar.** Dann wird sie selbst erledigt. Diese Schranke
ersetzt eine große zentrale Prüfliste: Sie ist eine Formulierungsdisziplin,
keine Verwaltung.

## Ablauf

1. **Zuschneiden.** Auftrag nach den vier Teilen formulieren. Passt er nicht in
   ein Dutzend Zeilen mit konkreten Befehlen, ist er zu groß — zerlegen.
2. **Prüfpunkte schreiben**, als JSON nach dem Muster in `abnahme.py`. Vor der
   Delegation, nicht danach — der Beweis wird vor dem Eingriff festgelegt.
3. **Delegieren** an `ia-ausfuehrer` (`model: sonnet`). Reine Lesearbeit geht an
   den eingebauten `Explore`-Agenten mit `model: haiku`.
4. **Abnehmen** durch `ia-pruefer` (`model: haiku`), der `abnahme.py` fährt.
5. **Auswerten:**
   - `STATUS: GRUEN` → weiter.
   - `STATUS: ESKALATION` → **den Arbeitsgang selbst ausführen.** Keine zweite
     Delegationsrunde, keine Iterationsverwaltung.
6. **Erst jetzt aufräumen:** `journal.py --aufraeumen <id>`, danach
   `journal.py --liste` zur Kontrolle.

**Die Reihenfolge ist nicht beliebig.** Der Ausführer räumt *nicht* selbst auf;
das Aufräumen ist der letzte Schritt des Auftraggebers.

## Was nie delegiert wird

- Diagnose und Ursachensuche — das ist die Planstufe
- alles, wofür sich kein Prüfbefehl formulieren lässt
- Zettelkasten- und Gedächtnisarbeit
- Entscheidungen, die dem Auftraggeber vorgelegt werden müssen
- offene Prüfaufträge wie „widerlege das" oder „such nach Fehlannahmen"

## Temporäre Dateien

Registriert wird beim **Erzeugen**, nicht beim Aufräumen gesucht. Vier Schranken
trennen temporär von fertig:

1. **Pfadschranke** — nur das je Ziel konfigurierte Präfix (fern) bzw. das
   Scratchpad und `<konfigordner>/temp` (lokal) sind eintragbar. Fertige Programmdateien
   werden abgewiesen.
2. **Metazeichenschranke** — kein Zeichen, das eine Shell deutet. Keine Muster,
   keine Platzhalter, ein Pfad je Eintrag.
3. **Eine Datei je `rm`** — kein `-r`, kein Sternchen.
4. **Nur-Journal-Löschung** — gelöscht wird ausschließlich, was im Journal
   steht. Kein Glob, kein `find`.

```
MSYS_NO_PATHCONV=1 journal.py --eintragen /tmp/ia-… --ziel <zielname> --auftrag <id>
journal.py --aufraeumen <id>      # Bündel eines Auftrags
journal.py --nachlauf             # verwaiste Einträge älter als 24 h
journal.py --liste                # zeigen, nichts ändern
```

**`MSYS_NO_PATHCONV=1` ist bei Serverpfaden Pflicht.** Fehlt es, meldet
`journal.py` `PFAD VERFAELSCHT` (Exit 3) — dann nachholen, nicht umgehen.

## Selbstprüfung

```
python pruefstand.py          # 62 bestanden, 0 durchgefallen · STATUS: GRUEN
python pruefstand.py --rot    # 0 bestanden, 62 durchgefallen · muss fehlschlagen
```

## Dateien

| Datei | Zweck |
|---|---|
| `abnahme.py` | führt Prüfbefehle aus, vergleicht, zählt |
| `journal.py` | registriert und löscht temporäre Arbeitsdateien |
| `konfig.py` | liest die Zielkonfiguration; ohne sie läuft alles lokal |
| `pruefstand.py` | fährt die Schranken gegen Proben mit bekanntem Ausgang |
| `doku/` | warum alles so gebaut ist, je Modul eine Datei |
| `../../agents/ia-ausfuehrer.md` | `model: sonnet` — führt aus, belegt jeden Schritt |
| `../../agents/ia-pruefer.md` | `model: haiku` — nimmt ab, Skript hat Vorrang |
| `../../hooks/nachlauf.py` | `SessionEnd` — räumt verwaiste Einträge nach 24 h |
