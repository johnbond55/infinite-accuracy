# Verdichtung — warum sie so gesteuert wird

Hält den Arbeitsfaden endlos: Claude Code verdichtet von selbst,
infinite-accuracy bestimmt, was dabei erhalten bleibt, und legt Früheres so ab,
dass es nachgeschlagen statt erinnert wird.

---

## Der Ablauf

| Schritt | Wer | Was |
|---|---|---|
| 1 | `regelschub.py` (UserPromptSubmit) | ab `ablage_schwelle_token` am Userhalt die Ablage anfordern — Zettelkasten und Destillat |
| 2 | Claude Code | bei erreichtem `autoCompactWindow` (abzüglich Reserve) die Verdichtung starten |
| 3 | `ernte.py` (PreCompact) | Riegel prüfen, Rohprotokoll ernten, Anweisung mit Kennmarke ausgeben |
| 4 | Claude Code | Zusammenfassung schreiben; jüngste Wechsel und bis zu fünf zuletzt gelesene Dateien bleiben |
| 5 | `wiedervorlage.py` (SessionStart `compact`) | Kennmarke prüfen, Regeln, Destillat dieser Sitzung und Karte vorlegen |
| 6 | `regelschub.py` | beim nächsten Prompt: Auftrag wieder scharf, Kennmarke nachprüfen, falls noch offen |

---

## Worauf das beruht

Die Doku von Claude Code beschreibt `PreCompact` nur als Ereignis. Was der Hook
bewirken kann, steht im Programm (gelesen in Claude Code 2.1.270):

| Beobachtung | Folge hier |
|---|---|
| Die Standardausgabe aller erfolgreichen PreCompact-Hooks wird zu `newCustomInstructions` und mit der Anweisung des Nutzers vereint — bei automatischer wie manueller Verdichtung | die Anweisung aus `ernte.py` |
| Exit 2 blockiert die Verdichtung (`blockedBy`), stderr ist die Meldung | der Riegel |
| Die Eingabe enthält `trigger` (`auto`/`manual`) und `custom_instructions` | Riegel nur bei `auto` |
| `/autocompact [auto\|<tokens>]` — das Fenster zählt in Token und wird am Modellfenster gekappt | `autoCompactWindow: 250000` braucht ein 1-Million-Modell |
| Beim Einlesen eines Transkripts wird alles vor der letzten Verdichtungsmarke verworfen | Hintergrund für spätere Umbauten |

**Undokumentiert heißt: kann sich mit jedem Update ändern.** Deshalb die Kennmarke.

---

## Die Kennmarke

`ernte.py` erzeugt je Verdichtung `ia-<sitzung>-<zeitstempel>`, schreibt sie in
den Stand der Sitzung und verlangt, dass die Zusammenfassung mit ihr beginnt.
Danach sucht `wiedervorlage.py` die jüngste Zusammenfassung (`isCompactSummary`)
im Transkript:

| Ergebnis | Bedeutung |
|---|---|
| `ok` | Anweisung übernommen |
| `fehlt` | Warnung im Kontext: Claude Code hat die Anweisung nicht übernommen — Befund melden |
| `unpruefbar` | die Zusammenfassung stand beim Start noch nicht im Transkript; `regelschub.py` prüft beim nächsten Prompt nach |
| `ohne_marke` | der PreCompact-Hook lief nicht |

Eine Anweisung, deren Wirkung niemand prüft, ist eine Hoffnung.

---

## Der Riegel

Die automatische Verdichtung kann mitten in einem Arbeitsgang kommen, der
Ablage-Auftrag nur am Userhalt. Springt der Kontext ohne Userhalt über den
Auslöser, fiele Unabgelegtes weg. Der Riegel schiebt die Verdichtung auf, bis
das angeforderte Destillat geschrieben ist — höchstens bis `riegel_bis_token`.
Darüber gibt er frei, damit das Fenster nicht vollläuft.

Manuelle Verdichtung (`/compact`) geht immer durch: wer sie auslöst, will sie.

---

## Einstellungen

