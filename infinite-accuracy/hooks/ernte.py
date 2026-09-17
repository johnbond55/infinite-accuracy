#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ernte.py — Rohprotokoll, Tilgung und die Anweisung an die Verdichtung.

Laeuft bei SessionEnd und vor jeder Verdichtung (PreCompact). Rein
mechanisch, ohne Modellaufruf.

Bei PreCompact zusaetzlich:
  Riegel      automatische Verdichtung aufschieben (Exit 2), solange in dieser
              Sitzung nicht abgelegt wurde und der Kontext unter
              riegel_bis_token liegt
  Anweisung   die Standardausgabe gibt Claude Code als Zusatzanweisung an die
              Zusammenfassung weiter; sie traegt eine Kennmarke, die
              wiedervorlage.py und regelschub.py danach suchen

Bibliothek fuer die anderen Hooks: geheimnisse_tilgen, transkript_haerten,
alte_transkripte_haerten, haerten_und_buchen, ernten, protokoll_bauen,
ernte_vermerken, hausmeister, kontext_token, letzte_zusammenfassung,
kennmarke_pruefen, stand_lesen, stand_schreiben, sitzungsordner, state_ordner.

Begruendungen und Fallen: ../skills/kaskade/doku/ernte.md und verdichtung.md
"""
import calendar
import json
import os
import re
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "skills", "kaskade")
if KASKADE not in sys.path:
    sys.path.insert(0, KASKADE)
try:
    import konfig
except Exception:                                                 # noqa: BLE001
    konfig = None

ENDE_BYTES = 4 * 1024 * 1024
TRENNER = bytes([10])          # Zeilentrenner der Transkripte


def _zahl(name, vorgabe):
    try:
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def _pfad(name, basis):
    if konfig is not None:
        try:
            return konfig.pfad(name)
        except Exception:                                         # noqa: BLE001
            pass
    if name == "zettelkasten":
        return os.path.join(basis, ".claude", "zettelkasten")
    return os.path.join(basis, ".claude", "infinite-accuracy", name)


def _punkt(n):
    return "{:,}".format(int(n)).replace(",", ".")


STOERTAGS = re.compile(
    r"<(ide_opened_file|ide_selection|system-reminder|command-name|command-message|"
    r"command-args|local-command-stdout)>.*?</\1>",
    re.DOTALL,
)

VOLLTREFFER = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.DOTALL), "privater Schluessel"),
    (re.compile(r"\bAGE-SECRET-KEY-1[0-9A-Z]{50,}"), "age-Schluessel"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "API-Schluessel"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}"), "GitHub-Token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}"), "GitHub-Token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}"), "Slack-Token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS-Schluessel"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"), "Google-Schluessel"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "JWT"),
]

FELDNAMEN = (r"api[_-]?key|apikey|passwo?r[dt]|secret|token|private[_-]?key|"
             r"client[_-]?secret|access[_-]?key|auth")
FELDTREFFER = [
    (re.compile(r"(['\"](?:%s)['\"]\s*:\s*['\"])([^'\"]{8,})(['\"])" % FELDNAMEN,
                re.IGNORECASE), 2, "Feldwert"),
    (re.compile(r"\b([A-Z][A-Z0-9_]*(?:KEY|PASSWORD|PASSWORT|SECRET|TOKEN)"
                r"[A-Z0-9_]*\s*=\s*)(\S{8,})"), 2, "Umgebungsvariable"),
    (re.compile(r"(Bearer\s+)([A-Za-z0-9._~+/=-]{20,})"), 2, "Bearer-Token"),
]


def geheimnisse_tilgen(text):
    """Ersetzt Geheimnisse in einem String. Gibt (neuer_text, anzahl) zurueck."""
    if not text or len(text) < 12:
        return text, 0
    gezaehlt = 0

    for muster, art in VOLLTREFFER:
        text, n = muster.subn("<Secret getilgt: %s>" % art, text)
        gezaehlt += n

    for muster, gruppe, art in FELDTREFFER:
        def ersetze(m, gruppe=gruppe, art=art):
            teile = list(m.groups())
            teile[gruppe - 1] = "<Secret getilgt: %s>" % art
            return "".join(t or "" for t in teile)
        text, n = muster.subn(ersetze, text)
        gezaehlt += n

    return text, gezaehlt


def _tilgen_rekursiv(objekt):
    """Geht durch die geparste Zeile und saeubert jeden String."""
    if isinstance(objekt, str):
        return geheimnisse_tilgen(objekt)
    if isinstance(objekt, list):
        gesamt = 0
        raus = []
        for e in objekt:
            neu, n = _tilgen_rekursiv(e)
            raus.append(neu)
            gesamt += n
        return raus, gesamt
    if isinstance(objekt, dict):
        gesamt = 0
        raus = {}
        for k, v in objekt.items():
            neu, n = _tilgen_rekursiv(v)
            raus[k] = neu
            gesamt += n
        return raus, gesamt
    return objekt, 0


def _schonfrist_grenze(zeilen, schonfrist_zeichen):
    """Ab welchem Index gilt die Schonfrist? Von hinten aufsummiert."""
    if schonfrist_zeichen <= 0:
        return len(zeilen)
    summe = 0
    for i in range(len(zeilen) - 1, -1, -1):
        summe += len(zeilen[i])
        if summe >= schonfrist_zeichen:
            return i
    return 0


def transkript_haerten(pfad, schonfrist_zeichen=None):
    """Tilgt Geheimnisse aus einem Transkript. Gibt die Zahl der Tilgungen zurueck."""
    if schonfrist_zeichen is None:
        schonfrist_zeichen = _zahl("schonfrist_zeichen", 120000)
    pfad = str(pfad)
    if not os.path.isfile(pfad):
        return 0
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace", newline="") as f:
            roh = f.read()
    except Exception:                                             # noqa: BLE001
        return 0
    zeilen = roh.split("\n")
    endet_mit_umbruch = bool(zeilen) and zeilen[-1] == ""
    if endet_mit_umbruch:
        zeilen.pop()
    if not zeilen:
        return 0

    grenze = _schonfrist_grenze(zeilen, schonfrist_zeichen)
    neu_zeilen, getilgt = [], 0
    for i, zeile in enumerate(zeilen):
        if i >= grenze or not zeile.strip():
            neu_zeilen.append(zeile)
            continue
        try:
            objekt = json.loads(zeile)
        except Exception:                                         # noqa: BLE001
            neu_zeilen.append(zeile)
            continue
        sauber, n = _tilgen_rekursiv(objekt)
        if not n:
            neu_zeilen.append(zeile)
            continue
        try:
            ersatz = json.dumps(sauber, ensure_ascii=False)
            json.loads(ersatz)
        except Exception:                                         # noqa: BLE001
            neu_zeilen.append(zeile)
            continue
        neu_zeilen.append(ersatz)
        getilgt += n

    if not getilgt:
        return 0
    if len(neu_zeilen) != len(zeilen):
        return 0

    inhalt = "\n".join(neu_zeilen) + ("\n" if endet_mit_umbruch else "")
    sicherung = pfad + ".ia-tilgung-bak"
    try:
        with open(pfad, "rb") as q, open(sicherung, "wb") as z:
            z.write(q.read())
    except Exception:                                             # noqa: BLE001
        return 0
    try:
        with open(pfad, "r+", encoding="utf-8", newline="\n") as f:
            f.seek(0)
            f.write(inhalt)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())
    except Exception:                                             # noqa: BLE001
        try:
            with open(sicherung, "rb") as q, open(pfad, "wb") as z:
                z.write(q.read())
        except Exception:                                         # noqa: BLE001
            pass
        getilgt = 0
    try:
        os.remove(sicherung)
    except Exception:                                             # noqa: BLE001
        pass
    return getilgt


def alte_transkripte_haerten(aktuelles=None, ordner=None):
    """Alle ANDEREN Transkripte des Projekts saeubern."""
    gesamt, dateien = 0, 0
    try:
        if not ordner:
            if not aktuelles:
                return 0, 0
            ordner = os.path.dirname(str(aktuelles))
        mindestalter = _zahl("nachlese_mindestalter_sekunden", 300)
        jetzt = time.time()
        for eintrag in os.scandir(ordner):
            if not eintrag.is_file() or not eintrag.name.endswith(".jsonl"):
                continue
            if aktuelles and os.path.abspath(eintrag.path) == os.path.abspath(str(aktuelles)):
                continue
            if jetzt - eintrag.stat().st_mtime < mindestalter:
                continue
            n = transkript_haerten(eintrag.path, schonfrist_zeichen=0)
            if n:
                gesamt += n
                dateien += 1
    except Exception:                                             # noqa: BLE001
        pass
    return gesamt, dateien


def projekt_verzeichnis(daten):
    cwd = daten.get("cwd")
    if cwd and os.path.isdir(cwd):
        return cwd
    if konfig is not None:
        try:
            return konfig.projekt_wurzel()
        except Exception:                                         # noqa: BLE001
            pass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sitzungsordner(basis):
    """Wo Rohprotokolle, Destillate und das Tilgungslog liegen."""
    return _pfad("sitzungen", basis)


def state_ordner(basis):
    """Wo Zaehlerstaende, Sperren und Standdateien liegen."""
    return _pfad("state", basis)


def saeubern(text):
    text = STOERTAGS.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ernten(pfad):
    """Liest das Transkript und gibt die Fakten als dict zurueck."""
    max_zeilen = _zahl("protokoll_max_zeilen", 40000)
    titel = ""
    prompts = []
    kommandos = []
    dateien = []
    schlusstexte = []
    erste_zeit = letzte_zeit = ""
    nachrichten = 0

    with open(pfad, "r", encoding="utf-8", errors="replace") as f:
        for nr, zeile in enumerate(f):
            if nr > max_zeilen:
                break
            if ('"promptSource"' not in zeile and '"assistant"' not in zeile
                    and '"ai-title"' not in zeile):
                continue
            try:
                o = json.loads(zeile)
            except Exception:                                     # noqa: BLE001
                continue

            typ = o.get("type")
            if typ == "ai-title":
                titel = o.get("aiTitle") or titel
                continue

            zeit = o.get("timestamp") or ""
            if zeit:
                if not erste_zeit:
                    erste_zeit = zeit
                letzte_zeit = zeit

            msg = o.get("message") or {}
            inhalt = msg.get("content")
            if not isinstance(inhalt, list):
                continue

            if typ == "user" and o.get("promptSource"):
                if any(isinstance(t, dict) and t.get("type") == "tool_result" for t in inhalt):
                    continue
                text = "".join(str(t.get("text", "")) for t in inhalt
                               if isinstance(t, dict) and t.get("type") == "text")
                text = saeubern(text)
                if text:
                    prompts.append(text)

            elif typ == "assistant":
                nachrichten += 1
                for teil in inhalt:
                    if not isinstance(teil, dict):
                        continue
                    if teil.get("type") == "text":
                        t = str(teil.get("text", "")).strip()
                        if t:
                            schlusstexte.append(t)
                    elif teil.get("type") == "tool_use":
                        name = teil.get("name")
                        eingabe = teil.get("input") or {}
                        if not isinstance(eingabe, dict):
                            continue
                        if name in ("PowerShell", "Bash"):
                            k = str(eingabe.get("command", "")).strip()
                            if k:
                                kommandos.append(" ".join(k.split())[:150])
                        elif name in ("Write", "Edit", "NotebookEdit"):
                            p = str(eingabe.get("file_path", "")).strip()
                            if p:
                                dateien.append(p)

    return {
        "titel": titel,
        "prompts": prompts,
        "kommandos": kommandos,
        "dateien": dateien,
        "schluss": schlusstexte[-1] if schlusstexte else "",
        "von": erste_zeit,
        "bis": letzte_zeit,
        "nachrichten": nachrichten,
    }


def kuerzen(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rstrip() + " …"


def eindeutig(liste):
    gesehen, raus = set(), []
    for e in liste:
        if e not in gesehen:
            gesehen.add(e)
            raus.append(e)
    return raus


def haerten_und_buchen(pfad, marke, ordner):
    """Tilgen UND ins Tilgungslog schreiben — die eine Fassung fuer alle Aufrufer."""
    if not pfad or not os.path.isfile(pfad):
        return 0
    n = transkript_haerten(pfad)
    n = n[0] if isinstance(n, tuple) else (n or 0)
    if n:
        try:
            os.makedirs(ordner, exist_ok=True)
            with open(os.path.join(ordner, "tilgungen.log"), "a",
                      encoding="utf-8") as f:
                f.write("%s  %-12s  %s  %d getilgt\n"
                        % (time.strftime("%Y-%m-%d %H:%M"), marke,
                           os.path.basename(pfad), n))
        except Exception:                                         # noqa: BLE001
            pass
    return n


def protokoll_bauen(f, anlass, basis):
    max_schluss = _zahl("protokoll_max_schluss", 2500)
    max_prompts = _zahl("protokoll_max_prompts", 25)
    max_promptlaenge = _zahl("protokoll_max_promptlaenge", 420)
    max_kommandos = _zahl("protokoll_max_kommandos", 40)

    zeile = []
    z = zeile.append

    z("# Sitzung %s — %s" % (time.strftime("%d.%m.%Y"), f["titel"] or "ohne Titel"))
    z("")
    z("*Automatisch geerntet: %s. %d Antworten, %d Prompts.*"
      % (anlass, f["nachrichten"], len(f["prompts"])))
    if f["von"]:
        z("*Zeitraum %s bis %s (UTC).*" % (f["von"][:16].replace("T", " "),
                                           f["bis"][:16].replace("T", " ")))
    z("")

    if f["schluss"]:
        z("## Schlussstand (letzte Antwort)")
        z("")
        s = f["schluss"]
        z(s if len(s) <= max_schluss else s[:max_schluss].rstrip() + "\n\n*… gekuerzt*")
        z("")

    z("## Was verlangt wurde")
    z("")
    for p in f["prompts"][:max_prompts]:
        z("- %s" % kuerzen(p, max_promptlaenge))
    if len(f["prompts"]) > max_prompts:
        z("- *… %d weitere*" % (len(f["prompts"]) - max_prompts))
    z("")

    dateien = eindeutig(f["dateien"])
    if dateien:
        z("## Angefasste Dateien (%d)" % len(dateien))
        z("")
        for p in dateien[:30]:
            try:
                kurz = os.path.relpath(p, basis)
            except Exception:                                     # noqa: BLE001
                kurz = p
            z("- `%s`" % kurz)
        if len(dateien) > 30:
            z("- *… %d weitere*" % (len(dateien) - 30))
        z("")

    kommandos = eindeutig(f["kommandos"])
    if kommandos:
        z("## Ausgefuehrte Kommandos (%d, davon %d verschieden)"
          % (len(f["kommandos"]), len(kommandos)))
        z("")
        z("```")
        for k in kommandos[:max_kommandos]:
            z(k)
        if len(kommandos) > max_kommandos:
            z("… %d weitere" % (len(kommandos) - max_kommandos))
        z("```")
        z("")

    z("---")
    z("*Rohprotokoll. Das gedeutete Destillat schreibt das Modell bei erreichter "
      "Kontextschwelle oder auf Zuruf.*")
    return "\n".join(zeile)


def ernte_vermerken(basis, pfad):
    """Groesse des geernteten Transkripts vermerken, damit haertung.py dieselbe
    Sitzung nicht noch einmal nacherntet."""
    try:
        state = state_ordner(basis)
        os.makedirs(state, exist_ok=True)
        stand_pfad_ = os.path.join(state, "haertung.json")
        stand = {}
        try:
            with open(stand_pfad_, "r", encoding="utf-8") as f:
                stand = json.load(f)
            if not isinstance(stand, dict):
                stand = {}
        except Exception:                                         # noqa: BLE001
            stand = {}
        eintrag = stand.get(os.path.basename(pfad)) or {}
        eintrag["geerntet_size"] = os.path.getsize(pfad)
        stand[os.path.basename(pfad)] = eintrag
        with open(stand_pfad_, "w", encoding="utf-8") as f:
            json.dump(stand, f)
    except Exception:                                             # noqa: BLE001
        pass


def hausmeister(ordner):
    """Rohprotokolle ausduennen: die juengsten bleiben, aeltere ins Archiv."""
    behalten = _zahl("rohprotokolle_behalten", 40)
    try:
        rohe = sorted(
            (e for e in os.scandir(ordner)
             if e.is_file() and e.name.endswith("-roh.md")),
            key=lambda e: e.name,
        )
        if len(rohe) <= behalten:
            return
        archiv = os.path.join(ordner, "archiv")
        os.makedirs(archiv, exist_ok=True)
        for e in rohe[:-behalten]:
            ziel = os.path.join(archiv, e.name)
            if os.path.exists(ziel):
                os.remove(ziel)
            os.replace(e.path, ziel)
    except Exception:                                             # noqa: BLE001
        pass


def _ende_lesen(transkript):
    if not transkript or not os.path.isfile(transkript):
        return None
    try:
        groesse = os.path.getsize(transkript)
        with open(transkript, "rb") as f:
            f.seek(max(0, groesse - ENDE_BYTES))
            return f.read()
    except Exception:                                             # noqa: BLE001
        return None


def kontext_token(transkript):
    """(token, verdichtet): Kontext der juengsten Antwort laut usage-Zeile;
    verdichtet=True, wenn dahinter eine Verdichtungsmarke steht."""
    daten = _ende_lesen(transkript)
    if daten is None:
        return None, False
    verdichtet = False
    for roh in reversed(daten.split(b"\n")):
        if b"compact_boundary" not in roh and (b"assistant" not in roh or b"usage" not in roh):
            continue
        try:
            o = json.loads(roh.decode("utf-8", "replace"))
        except Exception:                                         # noqa: BLE001
            continue
        if o.get("type") == "system" and o.get("subtype") == "compact_boundary":
            verdichtet = True
            continue
        if o.get("type") != "assistant":
            continue
        u = (o.get("message") or {}).get("usage") or {}
        if not u:
            continue
        tok = ((u.get("input_tokens") or 0)
               + (u.get("cache_creation_input_tokens") or 0)
               + (u.get("cache_read_input_tokens") or 0))
        return tok, verdichtet
    return None, verdichtet


def _zeit_aus_marke(text):
    """Zeitstempel einer Transkriptzeile (ISO in UTC) als Epochensekunden."""
    try:
        return calendar.timegm(time.strptime(str(text)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:                                             # noqa: BLE001
        return None


def zusammenfassung_mit_zeit(transkript):
    """(text, zeit) der juengsten Verdichtungs-Zusammenfassung, sonst (None, None).

    Die Zeit entscheidet, ob die Zusammenfassung zur zuletzt vergebenen
    Kennmarke gehoert. Eine aeltere stammt von einer frueheren Verdichtung:
    dann wurde die neue aufgeschoben (Riegel) und darf keinen Fehlalarm
    ausloesen.
    """
    daten = _ende_lesen(transkript)
    if daten is None:
        return None, None
    for roh in reversed(daten.split(TRENNER)):
        if b"isCompactSummary" not in roh:
            continue
        try:
            o = json.loads(roh.decode("utf-8", "replace"))
        except Exception:                                         # noqa: BLE001
            continue
        if o.get("isCompactSummary") is not True:
            continue
        zeit = _zeit_aus_marke(o.get("timestamp"))
        inhalt = (o.get("message") or {}).get("content")
        if isinstance(inhalt, str):
            return inhalt, zeit
        if isinstance(inhalt, list):
            return TRENNER.decode("ascii").join(
                str(t.get("text", "")) for t in inhalt
                if isinstance(t, dict) and t.get("type") == "text"), zeit
        return "", zeit
    return None, None


def letzte_zusammenfassung(transkript):
    """Text der juengsten Verdichtungs-Zusammenfassung, sonst None."""
    return zusammenfassung_mit_zeit(transkript)[0]


def kennmarke_pruefen(marke, zusammenfassung, zusammenfassung_zeit=None,
                      marke_zeit=None):
    """(art, meldung) mit art in ok · fehlt · unpruefbar · ohne_marke.

    Mit beiden Zeiten wird unterschieden, ob die Zusammenfassung ueberhaupt
    zu dieser Kennmarke gehoert. Fehlt die Marke in einer AELTEREN
    Zusammenfassung, hat die Verdichtung noch nicht stattgefunden - das ist
    kein Befund, sondern der aufgeschobene Riegel.
    """
    if not marke:
        return ("ohne_marke",
                "Keine Kennmarke hinterlegt: vor dieser Verdichtung lief der "
                "PreCompact-Hook von infinite-accuracy nicht.")
    if zusammenfassung is None:
        return ("unpruefbar",
                "Kennmarke %s nicht pruefbar: keine Zusammenfassung im Transkript "
                "gefunden." % marke)
    if marke in zusammenfassung:
        return ("ok", "Kennmarke %s in der Zusammenfassung bestaetigt." % marke)
    if (zusammenfassung_zeit is not None and marke_zeit is not None
            and zusammenfassung_zeit < marke_zeit):
        return ("unpruefbar",
                "Kennmarke %s nicht pruefbar: die juengste Zusammenfassung ist "
                "aelter als die Kennmarke - die Verdichtung steht noch aus."
                % marke)
    return ("fehlt",
            "WARNUNG: Kennmarke %s fehlt in der Zusammenfassung. Claude Code hat die "
            "Anweisung von infinite-accuracy nicht uebernommen, moeglicherweise nach "
            "einem Update von Claude Code. Abgelegtes im Zettelkasten nachschlagen "
            "und den Befund dem Nutzer melden (doku/verdichtung.md)." % marke)


def stand_pfad(basis, session_id):
    return os.path.join(state_ordner(basis), "last-%s.json" % str(session_id)[:64])


def stand_lesen(basis, session_id):
    try:
        with open(stand_pfad(basis, session_id), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:                                             # noqa: BLE001
        return {}


def stand_schreiben(basis, session_id, stand):
    try:
        os.makedirs(state_ordner(basis), exist_ok=True)
        with open(stand_pfad(basis, session_id), "w", encoding="utf-8") as f:
            json.dump(stand, f, ensure_ascii=False)
    except Exception:                                             # noqa: BLE001
        pass


def destillat_frisch(stand):
    """Wurde das angeforderte Destillat nach dem Auftrag geschrieben?"""
    pfad = stand.get("destillat")
    if not pfad or not os.path.isfile(pfad):
        return False
    try:
        return os.path.getmtime(pfad) >= float(stand.get("auftrag_ts") or 0) - 5
    except Exception:                                             # noqa: BLE001
        return False


def riegel_grund(trigger, tok, stand):
    """Leer = durchlassen. Sonst der Grund, warum die Verdichtung warten soll."""
    if trigger != "auto" or tok is None:
        return ""
    grenze = _zahl("riegel_bis_token", 300000)
    if tok >= grenze or destillat_frisch(stand):
        return ""
    return ("[infinite-accuracy] Verdichtung aufgeschoben: in dieser Sitzung wurde "
            "noch nicht abgelegt (Kontext %s Token, Riegel bis %s). Beim naechsten "
            "Userhalt fordert regelschub.py die Ablage an."
            % (_punkt(tok), _punkt(grenze)))


def kennmarke_bilden(session_id):
    return "ia-%s-%s" % (str(session_id or "ohne")[:8], time.strftime("%Y%m%d%H%M%S"))


def verdichtungs_anweisung(kennmarke, stand, rohprotokoll=None):
    """Der Text, den Claude Code der Zusammenfassung als Anweisung mitgibt."""
    zeilen = [
        "[infinite-accuracy Kennmarke %s]" % kennmarke,
        "Anweisung von infinite-accuracy fuer diese Zusammenfassung:",
        "1. Beginne die Zusammenfassung woertlich mit der Zeile: "
        "[infinite-accuracy Kennmarke %s]" % kennmarke,
        "2. Was im Destillat unten oder im Zettelkasten abgelegt ist, nicht "
        "nacherzaehlen: das Destillat als Grundstock uebernehmen, Abgelegtes nur "
        "als Verweis (Dateipfad, Dossier) nennen.",
        "3. Vollstaendig und woertlich erhalten: den laufenden Arbeitsschritt "
        "(Auftrag, letzter Stand, naechster Schritt), offene Rueckfragen, "
        "Festlegungen und Freigaben des Nutzers, Pfade, Hashes und Befehle der "
        "laufenden Aufgabe.",
        "4. Weglassen: Werkzeugausgaben, Dateiinhalte und Zwischenstaende, die "
        "abgeschlossen oder abgelegt sind.",
    ]
    pfad = stand.get("destillat")
    if pfad and os.path.isfile(pfad):
        try:
            with open(pfad, "r", encoding="utf-8-sig", errors="replace") as f:
                text = f.read().strip()
            grenze = _zahl("verdichtung_destillat_max", 12000)
            if len(text) > grenze:
                text = text[:grenze].rstrip() + "\n[… gekuerzt, vollstaendig in %s]" % pfad
            zeilen += ["", "--- Destillat %s ---" % pfad, text, "--- Ende Destillat ---"]
        except Exception:                                         # noqa: BLE001
            pass
    else:
        zeilen.append("Ein Destillat dieser Sitzung liegt nicht vor.")
        if rohprotokoll:
            zeilen.append("Rohprotokoll dieser Sitzung: %s" % rohprotokoll)
    return "\n".join(zeilen)


def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass

    try:
        roh = sys.stdin.read()
        daten = json.loads(roh) if roh.strip() else {}
        pfad = daten.get("transcript_path")
        if not pfad or not os.path.isfile(pfad):
            sys.exit(0)

        ereignis = daten.get("hook_event_name") or "?"
        basis = projekt_verzeichnis(daten)
        ordner = sitzungsordner(basis)
        sid = daten.get("session_id")
        vor_verdichtung = ereignis == "PreCompact"
        stand = stand_lesen(basis, sid) if (vor_verdichtung and sid) else {}

        if vor_verdichtung:
            trigger = daten.get("trigger") or "auto"
            tok, _ = kontext_token(pfad)
            grund = riegel_grund(trigger, tok, stand)
            if grund:
                sys.stderr.write(grund + "\n")
                sys.exit(2)
            anlass = "vor der Kontext-Komprimierung (%s)" % trigger
            marke = "vorcompact"
        else:
            anlass = "Sitzungsende (%s)" % (daten.get("reason") or "?")
            marke = "ende"

        protokoll = None
        try:
            fakten = ernten(pfad)
            if len(fakten["prompts"]) >= _zahl("protokoll_min_prompts", 2):
                os.makedirs(ordner, exist_ok=True)
                name = "%s-%s-roh.md" % (time.strftime("%Y-%m-%d-%H%M"), marke)
                text, getilgt_p = geheimnisse_tilgen(protokoll_bauen(fakten, anlass, basis))
                if getilgt_p:
                    text += ("\n\n*Im Protokoll wurden %d Geheimnisse getilgt.*\n"
                             % getilgt_p)
                protokoll = os.path.join(ordner, name)
                with open(protokoll, "w", encoding="utf-8") as f:
                    f.write(text)
                hausmeister(ordner)
                ernte_vermerken(basis, pfad)
        except Exception:                                         # noqa: BLE001
            pass

        haerten_und_buchen(pfad, marke, ordner)

        if vor_verdichtung:
            kennmarke = kennmarke_bilden(sid)
            if sid:
                stand["kennmarke"] = kennmarke
                stand["kennmarke_ts"] = int(time.time())
                stand_schreiben(basis, sid, stand)
            print(verdichtungs_anweisung(kennmarke, stand, protokoll))
    except Exception:                                             # noqa: BLE001
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
