# Warum es diesen Skill gibt

`SKILL.md` sagt, **wie** delegiert wird. Hier steht, **warum**.

---

## Die Rechnung dahinter

Der Tokenverbrauch einer Sitzung ist **Kontextgröße × Turnzahl**. Der größte
Posten ist nicht das, was neu geschrieben wird, sondern das Wiedereinlesen des
bestehenden Kontexts bei jedem Turn.

Ein Subagent bekommt einen eigenen, leeren Kontext; nur sein Abschlussbericht
kommt zurück. Das senkt beide Faktoren zugleich — und zwar umso stärker, je
länger die Sitzung schon läuft.

Wer das nachrechnen will: Die Nutzungsstatistik der eigenen Sitzungen zeigt den
Anteil `cache_read` an der Gesamtlast. Er ist regelmäßig der weitaus größte.

---

## Der Zuschnitt

Ein Auftrag an ein ausführendes Modell braucht vier Teile — **Kontext · Objekt ·
Weg · Abnahme.** Der Unterschied zwischen „koch eine Suppe" und „schneide dieses
Gemüse mit diesem Messer in diese Stücke".

Das deckt sich mit Anthropics Befund aus dem Multi-Agent-Bau: Jeder Subagent
braucht Ziel, Ausgabeformat, Werkzeug-/Quellenhinweis und klare
Aufgabengrenzen. Kurze Aufträge wie „recherchiere den Halbleitermangel" führten
dort dazu, dass Agenten die Aufgabe missverstanden oder dieselbe Arbeit doppelt
machten.

---

## Warum keine zweite Delegationsrunde

Bei `STATUS: ESKALATION` führt das planende Modell den Arbeitsgang selbst aus.
Keine zweite Runde, keine Iterationsverwaltung.

Eine Schleife verwaltet sich selbst und verbraucht dabei genau die Turns, die
die Delegation sparen sollte. Wenn ein Arbeitsgang beim ersten Versuch nicht
abgenommen wird, fehlt in aller Regel etwas im Auftrag — und das repariert kein
zweiter Durchlauf desselben Auftrags.

---

## Warum offene Aufträge verboten sind

Formulierungen wie „widerlege das" oder „such nach Fehlannahmen" haben
Subagenten schon dazu gebracht, Schlüsselspeicher zu sondieren und
Sicherheitsklassifizierer auszulösen.

**Nicht die Rechte waren das Problem, sondern die Offenheit des Auftrags.** Ein
ausführendes Modell darf mit vollen Rechten arbeiten — es darf nur nichts tun,
was nicht im Auftrag steht, und muss bei fehlender Angabe abbrechen statt zu
improvisieren.

---

## Die vier dokumentierten Fehlermuster

Aus `anthropics/claude-code#40339`:

| Fehlermuster | Gegenmittel hier |
|---|---|
| **Schlechtes Scoping** — vage Anweisung ohne Pfade und Zeilenbereiche | die vier Teile des Zuschnitts |
| **Fehlender Kontext** — der Subagent startet mit leerem Fenster | „Kontext" ist Pflicht, nicht Kür |
| **Keine Ergebnisprüfung** — das Hauptmodell übernimmt Behauptungen ungeprüft | `abnahme.py`, vor der Delegation geschrieben |
| **Vorgetäuschte Gründlichkeit** — der Subagent schließt aus Dateinamen statt aus Inhalt | Belegpflicht im Ausführer-Prompt plus maschineller Vergleich |

Das vierte ist der Grund, warum der Zähler kein Beiwerk ist: **Eine Behauptung
lässt sich nicht widerlegen, ein Prüfbefehl schon.**

---

## Warum der Ausführer nicht selbst aufräumt

Seine Arbeitsdateien müssen stehen bleiben, bis die Abnahme gelaufen ist —
sonst kann niemand mehr prüfen, was er getan hat, und bei einem Fehlschlag
fehlt die Spur zur Ursache.

Aufräumen ist der letzte Schritt des Auftraggebers. Bei `ESKALATION` bleiben die
Dateien stehen, bis der Fall geklärt ist; der SessionEnd-Nachlauf holt sie nach
24 Stunden ohnehin.

---

## Warum `MSYS_NO_PATHCONV=1` bei Serverpfaden

Git Bash schreibt jedes Argument, das mit `/` beginnt, in einen Windows-Pfad um,
bevor Python es sieht — aus `/tmp/ia-x` wird `C:/Users/…/Temp/ia-x`.

Ohne Schutz sähe die Abweisung wie eine funktionierende Pfadschranke aus,
obwohl gar nichts registriert wurde. `journal.py` erkennt den Fall und meldet
`PFAD VERFAELSCHT` (Exit 3) statt still zu scheitern. Ausführlich in
[journal.md](journal.md).

---

## Warum „eine Datei je `rm`"

Ein `rsync` oder `rm` mit Ziel `/` hat auf produktiven Servern schon das
Netzwerk zerstört und die Maschine unerreichbar gemacht. Die Schranke schließt
diesen Fall nicht durch Vorsicht aus, sondern durch Bauart: Es gibt keinen
Codepfad, der mehr als eine Datei je Befehl löschen kann.

---

## Was nie delegiert wird — und warum

| | Grund |
|---|---|
| Diagnose und Ursachensuche | das ist die Planstufe; ein Ausführer ohne Kontext rät |
| alles ohne formulierbaren Prüfbefehl | ohne Abnahme ist die Delegation ein Vertrauensvorschuss |
| Gedächtnis- und Notizarbeit | kleine Modelle schweifen ab und erfinden trotz gegenteiliger Anweisung |
| Entscheidungen, die dem Auftraggeber gehören | er muss sie treffen, nicht nachträglich billigen |
| offene Prüfaufträge | siehe oben |