| Wo | Schlüssel | Wert |
|---|---|---|
| `.claude/settings.json` | `autoCompactEnabled` | `true` |
| `.claude/settings.json` | `autoCompactWindow` | `250000` |
| jede `settings.json` | `env.DISABLE_AUTO_COMPACT` | **nicht setzen** — er wird vor `autoCompactEnabled` geprüft |
| Modellwahl | Fable oder Opus | jeweils mit `[1m]`, sonst kappt das 200.000-Fenster |

Der Auslöser muss über Grundlast plus Reserve plus Arbeitsraum liegen. Gemessen
am 12.09.2026: Grundlast 80.000–115.000 Token, Reserve für die Zusammenfassung
rund 33.000. Mit `autoCompactWindow: 160000` blieben 12.000 Token Arbeitsraum —
die Sitzung verdichtete acht Mal in Folge bei 127.000–157.000 Token, je zwei bis
drei Minuten. Mit 250.000 löst sie bei rund 217.000 aus und steht danach bei rund
100.000.

Ohne Verdichtung wuchsen Sitzungen bis 1.000.000 Token; die automatische
Verdichtung dampfte sie dann auf 15.000–18.000 ein.

---

## Vorberechnete Verdichtung

Claude Code kann die Zusammenfassung im Hintergrund vorbereiten
(`precomputeCompactionEnabled`). Auch dieser Weg ruft den PreCompact-Hook auf,
unter Umständen früher und mehrfach. Folge: zusätzliche Rohprotokolle. Dass die
Kennmarke dabei aus einem früheren Aufruf stammt, meldet die Prüfung seit 2.0.1
nicht mehr als `fehlt` — sie vergleicht die Zeit der jüngsten Zusammenfassung
mit der Zeit der Kennmarke. Ist die Zusammenfassung älter, hat die Verdichtung
noch nicht stattgefunden: `unpruefbar`.

---

## Wann die Prüfung greift

`wiedervorlage.py` prüft die Kennmarke beim Sitzungsstart. Oft steht die
Zusammenfassung zu diesem Zeitpunkt noch gar nicht im Transkript — Claude Code
schreibt sie eine Minute später. Dann meldet der Start `unpruefbar`, und das ist
kein Befund.

Deshalb prüft `regelschub.py` bei jedem Prompt nach, solange die Marke kein
Urteil hat (`geprueft_marke` im Stand). Bis 2.0.0 hing diese Nachprüfung an
`verdichtet` aus `kontext_token()` — das schlägt nur an, solange nach der
Verdichtungsmarke noch keine Antwort steht. Nach dem ersten Turn war die Marke
damit dauerhaft ungeprüft, ohne dass jemand es merkte.

| Fall | Urteil |
|---|---|
| Marke steht in der Zusammenfassung | `ok` |
| keine Zusammenfassung im Transkript | `unpruefbar`, beim nächsten Prompt erneut |
| Zusammenfassung älter als die Kennmarke (Riegel hielt) | `unpruefbar` |
| Zusammenfassung jünger, Marke fehlt darin | `fehlt` — Johannes melden |
| keine Kennmarke hinterlegt | `ohne_marke` — der PreCompact-Hook lief nicht |

---

## Was beim Ändern schiefgehen kann

| Änderung | Folge |
|---|---|
| `autoCompactWindow` unter Grundlast + Reserve + Arbeitsraum | Verdichtungsschleife, Sitzung arbeitsunfähig |
| `DISABLE_AUTO_COMPACT` stehen lassen | keine Verdichtung, das Fenster läuft in die Sackgasse |
| Riegel ohne Obergrenze | das Fenster läuft voll |
| Riegel auch für `manual` | `/compact` scheint kaputt |
| Kennmarke weglassen | ein Update von Claude Code hebelt die Anweisung still aus |
| Anweisung auch bei SessionEnd ausgeben | Rauschen; sie gehört nur zu PreCompact |
| Ablage-Schwelle über dem Auslöser | die Verdichtung kommt vor dem Auftrag, der Riegel muss jedes Mal auffangen |
