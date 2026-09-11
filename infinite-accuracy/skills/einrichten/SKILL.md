---
name: einrichten
description: Richtet infinite-accuracy für dieses Projekt ein — fragt nach den Zielsystemen, legt die Konfiguration an und prüft sie. Verwenden bei Erstinstallation, bei „infinite-accuracy einrichten", „Ziel hinzufügen", „konfigurieren", oder wenn journal.py ein unbekanntes Ziel meldet.
---

# infinite-accuracy einrichten

Du führst den Nutzer durch die Konfiguration. Alles Nötige steht hier; frage im
Fließtext, nicht mit Auswahlwerkzeugen.

## Schritt 1 — Stand feststellen

```
python "${CLAUDE_PLUGIN_ROOT}/skills/kaskade/konfig.py"
```

Die Ausgabe nennt den Konfigurationsordner und die bereits erkannten Ziele.
Zeige sie dem Nutzer, bevor du etwas änderst.

## Schritt 2 — Bedarf klären

Frage: **Sollen Arbeitsgänge nur lokal laufen, oder auch auf entfernten
Rechnern?**

Nur lokal → **fertig**. Ohne Konfiguration läuft alles lokal; es ist nichts
anzulegen. Sage das und beende.

Entfernt → frage je Zielsystem nach:

| | Beispiel |
|---|---|
| Kurzname, unter dem es angesprochen wird | `webserver` |
| Benutzer und Rechner | `admin@10.0.0.5` |
| Pfad zum privaten SSH-Schlüssel | `~/.ssh/id_ed25519` |
| Präfix für temporäre Dateien (optional) | `/tmp/ia-` — Vorgabe |

Frage nie nach einem Passwort. Dieses Plugin verwendet ausschließlich
SSH-Schlüssel; ein Ziel ohne Schlüssel wird nicht angefasst.

## Schritt 3 — Schreiben

Lege `<konfigordner>/ziele.json` an. Den Ordner nennt Schritt 1.

```json
{
  "webserver": {
    "ssh":  "admin@10.0.0.5",
    "keys": ["~/.ssh/id_ed25519"],
    "temp": "/tmp/ia-"
  }
}
```

Regeln beim Schreiben:

- Relative Schlüsselpfade werden gegen die Projektwurzel aufgelöst, absolute
  unverändert genommen.
- Unter Windows Vorwärtsschrägstriche verwenden (`C:/Users/...`). Ein einfacher
  Backslash ist in JSON ein ungültiger Escape.
- Mehrere Schlüssel je Ziel sind erlaubt; der erste existierende gewinnt.
- `lokal` ist eingebaut und darf nicht überschrieben werden.
- Eine vorhandene `ziele.json` nicht ersetzen — vorhandene Ziele beibehalten und
  das neue ergänzen.

## Schritt 4 — Abnehmen

Drei Prüfungen, alle drei zeigen:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/kaskade/konfig.py"
```
→ jedes Ziel gelistet, je Ziel `schluessel=gefunden`. Steht dort `FEHLT`, ist der
Pfad falsch oder die Datei nicht vorhanden.

```
python "${CLAUDE_PLUGIN_ROOT}/skills/kaskade/pruefstand.py"
```
→ `STATUS: GRUEN`, 0 durchgefallen.

```
python "${CLAUDE_PLUGIN_ROOT}/skills/kaskade/pruefstand.py" --rot
```
→ `STATUS: ESKALATION`, Exit 1. Dieser Lauf **muss** fehlschlagen.

Meldet eine der drei Prüfungen etwas anderes, ist die Einrichtung nicht fertig —
sage das klar, statt es zu beschönigen.

## Schritt 5 — Hinweisen

Sage dem Nutzer zum Schluss in zwei Sätzen:

- Die Konfiguration liegt im Projekt und gehört nicht in ein öffentliches
  Repository. Das mitgelieferte `.gitignore` schließt `ziele.json` bereits aus.
- Weitere Ziele jederzeit über diesen Skill oder durch Bearbeiten der Datei.
