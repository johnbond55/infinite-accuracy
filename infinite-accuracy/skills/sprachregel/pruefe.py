#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefe.py — Text gegen die Sprachregeln pruefen.

Stufe A ist ein Fund und wird beseitigt, Stufe B ist ein Hinweis und zaehlt
gegen die Schwelle. Ausgenommene Zonen — Codeblock, Zitatzeile, Kopfblock,
Verweisziel, Tabellenzelle — erkennt das Werkzeug selbst.

Aufrufe:
    pruefe.py <datei> [...]        Funde je Zeile, Zaehlwerk, Urteil
    pruefe.py --liste              Regelkatalog mit allen Woertern
    pruefe.py --json <datei> [...] Funde als JSON
Optionen:
    --schwelle N   erlaubte Hinweise der Stufe B je Datei, Vorgabe 10
    --alles        auch die ausgenommenen Zonen pruefen
Exit: 0 bestanden · 1 Fund der Stufe A oder mehr Hinweise als die Schwelle
      · 2 Aufruffehler

Kein stdin: das Werkzeug liest Dateien.
Begruendungen und Fallen: ../kaskade/doku/sprachregel.md
"""
import argparse
import json
import os
import re
import sys

SATZ_MAX_WOERTER = 25
SCHWELLE_VORGABE = 10
STRICH_JE_ABSATZ = 1

WORTREGELN = (
    ("A1", "A", "Hoeflichkeits- oder Chatbot-Floskel", "streichen",
     ("ich hoffe das hilft", "hoffe das hilft", "ich hoffe das passt",
      "gute frage", "sehr gute frage", "spannende frage", "berechtigte frage",
      "lass mich wissen", "lassen sie mich wissen", "sag bescheid",
      "sag mir bescheid", "melde dich gerne", "gerne helfe ich",
      "wie kann ich dir helfen", "ich stehe zur verfuegung",
      "ich stehe zur verfügung", "viel erfolg", "viel spass dabei",
      "viel spaß dabei", "ich freue mich", "keine sorge", "kein problem")),

    ("A2", "A", "Metagerede ueber die eigene Arbeit", "Ergebnis nennen",
     ("zunaechst einmal", "zunächst einmal", "im folgenden",
      "im weiteren verlauf", "wie eingangs erwaehnt", "wie eingangs erwähnt",
      "wie bereits erwaehnt", "wie bereits erwähnt", "wie bereits gesagt",
      "wie oben bereits", "lass uns", "lassen sie uns", "schauen wir uns",
      "werfen wir einen blick", "ich werde nun", "ich werde jetzt",
      "als naechstes werde ich", "als nächstes werde ich",
      "bevor ich beginne", "kurz zur einordnung", "vorab kurz")),

    ("A3", "A", "Werbewort ohne Messung", "messen oder streichen",
     ("nahtlos", "robust", "leistungsstark", "leistungsfaehig",
      "leistungsfähig", "umfassend", "ganzheitlich", "innovativ",
      "hochmodern", "modernste", "intuitiv", "benutzerfreundlich", "muehelos",
      "mühelos", "revolutionaer", "revolutionär", "bahnbrechend",
      "state of the art", "best practice", "next level", "massgeschneidert",
      "maßgeschneidert", "zukunftssicher", "wegweisend", "erstklassig",
      "hochwertig", "spielend leicht", "im handumdrehen", "kinderleicht",
      "beeindruckend", "perfekt abgestimmt")),

    ("A4", "A", "Wichtigkeitsbehauptung ohne Folge", "die Folge nennen",
     ("es ist wichtig", "wichtig zu beachten", "es sei angemerkt",
      "es sollte beachtet werden", "von zentraler bedeutung",
      "von grosser bedeutung", "von großer bedeutung", "essenziell",
      "essentiell", "unerlaesslich", "unerlässlich", "unverzichtbar",
      "spielt eine wichtige rolle", "nicht zu unterschaetzen",
      "nicht zu unterschätzen", "ein meilenstein", "game changer",
      "game-changer", "nicht von der hand zu weisen")),

    ("A5", "A", "Fuellwort oder Weichmacher", "streichen",
     ("eigentlich", "im grunde", "im prinzip", "grundsaetzlich",
      "grundsätzlich", "durchaus", "quasi", "gewissermassen",
      "gewissermaßen", "sozusagen", "letztendlich", "letztlich",
      "im endeffekt", "in der tat", "sicherlich", "zweifellos", "bekanntlich",
      "selbstredend", "nun ja", "ein stueck weit", "ein stück weit",
      "im wesentlichen", "mehr oder weniger", "schlichtweg", "regelrecht",
      "selbstverstaendlich", "selbstverständlich")),

    ("A6", "A", "Schlussfloskel", "Ende ohne Zusammenfassung",
     ("zusammenfassend", "zusammengefasst", "abschliessend laesst sich",
      "abschließend lässt sich", "abschliessend bleibt",
      "abschließend bleibt", "unterm strich", "alles in allem",
      "insgesamt betrachtet", "wie man sieht", "das war's", "das wars",
      "kurzum", "am ende des tages", "im grossen und ganzen",
      "im großen und ganzen", "auf den punkt gebracht", "fazit")),
)

MUSTERREGELN = (
    ("A7", "A", "Ankuendigung statt Aussage", "die Sache selbst zeigen",
     r"(?<!\w)(hier (ist|sind|kommt|folgt|folgen)(?!\w)"
     r"|(ich zeige|zeige ich)( dir| ihnen)(?!\w)"
     r"|ich (werde|wuerde|würde)( dir| ihnen)?( jetzt| nun| kurz)?"
     r" (zeigen|erklaeren|erklären|erlaeutern|erläutern|darstellen)(?!\w))"),

    ("A8", "A", "Bericht ueber den eigenen Weg", "Ergebnis und Beweis nennen",
     r"(?<!\w)(ich habe|habe ich)( mir)?[^.;]{0,50}"
     r"(angeschaut|angesehen|geprueft und festgestellt|geprüft und festgestellt)(?!\w)"),

    ("B1", "B", "Substantivierung mit Hilfsverb", "das Verb nehmen",
     r"(?<!\w)(\w{4,}ung (erfolgt|erfolgen|erfolgte)"
     r"|(eine|die|zur|zum) \w{4,}ung (durchfuehren|durchführen|durchgefuehrt"
     r"|durchgeführt|vornehmen|vorgenommen))(?!\w)"),

    ("B3", "B", "Absolutwort als Verstaerker", "Geltungsbereich benennen",
     r"(?<!\w)(ausnahmslos|jederzeit|ohne ausnahme|in jedem fall"
     r"|saemtliche|sämtliche|voellig|völlig)(?!\w)"),

    ("B4", "B", "Ding handelt wie ein Mensch", "den Handelnden benennen",
     r"(?<!\w)(das system|die software|die anwendung|der code|die datei"
     r"|die loesung|die lösung|die aenderung|die änderung|das werkzeug)"
     r" (entscheidet|denkt|weiss|weiß|will|glaubt|versteht|beschliesst"
     r"|beschließt|kuemmert|kümmert|sorgt|wuenscht|wünscht)(?!\w)"),

    ("B8", "B", "Binaerkontrast", "die Aussage direkt setzen",
     r"(?<!\w)nicht [^.;:]{2,60}, sondern(?!\w)"),

    ("B10", "B", "Emoji oder Schmuckzeichen", "streichen",
     u"[\U0001F300-\U0001FAFF☀-➿️]"),

    ("B11", "B", "Fettung eines ganzen Satzes", "nur Begriff oder Urteil fetten",
     r"\*\*[^*]{80,}\*\*"),

    ("B12", "B", "Wortdopplung", "ein Wort streichen",
     r"(?<!\w)(\w{3,}) \1(?!\w)"),
)

MESSREGELN = (
    ("B2", "B", "Passiv ohne Handelnden", "den Handelnden benennen"),
    ("B5", "B", "Satz laenger als %d Woerter" % SATZ_MAX_WOERTER, "teilen"),
    ("B6", "B", "mehr als %d Gedankenstrich je Absatz" % STRICH_JE_ABSATZ,
     "Komma oder Punkt"),
    ("B7", "B", "drei Saetze mit gleichem Anfang", "Satzbau wechseln"),
    ("B9", "B", "rhetorische Frage als Aufhaenger", "die Aussage setzen"),
)

PASSIV = re.compile(r"(?<!\w)(wird|wurde|wurden|werden)(?!\w)[^.;]{0,60}"
                    r"(?<!\w)ge\w{3,}(t|en)(?!\w)", re.IGNORECASE)
HANDELNDER = re.compile(r"(?<!\w)(von|durch)(?!\w)", re.IGNORECASE)
FRAGEWORT = re.compile(r"^(was|warum|wieso|weshalb|wie)(?!\w)", re.IGNORECASE)
STRICH = re.compile(u"—|\\s–\\s")
SATZENDE = re.compile(r"(?<=[.!?])\s+")
HAENGT_AN = re.compile(r"(?:(?<!\w)\w\.|(?<!\w)z\.\s?B\.|(?<!\w)bzw\."
                       r"|(?<!\w)ggf\.|(?<!\w)ca\.|(?<!\w)Nr\.|(?<!\w)Abs\."
                       r"|\d\.)$")
LISTENZEICHEN = re.compile(r"^\s*([-*+]|\d+\.)\s+")


def _wortmuster(begriff):
    """Begriff als Regex mit Wortgrenzen; Leerzeichen dulden auch ein Komma."""
    teile = [re.escape(w) for w in begriff.split()]
    return r"(?<!\w)" + r"[\s,]+".join(teile) + r"(?!\w)"


def katalog():
    """Liste von (id, stufe, was, rat, muster-oder-None) in Katalogreihenfolge."""
    raus = []
    for rid, stufe, was, rat, begriffe in WORTREGELN:
        muster = "|".join(_wortmuster(b) for b in begriffe)
        raus.append((rid, stufe, was, rat, re.compile(muster, re.IGNORECASE)))
    for rid, stufe, was, rat, muster in MUSTERREGELN:
        raus.append((rid, stufe, was, rat, re.compile(muster, re.IGNORECASE)))
    for rid, stufe, was, rat in MESSREGELN:
        raus.append((rid, stufe, was, rat, None))
    return sorted(raus, key=lambda r: (r[0][0], int(r[0][1:])))


def _maskieren(zeile):
    """Inline-Code, Verweisziele und Adressen durch Leerzeichen ersetzen."""
    def leer(m):
        return " " * (m.end() - m.start())
    z = re.sub(r"`[^`]*`", leer, zeile)
    z = re.sub(r"\]\([^)]*\)", leer, z)
    z = re.sub(r"<[^ >]+>", leer, z)
    z = re.sub(r"https?://\S+", leer, z)
    return z


def zonen(zeilen):
    """Je Zeile die Marken code, kopf, zitat, tabelle."""
    raus = []
    in_code = False
    in_kopf = False
    for i, roh in enumerate(zeilen):
        s = roh.strip()
        marken = set()
        if i == 0 and s == "---":
            in_kopf = True
            raus.append({"kopf"})
            continue
        if in_kopf:
            if s == "---":
                in_kopf = False
            raus.append({"kopf"})
            continue
        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            raus.append({"code"})
            continue
        if in_code:
            marken.add("code")
        if s.startswith(">"):
            marken.add("zitat")
        if s.startswith("|") and s.endswith("|"):
            marken.add("tabelle")
        raus.append(marken)
    return raus


def _saetze(text):
    """Text in Saetze zerlegen; Abkuerzungen beenden keinen Satz."""
    raus = []
    for teil in SATZENDE.split(text):
        if raus and HAENGT_AN.search(raus[-1]):
            raus[-1] = raus[-1] + " " + teil
        else:
            raus.append(teil)
    return [s for s in (t.strip() for t in raus) if s]


def _absaetze(zeilen, marken, alles):
    """Liste von Absaetzen, je Absatz [(zeilennummer, maskierter text)].

    Jeder Aufzaehlungspunkt ist ein eigener Absatz.
    """
    raus = []
    puffer = []
    for i, roh in enumerate(zeilen):
        s = roh.strip()
        gesperrt = bool(marken[i] & {"code", "kopf", "zitat", "tabelle"})
        if not s or s.startswith("#") or (gesperrt and not alles):
            if puffer:
                raus.append(puffer)
                puffer = []
            continue
        if LISTENZEICHEN.match(roh) and puffer:
            raus.append(puffer)
            puffer = []
        puffer.append((i + 1, _maskieren(roh)))
    if puffer:
        raus.append(puffer)
    return raus


def _fuegen(absatz):
    """(text, grenzen) — grenzen ist [(offset, zeilennummer)]."""
    text = ""
    grenzen = []
    for nr, roh in absatz:
        s = LISTENZEICHEN.sub("", roh).strip()
        if not s:
            continue
        if text:
            text += " "
        grenzen.append((len(text), nr))
        text += s
    return text, grenzen


def _zeile_fuer(grenzen, pos):
    nr = grenzen[0][1] if grenzen else 1
    for start, n in grenzen:
        if start <= pos:
            nr = n
        else:
            break
    return nr


def _fund(datei, zeile, rid, stufe, was, rat, text):
    return {"datei": datei, "zeile": zeile, "id": rid, "stufe": stufe,
            "was": was, "rat": rat, "fund": text.strip()[:60]}


def _messfunde(datei, absaetze):
    raus = []
    for absatz in absaetze:
        text, grenzen = _fuegen(absatz)
        if not text:
            continue
        erste = grenzen[0][1]
        striche = len(STRICH.findall(text))
        if striche > STRICH_JE_ABSATZ:
            raus.append(_fund(datei, erste, "B6", "B",
                              "mehr als %d Gedankenstrich je Absatz" % STRICH_JE_ABSATZ,
                              "Komma oder Punkt", "%d Striche" % striche))
        saetze = _saetze(text)
        zeiger = 0
        anfaenge = []
        for satz in saetze:
            pos = text.find(satz, zeiger)
            if pos < 0:
                pos = zeiger
            zeiger = pos + len(satz)
            nr = _zeile_fuer(grenzen, pos)
            woerter = satz.split()
            if len(woerter) > SATZ_MAX_WOERTER:
                raus.append(_fund(datei, nr, "B5", "B",
                                  "Satz laenger als %d Woerter" % SATZ_MAX_WOERTER,
                                  "teilen", "%d Woerter: %s" % (len(woerter), satz)))
            if PASSIV.search(satz) and not HANDELNDER.search(satz):
                raus.append(_fund(datei, nr, "B2", "B", "Passiv ohne Handelnden",
                                  "den Handelnden benennen", satz))
            anfaenge.append((nr, " ".join(w.lower() for w in woerter[:2])))
        for i in range(2, len(anfaenge)):
            drei = {anfaenge[i - 2][1], anfaenge[i - 1][1], anfaenge[i][1]}
            if len(drei) == 1 and anfaenge[i][1]:
                raus.append(_fund(datei, anfaenge[i][0], "B7", "B",
                                  "drei Saetze mit gleichem Anfang",
                                  "Satzbau wechseln", anfaenge[i][1]))
        if len(saetze) > 2 and saetze[0].endswith("?") and FRAGEWORT.match(saetze[0]):
            raus.append(_fund(datei, erste, "B9", "B",
                              "rhetorische Frage als Aufhaenger",
                              "die Aussage setzen", saetze[0]))
    return raus


def pruefen(datei, text, alles=False):
    """Alle Funde einer Datei, nach Zeile und Regel sortiert."""
    zeilen = text.splitlines()
    marken = zonen(zeilen)
    regeln = [r for r in katalog() if r[4] is not None]
    raus = []
    for i, roh in enumerate(zeilen):
        if not alles and (marken[i] & {"code", "kopf", "zitat"}):
            continue
        zeile = _maskieren(roh)
        for rid, stufe, was, rat, muster in regeln:
            for treffer in muster.finditer(zeile):
                raus.append(_fund(datei, i + 1, rid, stufe, was, rat,
                                  treffer.group(0)))
    raus.extend(_messfunde(datei, _absaetze(zeilen, marken, alles)))
    return sorted(raus, key=lambda f: (f["zeile"], f["id"]))


def lesen(pfad):
    with open(pfad, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def liste_drucken(schreiben):
    schreiben("Regelkatalog — Stufe A wird beseitigt, Stufe B zaehlt gegen die Schwelle")
    begriffe = {rid: b for rid, _s, _w, _r, b in WORTREGELN}
    for rid, stufe, was, rat, muster in katalog():
        schreiben("")
        schreiben("%-4s %s  %s -> %s" % (rid, stufe, was, rat))
        if rid in begriffe:
            schreiben("     " + " · ".join(begriffe[rid]))
        elif muster is None:
            schreiben("     gemessen, kein Wortlaut")
        else:
            schreiben("     Muster: " + muster.pattern.replace("\n", " "))


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dateien", nargs="*")
    p.add_argument("--liste", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--alles", action="store_true")
    p.add_argument("--schwelle", type=int, default=SCHWELLE_VORGABE)
    a = p.parse_args()

    strom = sys.stdout
    if hasattr(strom, "reconfigure"):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                          # noqa: BLE001
            pass

    def sag(text=""):
        strom.write(text + "\n")

    if a.liste:
        liste_drucken(sag)
        return 0
    if not a.dateien:
        sag("Kein Dateiname. Aufruf: pruefe.py <datei> [...] oder --liste")
        return 2

    alle = []
    rot = False
    for pfad in a.dateien:
        if not os.path.isfile(pfad):
            sag("%s: nicht lesbar" % pfad)
            rot = True
            continue
        funde = pruefen(pfad, lesen(pfad), a.alles)
        alle.extend(funde)
        zahl_a = sum(1 for f in funde if f["stufe"] == "A")
        zahl_b = len(funde) - zahl_a
        if not a.json:
            for f in funde:
                sag("%s:%d  [%s] %s: %s -> %s"
                    % (f["datei"], f["zeile"], f["id"], f["was"], f["fund"], f["rat"]))
            sag("%s: %d Fund(e) Stufe A, %d Hinweis(e) Stufe B (Schwelle %d)"
                % (pfad, zahl_a, zahl_b, a.schwelle))
        if zahl_a > 0 or zahl_b > a.schwelle:
            rot = True

    if a.json:
        sag(json.dumps({"funde": alle, "schwelle": a.schwelle,
                        "urteil": "ROT" if rot else "GRUEN"},
                       ensure_ascii=False, indent=2))
    else:
        sag("STATUS: %s" % ("ROT" if rot else "GRUEN"))
    return 1 if rot else 0


if __name__ == "__main__":
    sys.exit(main())
