# journal.py — warum es so gebaut ist

Der Code in `journal.py` sagt, **was** geschieht. Hier steht, **warum** — und
was passiert, wenn man es anders macht. Wer eine Zeile dort ändert, liest
vorher den zugehörigen Abschnitt hier.

---

## Der Grundsatz

**Ein `rm` wird nicht gesucht, sondern beim Erzeugen registriert.**

Wer eine temporäre Arbeitsdatei anlegt, trägt sie sofort ein; aufgeräumt wird
später genau diese Liste — kein Glob, kein `find`, kein Muster. Damit hat jedes
`rm` einen bekannten Ursprung.

Der Gegenentwurf wäre ein Aufräumer, der nach Mustern sucht („alles unter
`/tmp/ia-*` älter als ein Tag"). Der ist bequemer und genau deshalb gefährlich:
Er löscht, was zufällig auf ein Muster passt, und niemand kann hinterher sagen,
warum eine bestimmte Datei weg ist. Ein `rsync`/`rm` mit Ziel `/` hat auf einem
produktiven Server schon das Netzwerk zerstört und ihn unerreichbar gemacht.

---

## Die vier Schranken

Sie trennen „temporär" von „fertig", und zwar beweisbar statt behauptet.

| | Schranke | Wo | Was sie verhindert |
|---|---|---|---|
| 1 | **Pfadschranke** | `pfad_erlaubt()`, beim Eintragen | Fertige Programmdateien können gar nicht erst ins Journal geraten. `/opt/dienst/programm.py` wird abgewiesen. |
| 2 | **Metazeichenschranke** | `_hat_metazeichen()`, beim Eintragen | Kein Zeichen, das eine Shell deutet. |
| 3 | **Eine Datei je `rm`** | `_loeschen_einzeln()` | Kein `-r`, kein Sternchen. Muss ein Verzeichnis weg, steht jede Datei einzeln drin. |
| 4 | **Nur-Journal-Löschung** | `aufraeumen()` | Gelöscht wird ausschließlich, was im Journal steht. |

Schranke 2 und das `shlex.quote()` in Schranke 3 gehören zusammen: **Ohne beide
wäre „kein Sternchen" nur behauptet.** Grund steht unten.

---

## `META_SERVER` / `META_LOKAL` / `_hat_metazeichen()`

**Zwei Listen, weil die Ziele verschieden gefährlich sind.**

Ein Serverpfad geht über `ssh` an eine **entfernte Shell** — `ssh` shellt sein
letztes Argument immer. Dort machte ein Sternchen aus „eine Datei je `rm`" ein
Glob-Löschen, und ein Semikolon hängte einen zweiten Befehl an. Eingetragen wird
vom ausführenden Modell, also von genau der Quelle, der dieser Skill laut
eigener Begründung nicht traut.

Lokale Pfade brauchen eine andere Liste: Dort löscht `os.remove()` ohne jede
Shell, dafür sind Leerzeichen, Backslash und Doppelpunkt in Windows-Pfaden
völlig normal. Abgewiesen werden lokal nur die Glob-Zeichen — ein Eintrag mit
`*` ist dort keine Gefahr, aber immer ein Irrtum: Gelöscht würde die Datei, die
wörtlich so heißt, und der Eintragende meinte etwas anderes.

**Falle beim Ändern:** Backslash, Doppelpunkt und Leerzeichen dürfen nie in
`META_LOKAL` wandern — damit wäre auf Windows jeder zweite Pfad unbrauchbar.

*Nachträglich behoben: Vorher bestand `/tmp/ia-42-*` beide Prüfungen und wurde
auf dem Server expandiert — das widersprach der eigenen Zusage wörtlich.*

---

## `pfad_erlaubt()`

Vier Abweisungsgründe, in dieser Reihenfolge:

1. **`..` im Pfad** — sonst klettert man aus dem Temp-Ort heraus.
2. **Shell-Metazeichen** — siehe oben.
3. **Serverpfad nicht absolut** — Serverpfade beginnen mit `/`.
4. **Nicht unter einem erlaubten Präfix.**

**Die Verzeichnisgrenze bei Punkt 4 (`p + os.sep`) ist kein Schönheitsfehler.**
Ohne den angehängten Trenner passierte neben dem Scratchpad `…\Temp\claude` auch
der Nachbarordner `…\Temp\claude-alt` die Schranke, weil `startswith` nur
Zeichen vergleicht und keine Pfadebenen kennt.

Serverpfade werden bewusst **ohne** Verzeichnisgrenze geprüft: `/tmp/ia-` ist
dort ein Namenspräfix, kein Verzeichnis. Alle Dateien, die so beginnen, sind
gemeint.

*Verzeichnisgrenze nachträglich ergänzt.*

---

## `erlaubte_praefixe()`

`tempfile.gettempdir()` statt `~/AppData/Local/Temp`: Es liest `TMPDIR`, `TEMP`
und `TMP` und fällt plattformgerecht zurück. Der alte Rückfall war reines
Windows — auf Linux/macOS ist `TEMP` meist ungesetzt, und die Pfadschranke
zeigte dann auf ein Verzeichnis, das es gar nicht gibt.

Gemessen: `CLAUDE_SCRATCHPAD` ist nicht überall gesetzt — der Rückfall ist der
Regelfall, nicht die Ausnahme.

Der zweite erlaubte Ort, `<konfigordner>/temp`, ist
plattformneutral und funktioniert immer.

---

## `msys_verdacht()`

Git Bash (MSYS2) wandelt jedes Argument, das mit `/` beginnt, in einen
Windows-Pfad um, **bevor Python es sieht**: aus `/tmp/ia-x` wird
`C:/Users/…/Temp/ia-x`, aus `/opt/y` wird `C:/Program Files/Git/opt/y`.

Ohne diese Erkennung könnte der Ausführer seine Serverdateien nicht
registrieren — und die Abweisung sähe aus wie eine funktionierende
Pfadschranke. Deshalb ein eigener Exit-Code (3) und eine eigene Meldung:
`PFAD VERFAELSCHT`.

Abhilfe im Aufruf: `MSYS_NO_PATHCONV=1` voranstellen.

*Beim ersten Laufversuch gemessen.*

---

## Eigene Meldungen statt einer gemeinsamen

`eintragen()` hat drei verschiedene Abweisungsmeldungen: Metazeichen,
`PFAD VERFAELSCHT`, Pfadschranke. Das ist Absicht.

**Wer eine Abweisung falsch deutet, sucht den Fehler am falschen Ende.** Beim
MSYS-Fall sah die Abweisung aus wie eine funktionierende Pfadschranke, obwohl
gar nichts registriert wurde. Dieselbe Verwechslungsgefahr besteht zwischen
„liegt nicht im Temp-Ort" und „enthält ein Sternchen" — die Abhilfe ist jeweils
eine völlig andere.

---

## `_loeschen_einzeln()` — `shlex.quote()`

Die **zweite** Sicherung hinter der Metazeichenschranke. `ssh` reicht sein
letztes Argument immer an eine entfernte Shell weiter, und das Journal ist eine
Textdatei — wer sie von Hand ändert, umgeht die erste Sicherung.

**Eine Zusage wie „kein Sternchen" darf nicht an einer einzigen Prüfung
hängen.**

Was gebaut wird:

```
/tmp/ia-42-modul.py          ->  rm -f -- /tmp/ia-42-modul.py
/tmp/ia-42-*                 ->  rm -f -- '/tmp/ia-42-*'
/tmp/ia-x;rm /etc/passwd     ->  rm -f -- '/tmp/ia-x;rm /etc/passwd'
```

`-f` schluckt „war schon weg" — ein Aufräumer, der über eine bereits gelöschte
Datei stolpert, ist unbrauchbar.

Verzeichnisse werden nie gelöscht, auch lokal nicht (`os.path.isdir` → Abbruch).

*`shlex.quote()` nachträglich ergänzt.*

---

## `aufraeumen()` — die Sieben-Tage-Regel

Abgehakte Einträge älter als sieben Tage fallen ganz aus dem Journal. Ohne das
wüchse die Datei unbegrenzt, und der Sinn des Journals — auf einen Blick sehen,
was offen ist — ginge verloren.

Abgehakt heißt: Feld `weg` gesetzt. Ein fehlgeschlagener Löschversuch bleibt
offen stehen und wird beim nächsten Lauf erneut versucht.

---

## `projekt_wurzel()`

Steigt vom Skript aus aufwärts und sucht einen Ordner mit `.claude` darin.
**Niemals `cd`** — ein `cd` verschiebt das Arbeitsverzeichnis der ganzen
Sitzung, die Hooks stehen mit relativem Pfad in `settings.json` und sind danach
unauffindbar. Das führt zu einer Selbstaussperrung, aus der heraus sich auch
nichts mehr zurückstellen lässt.

**Bekannte Schwäche:** Bei Installation als Benutzer-Skill
(`~/.claude/skills/…`) ist der erste Treffer das Home-Verzeichnis; Journal und
Temp-Schranke hängen dann am Heimatordner statt am Projekt. Für die Ablage als
Projekt-Skill ist das Verhalten richtig. Eine Umstellung auf
`CLAUDE_PROJECT_DIR` wäre der saubere Weg.

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| Metazeichenschranke lockern | Glob-Löschen auf dem Server, entgegen der eigenen Zusage |
| `shlex.quote()` entfernen | dasselbe, sobald jemand das Journal von Hand bearbeitet |
| `p + os.sep` zu `p` vereinfachen | Nachbarordner mit gleichem Namenspräfix werden löschbar |
| Zielnamen ändern | drei Stellen: `ZIELE`, `argparse choices`, die feste Liste in `eintragen()` |
| `-f` aus dem `rm` nehmen | jeder Lauf über eine bereits gelöschte Datei meldet einen Fehler |
