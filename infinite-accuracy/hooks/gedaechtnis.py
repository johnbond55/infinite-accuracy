#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gedaechtnis.py — Zettelkasten-Mechanik fuer das Gedaechtnis.

Baut aus den Gedaechtnisdateien einen schlanken Kurzindex (MEMORY.md, wird
immer geladen) und ein ausfuehrliches Verzeichnis (REGISTER.md, nur auf
Zuruf). Prueft ausserdem auf Geheimnisse, tote Verweise und aufgeblaehte
Eintraege — es meldet nur, es aendert nichts am Inhalt.

MEMORY.md laedt Claude Code nur bis zur Ladegrenze (200 Zeilen, 25.000
Zeichen). Wird der Index laenger, stehen die nachrangigen Eintraege - nach
Regeln und Nutzerangaben die aeltesten - nur als Schlagwort darin; der Kopf
sagt, wie viele.

Begruendungen und Fallen: ../skills/kaskade/doku/gedaechtnis.md

Aufrufe:
    gedaechtnis.py              Bericht ueber alle Auffaelligkeiten
    gedaechtnis.py --register   MEMORY.md und REGISTER.md neu bauen
    gedaechtnis.py --kurz       eine Zeile fuer den Sitzungsstart
"""
import calendar
import json
import os
import re
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "skills", "kaskade")
for _p in (HIER, KASKADE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    import konfig
except Exception:                                                 # noqa: BLE001
    konfig = None

TEXTE_DATEI = "register-texte.json"

LADEGRENZE_ZEILEN = 200
LADEGRENZE_ZEICHEN = 25000
SCHLAGWORTZEILE_MAX = 200
VORRANG = ("feedback", "user")

TEXTE_VORGABE = {
    "kopfzeile": "# Gedächtnis — Schlagwort-Register",
    "vorspann": ("*Kurzindex. Ausführlich in `REGISTER.md`, Inhalt in der "
                 "jeweiligen Datei — **erst nachschlagen, dann vermuten**.*"),
    "register_kopfzeile": "# Register — ausführliches Verzeichnis des Gedächtnisses",
    "register_vorspann": ("*Wird NICHT automatisch geladen. Hier nachschlagen, "
                          "wenn der Kurzindex in `MEMORY.md` nicht reicht.*"),
    "gekuerzt": ("*Gekürzt auf die Ladegrenze: {kurz} von {gesamt} Einträgen "
                 "stehen nur als Schlagwort — Datei `<schlagwort>.md`, "
                 "Beschreibung in `REGISTER.md`.*"),
    "weggelassen": ("*{fehlt} Einträge fehlen hier ganz (nur in `REGISTER.md`) "
                    "— das Gedächtnis ausmisten.*"),
    "schlagworte": "Schlagworte:",
    "rubriken": {
        "feedback": "Wie ich arbeiten soll",
        "user": "Wer der Nutzer ist",
        "project": "Laufende Vorhaben",
        "reference": "Verweise",
        "?": "Sonstiges",
    },
}

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LINK = re.compile(r"\[\[([a-z0-9][a-z0-9-]{2,60})\]\]")

PLATZHALTER = re.compile(
    r"^\s*(?:"
    r"\{[^}]*\}"
    r"|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"
    r"|<[^>]*>"
    r"|%[A-Za-z_][A-Za-z0-9_]*%"
    r"|[xX*.•…-]{3,}"
    r"|(?:dein|deine|your|my|test)[_-]?[A-Za-z0-9_-]*"
    r"|changeme|change[_-]?me|redacted|platzhalter|placeholder|beispiel"
    r"|example|todo|tbd|geheim|s3cret"
    r")\s*$",
    re.IGNORECASE)


def _zahl(name, vorgabe):
    try:
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def texte():
    """Ueberschriften und Rubriken des Index."""
    gesetzt = dict(TEXTE_VORGABE)
    if konfig is not None:
        try:
            eigene = konfig.tabelle(TEXTE_DATEI, vorgabe={})
            for k, v in eigene.items():
                if k == "rubriken" and isinstance(v, dict):
                    rub = dict(TEXTE_VORGABE["rubriken"])
                    rub.update(v)
                    gesetzt["rubriken"] = rub
                elif isinstance(v, str):
                    gesetzt[k] = v
        except Exception:                                         # noqa: BLE001
            pass
    return gesetzt


def projekt_verzeichnis():
    """Die Projektwurzel — aus CLAUDE_PROJECT_DIR, sonst ueber die Konfiguration."""
    umgebung = os.environ.get("CLAUDE_PROJECT_DIR")
    if umgebung and os.path.isdir(umgebung):
        return umgebung
    if konfig is not None:
        try:
            return konfig.projekt_wurzel()
        except Exception:                                         # noqa: BLE001
            pass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(projekt):
    """Der Ordnername, unter dem Claude Code die Projektdaten ablegt."""
    p = os.path.abspath(projekt)
    if len(p) > 1 and p[1] == ":":
        p = p[0].lower() + p[1:]
    for zeichen in (":", "\\", "/", "_"):
        p = p.replace(zeichen, "-")
    return p


def memory_dir(vorgabe=None):
    """Wo das Gedaechtnis liegt — Vorgabe, Projekt, dann der Claude-Code-Ort."""
    if vorgabe and os.path.isdir(vorgabe):
        return vorgabe
    projekt = projekt_verzeichnis()
    kandidaten = [
        os.path.join(projekt, ".claude", "memory"),
        os.path.join(os.path.expanduser("~"), ".claude", "projects",
                     slug(projekt), "memory"),
    ]
    for k in kandidaten:
        if os.path.isdir(k):
            return k
    return None


def _feld(kopf, name):
    m = re.search(r"^%s:\s*(.+)$" % name, kopf, re.MULTILINE)
    if not m:
        return ""
    return m.group(1).strip().strip('"').strip("'")


def _aktualitaet(kopf, pfad):
    """Zeitpunkt der letzten Aenderung: modified aus dem Kopf, sonst die Datei."""
    wert = _feld(kopf, "  modified") or _feld(kopf, "modified")
    for laenge, form in ((19, "%Y-%m-%dT%H:%M:%S"), (10, "%Y-%m-%d")):
        try:
            return float(calendar.timegm(time.strptime(wert[:laenge], form)))
        except (TypeError, ValueError):
            pass
    try:
        return os.path.getmtime(pfad)
    except OSError:
        return 0.0


def lesen(ordner):
    """Alle Gedaechtnisdateien einlesen. Gibt eine Liste von dicts zurueck."""
    eintraege = []
    for name in sorted(os.listdir(ordner)):
        if not name.endswith(".md") or name in ("MEMORY.md", "REGISTER.md"):
            continue
        pfad = os.path.join(ordner, name)
        try:
            with open(pfad, "r", encoding="utf-8-sig", errors="replace") as f:
                text = f.read()
        except Exception:                                         # noqa: BLE001
            continue
        m = FRONT.match(text)
        kopf = m.group(1) if m else ""
        rumpf = text[m.end():] if m else text
        eintraege.append({
            "datei": name,
            "slug": _feld(kopf, "name") or name[:-3],
            "beschreibung": _feld(kopf, "description"),
            "typ": _feld(kopf, "  type") or _feld(kopf, "type") or "?",
            "aktualitaet": _aktualitaet(kopf, pfad),
            "zeichen": len(text),
            "links": sorted(set(LINK.findall(text))),
            "rumpf": rumpf,
        })
    return eintraege


def _kurzfassen(text, grenze=None):
    """Auf eine Indexzeile eindampfen: erster Sinnabschnitt, hart gekuerzt."""
    if grenze is None:
        grenze = 110
    text = " ".join((text or "").split())
    if len(text) <= grenze:
        return text
    schnitt = text[:grenze]
    for trenner in ("; ", " · ", ", ", " "):
        p = schnitt.rfind(trenner)
        if p > grenze * 0.6:
            return schnitt[:p] + " …"
    return schnitt + " …"


def index_mass(text, mit_cr=False):
    """(Zeilen, Zeichen) eines Index.

    mit_cr zaehlt jedes Zeilenende so, wie es unter Windows auf der Platte
    steht: zwei Zeichen statt einem.
    """
    zeilen = text.count("\n")
    if text and not text.endswith("\n"):
        zeilen += 1
    zeichen = len(text)
    if mit_cr:
        zeichen += text.count("\n") - text.count("\r\n")
    return zeilen, zeichen


def _schlagwortzeilen(kopf, woerter, breite=SCHLAGWORTZEILE_MAX):
    """Schlagworte als Aufzaehlungspunkt, umbrochen auf hoechstens breite Zeichen."""
    zeilen = []
    anfang, teile = "- %s " % kopf, []
    for wort in woerter:
        if teile and len(anfang + " · ".join(teile + [wort]) + " ·") > breite:
            zeilen.append(anfang + " · ".join(teile) + " ·")
            anfang, teile = "  ", []
        teile.append(wort)
    if teile:
        zeilen.append(anfang + " · ".join(teile))
    return zeilen


def _index_text(t, eintraege, voll, kurz):
    """Der Kurzindex: voll = ganze Zeilen, kurz = nur Schlagwort, der Rest fehlt."""
    z = [t["kopfzeile"], "", t["vorspann"], ""]
    fehlt = len(eintraege) - len(voll) - len(kurz)
    if kurz:
        z += [t["gekuerzt"].replace("{kurz}", str(len(kurz)))
              .replace("{gesamt}", str(len(eintraege))), ""]
    if fehlt:
        z += [t["weggelassen"].replace("{fehlt}", str(fehlt)), ""]
    nach_typ = {}
    for i, e in enumerate(eintraege):
        nach_typ.setdefault(e["typ"], []).append((i, e))
    rubriken = t["rubriken"]
    reihenfolge = [k for k in ("feedback", "user", "project", "reference", "?")
                   if k in rubriken]
    reihenfolge += [k for k in sorted(nach_typ) if k not in reihenfolge]
    for typ in reihenfolge:
        gruppe = nach_typ.get(typ) or []
        ganz = [e for i, e in gruppe if i in voll]
        worte = sorted(e["datei"][:-3] for i, e in gruppe if i in kurz)
        if not ganz and not worte:
            continue
        z.append("## %s" % rubriken.get(typ, typ))
        z.append("")
        for e in sorted(ganz, key=lambda x: x["slug"]):
            z.append("- [%s](%s) — %s"
                     % (e["slug"], e["datei"], _kurzfassen(e["beschreibung"])))
        if worte:
            z += _schlagwortzeilen(t["schlagworte"], worte)
        z.append("")
    return "\n".join(z).rstrip() + "\n"


def _groesstes(lo, hi, geht):
    """Groesstes n in [lo, hi] mit geht(n) - geht gilt bei lo und faellt monoton."""
    while lo < hi:
        mitte = (lo + hi + 1) // 2
        if geht(mitte):
            lo = mitte
        else:
            hi = mitte - 1
    return lo


def _rang(e):
    """Vorrang: Regeln und Nutzer zuerst, dann das Juengste, dann der Name."""
    return (0 if e["typ"] in VORRANG else 1, -(e.get("aktualitaet") or 0.0), e["slug"])


def index_bauen(eintraege, t=None, max_zeilen=None, max_zeichen=None):
    """Kurzindex innerhalb des Budgets. Gibt (text, info) zurueck.

    Passt der volle Index, bleibt er, wie er ist. Sonst stehen die ersten k
    Eintraege nach Rang als ganze Zeile, die naechsten bis b nur als
    Schlagwort, der Rest fehlt - b und danach k so gross wie moeglich.
    Gemessen wird mit Windows-Zeilenenden.
    """
    t = t or texte()
    if max_zeilen is None:
        max_zeilen = min(int(_zahl("index_max_zeilen", 190)), LADEGRENZE_ZEILEN)
    if max_zeichen is None:
        max_zeichen = min(int(_zahl("index_max_zeichen", 24000)), LADEGRENZE_ZEICHEN)
    gesamt = len(eintraege)
    rang = sorted(range(gesamt), key=lambda i: _rang(eintraege[i]))

    def passt(text):
        zeilen, zeichen = index_mass(text, mit_cr=True)
        return zeilen <= max_zeilen and zeichen <= max_zeichen

    def bauen(k, b):
        return _index_text(t, eintraege, set(rang[:k]), set(rang[k:b]))

    k = b = gesamt
    text = bauen(k, b)
    if not passt(text):
        # Beide Grenzfaelle vorab: bei b = gesamt entfaellt der Weggelassen-,
        # bei k = b der Gekuerzt-Hinweis - dort ist die Laenge nicht monoton.
        def sichtbar(n):
            return passt(bauen(0, n))

        def ganz(n):
            return passt(bauen(n, b))

        b = gesamt if sichtbar(gesamt) else _groesstes(0, gesamt - 1, sichtbar)
        k = b if ganz(b) else _groesstes(0, max(b - 1, 0), ganz)
        text = bauen(k, b)
    zeilen, zeichen = index_mass(text, mit_cr=True)
    return text, {"gesamt": gesamt, "voll": k, "kurz": b - k, "weg": gesamt - b,
                  "weg_liste": sorted(eintraege[i]["datei"] for i in rang[b:]),
                  "zeilen": zeilen, "zeichen": zeichen, "passt": passt(text),
                  "max_zeilen": max_zeilen, "max_zeichen": max_zeichen}


def register_bauen(ordner, schreiben=False, info=None):
    """Baut den schlanken Index und das ausfuehrliche Verzeichnis."""
    eintraege = lesen(ordner)
    t = texte()
    schlank, messung = index_bauen(eintraege, t)
    if info is not None:
        info.update(messung)

    r = [t["register_kopfzeile"], "", t["register_vorspann"], "",
         "| Eintrag | Typ | Zeichen | verweist auf |", "|---|---|---:|---|"]
    for e in sorted(eintraege, key=lambda x: x["slug"]):
        r.append("| [%s](%s) | %s | %d | %s |"
                 % (e["slug"], e["datei"], e["typ"], e["zeichen"],
                    ", ".join(e["links"][:6]) or "—"))
    r.append("")
    r.append("## Beschreibungen")
    r.append("")
    for e in sorted(eintraege, key=lambda x: x["slug"]):
        r.append("**%s** — %s" % (e["slug"], e["beschreibung"] or "(ohne)"))
        r.append("")
    ausfuehrlich = "\n".join(r).rstrip() + "\n"

    if schreiben:
        with open(os.path.join(ordner, "MEMORY.md"), "w", encoding="utf-8") as f:
            f.write(schlank)
        with open(os.path.join(ordner, "REGISTER.md"), "w", encoding="utf-8") as f:
            f.write(ausfuehrlich)
    return schlank, ausfuehrlich, eintraege


def geheimnisse_finden(ordner):
    """Sucht Geheimnisse in den Gedaechtnisdateien. Meldet nur — tilgt NICHTS.

    Gibt (funde, fehler, uebergangene_platzhalter) zurueck; funde ist eine
    Liste von (datei, zeile, art) — nie der Wert selbst.
    """
    try:
        import ernte as v
    except Exception as e:                                        # noqa: BLE001
        return None, str(e), 0

    funde = []
    uebergangen = 0
    for name in sorted(os.listdir(ordner)):
        if not name.endswith(".md"):
            continue
        try:
            with open(os.path.join(ordner, name), "r",
                      encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:                                         # noqa: BLE001
            continue

        treffer = []
        for muster, art in v.VOLLTREFFER:
            for m in muster.finditer(text):
                treffer.append((m.start(), art))
        for muster, gruppe, art in v.FELDTREFFER:
            for m in muster.finditer(text):
                if PLATZHALTER.match(m.group(gruppe) or ""):
                    uebergangen += 1
                    continue
                treffer.append((m.start(gruppe), art))

        for pos, art in sorted(treffer):
            funde.append((name, text.count("\n", 0, pos) + 1, art))
    return funde, None, uebergangen


def review(ordner):
    """Der Hausmeister: was ist faul im Gedaechtnis?"""
    eintraege = lesen(ordner)
    slugs = {e["slug"] for e in eintraege}
    dateien = {e["datei"][:-3] for e in eintraege}
    bekannt = slugs | dateien

    befunde = []

    funde, fehler, uebergangen = geheimnisse_finden(ordner)
    if fehler:
        befunde.append(("Geheimnisprüfung gestört",
                        "ernte.py nicht ladbar (%s) — das Gedaechtnis wurde "
                        "NICHT auf Zugaenge geprueft" % fehler[:120]))
    else:
        for datei, zeile, art in funde:
            befunde.append(("GEHEIMNIS",
                            "%s Zeile %d: %s — gehoert nicht ins Gedaechtnis, "
                            "sondern in einen Passwortspeicher"
                            % (datei, zeile, art)))
        if uebergangen:
            befunde.append(("Platzhalter übergangen",
                            "%d Fund(e) sahen aus wie Platzhalter ({env:…}, "
                            "$VAR, <…>) und wurden nicht gemeldet" % uebergangen))

    for name in sorted(os.listdir(ordner)):
        k = name.lower()
        if "conflicted copy" in k or "konflikt" in k or "_conflict" in k:
            befunde.append(("Konfliktdatei",
                            "%s — der Sync-Client hat zwei Fassungen angelegt; "
                            "die richtige behalten, die andere loeschen" % name))

    for e in eintraege:
        for l in e["links"]:
            if l not in bekannt:
                befunde.append(("toter Verweis",
                                "%s verweist auf [[%s]] — gibt es nicht"
                                % (e["slug"], l)))

    verwiesen = set()
    for e in eintraege:
        verwiesen.update(e["links"])
    waisen = [e["slug"] for e in eintraege
              if e["slug"] not in verwiesen and e["datei"][:-3] not in verwiesen]
    if eintraege and len(waisen) > len(eintraege) // 4:
        befunde.append(("Vernetzung",
                        "%d von %d Einträgen ohne eingehenden Verweis — der "
                        "Zettelkasten lebt von Querverweisen (%s …)"
                        % (len(waisen), len(eintraege), ", ".join(sorted(waisen)[:4]))))

    monster = _zahl("eintrag_monster_zeichen", 15000)
    for e in eintraege:
        if e["zeichen"] > monster:
            befunde.append(("aufgebläht",
                            "%s hat %d Zeichen — teilen (Faustregel: ein Fakt, "
                            "eine Datei)" % (e["slug"], e["zeichen"])))

    for e in eintraege:
        if not e["beschreibung"]:
            befunde.append(("ohne Beschreibung",
                            "%s hat kein description-Feld — steht blind im Index"
                            % e["slug"]))

    index = os.path.join(ordner, "MEMORY.md")
    if os.path.isfile(index):
        try:
            with open(index, "r", encoding="utf-8", errors="replace", newline="") as f:
                zeilen, zeichen = index_mass(f.read())
        except OSError:
            zeilen = zeichen = 0
        if zeilen > LADEGRENZE_ZEILEN or zeichen > LADEGRENZE_ZEICHEN:
            befunde.append(("Kurzindex zu lang",
                            "MEMORY.md hat %d Zeilen und %d Zeichen — Claude Code "
                            "lädt nur %d Zeilen bzw. %d Zeichen, der Rest fehlt "
                            "still. Neu bauen: gedaechtnis.py --register"
                            % (zeilen, zeichen, LADEGRENZE_ZEILEN, LADEGRENZE_ZEICHEN)))
    _, messung = index_bauen(eintraege)
    if messung["weg"]:
        befunde.append(("Kurzindex zu klein",
                        "%d von %d Einträgen passen nicht einmal als Schlagwort in "
                        "MEMORY.md und stehen nur in REGISTER.md (%s …) — ausmisten "
                        "oder zusammenlegen"
                        % (messung["weg"], messung["gesamt"],
                           ", ".join(messung["weg_liste"][:4]))))

    gesamt = sum(e["zeichen"] for e in eintraege)
    return befunde, {"dateien": len(eintraege), "zeichen": gesamt}


def kurzmeldung(ordner):
    """Eine Zeile fuer den SessionStart — nur wenn wirklich etwas faul ist."""
    try:
        befunde, lage = review(ordner)
    except Exception:                                             # noqa: BLE001
        return ""
    if not befunde:
        return ""

    schwer = [t for a, t in befunde if a in ("GEHEIMNIS", "Geheimnisprüfung gestört")]
    leicht = {}
    for a, _ in befunde:
        if a in ("GEHEIMNIS", "Geheimnisprüfung gestört", "Platzhalter übergangen"):
            continue
        leicht[a] = leicht.get(a, 0) + 1

    zeilen = []
    if schwer:
        zeilen.append("[Gedächtnis — DRINGEND] %d Fund(e): %s"
                      % (len(schwer), " · ".join(schwer[:3])
                         + (" · …" if len(schwer) > 3 else "")))
    if leicht:
        teile = ", ".join("%d× %s" % (n, a) for a, n in sorted(leicht.items()))
        zeilen.append("[Gedächtnis] %d Einträge, %d Zeichen. Auffällig: %s. "
                      "Prüfen mit `gedaechtnis.py --review`."
                      % (lage["dateien"], lage["zeichen"], teile))
    return "\n".join(zeilen)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass
    ordner = memory_dir()
    if not ordner:
        print("Gedaechtnis-Ordner nicht gefunden.")
        return 1

    if "--kurz" in sys.argv:
        print(kurzmeldung(ordner) or "(nichts Auffaelliges)")
        return 0

    if "--register" in sys.argv:
        info = {}
        schlank, ausf, eintraege = register_bauen(ordner, schreiben=True, info=info)
        print("MEMORY.md neu:   %6d Zeichen (%d Eintraege)"
              % (len(schlank), len(eintraege)))
        print("                 %6d Zeilen, %d Zeichen mit Windows-Zeilenenden "
              "(Budget %d/%d, Ladegrenze %d/%d)"
              % (info["zeilen"], info["zeichen"], info["max_zeilen"],
                 info["max_zeichen"], LADEGRENZE_ZEILEN, LADEGRENZE_ZEICHEN))
        print("                 %6d ganze Zeilen, %d nur als Schlagwort, %d nicht aufgefuehrt"
              % (info["voll"], info["kurz"], info["weg"]))
        if not info["passt"]:
            print("ACHTUNG: auch gekuerzt ueber dem Budget — Eintraege ausmisten.")
        print("REGISTER.md neu: %6d Zeichen" % len(ausf))
        return 0

    befunde, lage = review(ordner)
    print("Gedaechtnis: %d Eintraege, %d Zeichen" % (lage["dateien"], lage["zeichen"]))
    print()
    if not befunde:
        print("Keine Auffaelligkeiten.")
        return 0
    art_vorher = None
    for art, text in sorted(befunde):
        if art != art_vorher:
            print("--- %s ---" % art.upper())
            art_vorher = art
        print("  %s" % text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
