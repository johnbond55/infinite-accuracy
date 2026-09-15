#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zettel.py — Zettelkasten des Projekts, nach der Ablage der Schreibstube (Ferradea).

Drei Schichten je Arbeitsverzeichnis (basis "" = Wurzel, "Projekte/<slug>" = Projekt):
  Journal    Strom, append-only, je Tag eine Seite, Eintraege mit #Schlagworten
  Dossiers   lebende Titelseite (Stand/Gesichert/Offen/Ressourcen) und
             Besuchs-Log — nur Links auf Journal-Eintraege, geschrieben beim Ablegen
  Meta-Meta  Erkenntnis-Index (Wurzel) bzw. Roadmap (Projekt)
Dazu Schlagwort-Register, Reflexionen, Projekte-Regal und Hausmeister.

Den Inhalt schreibt das Modell im Chat. Dieses Werkzeug legt ab, verlinkt, sucht
und liest; es ruft kein Modell auf.

Aufrufe:
    zettel.py ablegen <eingabe.json>
    zettel.py suche <begriff> [...] [--projekt P]
    zettel.py lies <seite|thema> [--projekt P]
    zettel.py stand [<thema>] [--projekt P]
    zettel.py karte | landkarte | fortschritt [--projekt P]
    zettel.py projekte
    zettel.py reflexion <JJJJ-MM-TT> <textdatei> [--projekt P]
    zettel.py reflexionen [--projekt P]
    zettel.py roh <textdatei> [--projekt P]
    zettel.py portieren <thema> <projekt>
    zettel.py hausmeister [--archivieren]
    zettel.py reindex

Begruendungen und Fallen: ../kaskade/doku/zettel.md
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HIER = os.path.dirname(os.path.abspath(__file__))
KASKADE = os.path.join(os.path.dirname(HIER), "kaskade")
if KASKADE not in sys.path:
    sys.path.insert(0, KASKADE)
try:
    import konfig
except Exception:                                                 # noqa: BLE001
    konfig = None


def _zahl(name, vorgabe):
    try:
        return konfig.zahl(name)
    except Exception:                                             # noqa: BLE001
        return vorgabe


def _wurzel():
    if konfig is not None:
        try:
            return Path(konfig.pfad("zettelkasten"))
        except Exception:                                         # noqa: BLE001
            pass
    return Path(os.getcwd()) / ".claude" / "zettelkasten"


def _state_wurzel(zk):
    if konfig is not None:
        try:
            return Path(konfig.pfad("state"))
        except Exception:                                         # noqa: BLE001
            pass
    return zk


ZK = _wurzel()
STATE = _state_wurzel(ZK)
ARCHIV = "_Archiv"
EINGANG = "_eingang"


def setzen_wurzel(pfad):
    """Wurzel des Zettelkastens umsetzen. Fuer Proben."""
    global ZK
    ZK = Path(pfad)


def setzen_state(pfad):
    """Ort des Kreis-Zaehlers umsetzen. Fuer Proben."""
    global STATE
    STATE = Path(pfad)


def _now():
    return datetime.now()


def _rel(basis: str, relpath: str) -> str:
    return (basis.strip("/") + "/" + relpath) if basis else relpath


def _ist_projekt(basis: str) -> bool:
    return bool(basis) and basis.strip("/").startswith("Projekte/")


def _ensure_dir(d) -> None:
    Path(d).mkdir(parents=True, exist_ok=True)


def _schreiben(p, text: str) -> None:
    p = Path(p)
    _ensure_dir(p.parent)
    tmp = p.with_name(p.name + ".ia-neu")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, p)


def _append(relpath: str, header: str, block: str) -> Path:
    p = ZK / relpath
    _ensure_dir(p.parent)
    neu = not p.exists()
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        if neu and header:
            f.write(header.rstrip() + "\n")
        f.write("\n" + block.rstrip() + "\n")
    return p


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s)
    return s[:60] or "ohne-titel"


def _tags(schlagworte) -> str:
    tags = []
    for w in (schlagworte or [])[:5]:
        s = _slug(w)
        if s and s != "ohne-titel" and ("#" + s) not in tags:
            tags.append("#" + s)
    return ("Schlagworte: " + " ".join(tags)) if tags else ""


def pagename(p) -> str:
    """Absoluter Pfad -> Seitenname (relativ zur Wurzel, ohne .md, mit /)."""
    rel = Path(p).relative_to(ZK).as_posix()
    return rel[:-3] if rel.endswith(".md") else rel


def journal_pagename(p) -> str:
    return pagename(p)


def _index_link(index_rel: str, target: str, label: str, section: str) -> None:
    """Idempotent: Wikilink auf die Uebersichtsseite haengen, falls noch nicht da."""
    p = ZK / index_rel
    content = p.read_text(encoding="utf-8") if p.exists() else ""
    if f"[[{target}]]" in content:
        return
    add = ""
    if section and f"## {section}" not in content:
        add += f"\n\n## {section}"
    add += f"\n- [[{target}]]" + (f" — {label}" if label else "")
    _ensure_dir(p.parent)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(add + "\n")


# ---------- Journal (Strom, append-only) ----------

def journal_append(text: str, quelle: str = "live", titel: str = "",
                   schlagworte=None, basis: str = "") -> Path:
    n = _now()
    rel = _rel(basis, f"Journal/{n:%Y}/{n:%Y-%m-%d}.md")
    header = f"# Journal {n:%Y-%m-%d}\n"
    kopf = f"## {n:%H:%M}" + (f" — {titel}" if titel else "")
    block = f"{kopf}\n\n{text.strip()}"
    tagline = _tags(schlagworte)
    if tagline:
        block += f"\n\n{tagline}"
    block += f"\n\n_Quelle: {quelle}_"
    p = _append(rel, header, block)
    _index_link(_rel(basis, "Journal.md"), _rel(basis, f"Journal/{n:%Y}/{n:%Y-%m-%d}"),
                f"{n:%Y-%m-%d}", "Tage")
    return p


def rawpush(text: str, basis: str = "") -> Path:
    return journal_append(text, quelle="rawpush", basis=basis)


# ---------- Meta-Meta: Erkenntnis-Index (Journal) / Roadmap (Projekt) ----------

def _metameta(basis: str):
    if _ist_projekt(basis):
        return (_rel(basis, "Roadmap.md"),
                "# Roadmap\n\nDer Plan & die gesicherte Richtung dieses Projekts. "
                "Der Gefährte trägt Entscheidungen/Einsichten ein; du ordnest frei.\n")
    return (_rel(basis, "Erkenntnis-Index.md"),
            "# Erkenntnis-Index\n\nDestillierte Einsichten, eine Zeile je "
            "Erkenntnis. Wird immer mitgeladen.\n")


def erkenntnis_append(zeile: str, quelle_link: str = "", basis: str = "") -> Path:
    n = _now()
    rel, header = _metameta(basis)
    ref = quelle_link or _rel(basis, f"Journal/{n:%Y}/{n:%Y-%m-%d}")
    block = f"- {zeile.strip()}  _(erkannt {n:%Y-%m-%d}, [[{ref}]])_"
    return _append(rel, header, block)


def erkenntnis_text(limit: int = 30, basis: str = "") -> str:
    rel, _ = _metameta(basis)
    p = ZK / rel
    if not p.exists():
        return ""
    zeilen = [l for l in p.read_text(encoding="utf-8").splitlines()
              if l.strip().startswith("- ")]
    return "\n".join(zeilen[-limit:])


# ---------- Reflexionen ----------

def reflexion_append(text: str, datum: str, basis: str = "") -> Path:
    n = _now()
    header = ("# Reflexionen\n\nOffene Fragen mit Prüftermin. Der Termin-Wächter "
              "meldet sich am angegebenen Datum.\n")
    block = (f"## @{datum} — angelegt {n:%Y-%m-%d}\n\n{text.strip()}\n\n"
             f"- [ ] am {datum} prüfen")
    return _append(_rel(basis, "Reflexionen.md"), header, block)


def open_reflexionen(basis: str = "") -> list:
    p = ZK / _rel(basis, "Reflexionen.md")
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'## @(\d{4}-\d{2}-\d{2}).*?(?=\n## @|\Z)', txt, re.S):
        block, datum = m.group(0), m.group(1)
        if re.search(r'- \[ \] am ' + re.escape(datum), block):
            body = re.sub(r'^## @.*\n', '', block)
            body = re.sub(r'\n- \[ \].*', '', body).strip()
            out.append((datum, body))
    return out


# ---------- Dossiers (Meta-Ebene) ----------

def _dossier_header(thema: str, basis: str, untertitel: str = "Themen-Dossier.") -> str:
    ress = "## Ressourcen\n\nLinks, Zeichnungen, CAD, Tabellen zu diesem Teilaspekt.\n\n"
    return (f"# {thema}\n\n{untertitel}\n\n## Stand\n\n## Gesichert\n\n"
            f"## Offen\n\n{ress}## Besuchs-Log\n")


def existing_dossiers(basis: str = "") -> list:
    d = ZK / _rel(basis, "Dossiers")
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.md")):
        try:
            erste = f.read_text(encoding="utf-8").splitlines()[0]
            out.append(erste.lstrip("# ").strip() or f.stem)
        except Exception:                                         # noqa: BLE001
            out.append(f.stem)
    return out


def dossier_link(thema: str, journal_page: str, schlagworte=None, basis: str = "") -> Path:
    n = _now()
    rel = _rel(basis, f"Dossiers/{_slug(thema)}.md")
    header = _dossier_header(thema, basis)
    tagline = _tags(schlagworte)
    block = f"### {n:%Y-%m-%d %H:%M} — [[{journal_page}]]"
    if tagline:
        block += f"\n{tagline}"
    p = _append(rel, header, block)
    _index_link(_rel(basis, "Dossiers.md"), _rel(basis, f"Dossiers/{_slug(thema)}"),
                thema, "Akten")
    return p


def _dossier_abschnitt(text: str, titel: str) -> str:
    m = re.search(r'^## ' + re.escape(titel) + r'\s*\n(.*?)(?=\n## |\Z)', text, re.S | re.M)
    return m.group(1).strip() if m else ""


def dossier_sections_text(thema: str, basis: str = "") -> str:
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    i0 = text.find("## Stand")
    i1 = text.find("## Ressourcen")
    if i1 == -1:
        i1 = text.find("## Besuchs-Log")
    if i0 == -1:
        return ""
    return text[i0:i1] if i1 != -1 else text[i0:]


def dossier_journal_texts(thema: str, limit: int = 12, maxchars: int = 9000,
                          basis: str = "") -> str:
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    links = re.findall(r"\[\[(Journal/[^\]|]+|Projekte/[^\]|]+?/Journal/[^\]|]+)", text)
    out = []
    for l in links[-limit:]:
        f = ZK / (l + ".md")
        if f.exists():
            try:
                out.append(f.read_text(encoding="utf-8"))
            except Exception:                                     # noqa: BLE001
                pass
    return ("\n\n---\n\n".join(out))[-maxchars:]


def dossier_write_sections(thema: str, stand: str, gesichert: str, offen: str,
                           basis: str = "") -> Path:
    """Schreibt Stand/Gesichert/Offen neu; Titel, Ressourcen und Besuchs-Log bleiben."""
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        return p
    text = p.read_text(encoding="utf-8")
    i_stand = text.find("## Stand")
    i_rest = text.find("## Ressourcen")
    if i_rest == -1:
        i_rest = text.find("## Besuchs-Log")
    preamble = text[:i_stand].rstrip() if i_stand != -1 else f"# {thema}\n\nThemen-Dossier."
    rest = text[i_rest:].rstrip() if i_rest != -1 else "## Besuchs-Log"

    def sec(title, body):
        body = (body or "").strip()
        return f"## {title}\n\n" + (body + "\n\n" if body else "")

    neu = (preamble + "\n\n"
           + sec("Stand", stand) + sec("Gesichert", gesichert) + sec("Offen", offen)
           + rest + "\n")
    _schreiben(p, neu)
    return p


def dossier_ensure(thema: str, basis: str = "", untertitel: str = "Themen-Dossier.") -> Path:
    """Legt ein Dossier (nur Kopf) an, falls es fehlt; verlinkt es in der Uebersicht."""
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        _schreiben(p, _dossier_header(thema, basis, untertitel))
        _index_link(_rel(basis, "Dossiers.md"), _rel(basis, f"Dossiers/{_slug(thema)}"),
                    thema, "Akten")
    return p


def dossier_ressource(thema: str, zeile: str, basis: str = "") -> None:
    """Haengt eine Ressourcen-Zeile (Link + Einzeiler) in ein Dossier."""
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    m = re.search(r'(## Ressourcen\s*\n(?:.*?\n)*?)(?=\n## Besuchs-Log|\Z)', text, re.S)
    if not m:
        einschub = "## Ressourcen\n\nLinks, Zeichnungen, CAD, Tabellen zu diesem Teilaspekt.\n\n"
        bl = text.find("## Besuchs-Log")
        if bl == -1:
            text = text.rstrip() + "\n\n" + einschub
        else:
            text = text[:bl] + einschub + text[bl:]
        m = re.search(r'(## Ressourcen\s*\n(?:.*?\n)*?)(?=\n## Besuchs-Log|\Z)', text, re.S)
        if not m:
            return
    block = m.group(1).rstrip()
    if zeile.strip() in block:
        return
    neu = text[:m.start(1)] + block + f"\n- {zeile.strip()}\n\n" + text[m.end(1):]
    _schreiben(p, neu)


def dossier_ressource_notiz(thema: str, url: str, notiz: str, basis: str = "") -> None:
    """Haengt an die Ressourcen-Zeile, die `url` enthaelt, eine Notiz an (idempotent)."""
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        return
    lines = p.read_text(encoding="utf-8").split("\n")
    for i, ln in enumerate(lines):
        if url in ln and ln.lstrip().startswith("-"):
            if notiz.strip() in ln:
                return
            lines[i] = ln.rstrip() + " · " + notiz.strip()
            _schreiben(p, "\n".join(lines))
            return


def dossier_ressource_zeile(thema: str, url: str, basis: str = "") -> str:
    """Gibt die Ressourcen-Zeile (ohne fuehrendes '- '), die `url` enthaelt, oder ''."""
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        return ""
    for ln in p.read_text(encoding="utf-8").split("\n"):
        if url in ln and ln.lstrip().startswith("-"):
            return ln.lstrip("- ").rstrip()
    return ""


def dossier_ressource_entfernen(thema: str, url: str, basis: str = "") -> None:
    """Entfernt die Ressourcen-Zeile, die `url` enthaelt (idempotent)."""
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    if not p.exists():
        return
    lines = p.read_text(encoding="utf-8").split("\n")
    neu = [ln for ln in lines if not (url in ln and ln.lstrip().startswith("-"))]
    if len(neu) != len(lines):
        _schreiben(p, "\n".join(neu))


def dossier_text(thema: str, basis: str = "") -> str:
    p = ZK / _rel(basis, f"Dossiers/{_slug(thema)}.md")
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------- Recall / Rueckblick ----------

def landkarte(maxchars: int = 7000, basis: str = "") -> str:
    teile = []
    d = ZK / _rel(basis, "Dossiers")
    if d.is_dir():
        for f in sorted(d.glob("*.md")):
            try:
                t = f.read_text(encoding="utf-8")
            except Exception:                                     # noqa: BLE001
                continue
            titel = t.splitlines()[0].lstrip("# ").strip() if t else f.stem
            stand = _dossier_abschnitt(t, "Stand")
            offen = _dossier_abschnitt(t, "Offen")
            ziel = _rel(basis, f"Dossiers/{f.stem}")
            blk = f"## {titel}  (→ [[{ziel}]])"
            if stand:
                blk += f"\nStand: {stand}"
            if offen:
                blk += f"\nOffen:\n{offen}"
            teile.append(blk)
    erk = erkenntnis_text(40, basis=basis)
    karte = ""
    if teile:
        karte += "DOSSIERS (Themen mit Stand + offenen Fragen):\n\n" + "\n\n".join(teile)
    if erk:
        label = "ROADMAP" if _ist_projekt(basis) else "ERKENNTNIS-INDEX"
        karte += f"\n\n---\n\n{label}:\n" + erk
    return karte.strip()[:maxchars]


def _erster_satz(text: str, maxchars: int = 200) -> str:
    t = " ".join((text or "").split())
    if not t:
        return ""
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    return s[:maxchars]


def karte_saetze(basis: str = "", maxchars: int = 2500) -> str:
    """Kompakte Dossier-Karte fuers Gespraech: je Dossier eine Zeile
    „Titel: ein Satz zum Stand" (Rueckfall: Untertitel-Zeile)."""
    d = ZK / _rel(basis, "Dossiers")
    if not d.is_dir():
        return ""
    zeilen = []
    for f in sorted(d.glob("*.md")):
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            continue
        titel = t.splitlines()[0].lstrip("# ").strip() if t else f.stem
        satz = _erster_satz(_dossier_abschnitt(t, "Stand"))
        if satz.startswith("#"):
            satz = ""
        if not satz:
            for ln in t.splitlines()[1:]:
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    satz = _erster_satz(ln)
                    break
        if satz == "Themen-Dossier.":
            satz = ""
        zeilen.append(f"- {titel}: {satz}" if satz else f"- {titel}")
    return "\n".join(zeilen)[:maxchars]


def zettel_thema_aufloesen(thema: str, basis: str = "") -> str:
    """Findet zum frei formulierten Thema das bestehende Dossier ('' wenn keins)."""
    s = _slug(thema)
    if (ZK / _rel(basis, f"Dossiers/{s}.md")).exists():
        return thema
    for name in existing_dossiers(basis=basis):
        ns = _slug(name)
        if ns == s or s in ns or ns in s:
            return name
    return ""


def zettel_material(thema: str, basis: str = "", maxchars: int = 9000) -> str:
    """Diskussionsgrundlage zum Thema: Dossier-Titelseite + verlinkte Journal-Eintraege."""
    treffer = zettel_thema_aufloesen(thema, basis=basis)
    if not treffer:
        return ""
    mat = (dossier_text(treffer, basis=basis) or "").strip()
    jt = dossier_journal_texts(treffer, basis=basis)
    if jt.strip():
        mat += "\n\n=== ZUGEHÖRIGE JOURNAL-EINTRÄGE ===\n\n" + jt.strip()
    return mat[:maxchars]


def fortschritt_material(maxchars: int = 7000, basis: str = "") -> str:
    teile = []
    d = ZK / _rel(basis, "Dossiers")
    if d.is_dir():
        for f in sorted(d.glob("*.md")):
            try:
                t = f.read_text(encoding="utf-8")
            except Exception:                                     # noqa: BLE001
                continue
            titel = t.splitlines()[0].lstrip("# ").strip() if t else f.stem
            stand = _dossier_abschnitt(t, "Stand")
            ges = _dossier_abschnitt(t, "Gesichert")
            if stand or ges:
                blk = f"## {titel}"
                if stand:
                    blk += f"\nStand: {stand}"
                if ges:
                    blk += f"\nGesichert:\n{ges}"
                teile.append(blk)
    erk = erkenntnis_text(60, basis=basis)
    m = ""
    if teile:
        m += "DOSSIERS:\n\n" + "\n\n".join(teile)
    if erk:
        m += "\n\n---\n\n" + ("ROADMAP:\n" if _ist_projekt(basis) else "ERKENNTNIS-INDEX:\n") + erk
    return m.strip()[:maxchars]


def journal_recent(tage: int = 3, maxchars: int = 4000, basis: str = "") -> str:
    base = ZK / _rel(basis, "Journal")
    if not base.is_dir():
        return ""
    files = sorted(base.glob("*/*.md"))
    txt = ""
    for f in files[-tage:]:
        try:
            txt += f.read_text(encoding="utf-8") + "\n"
        except Exception:                                         # noqa: BLE001
            pass
    return txt[-maxchars:]


# ---------- Schlagwort-Register (mittlere Abrufebene) ----------

REGISTER_HEADER = ("# Schlagwort-Register\n\nJe Schlagwort die Journal-Einträge, "
                   "die es tragen. Wird vom Sekretär bei jeder Ablage gepflegt.\n")


def register_eintragen(schlagworte, journal_page: str, basis: str = "") -> None:
    """Pflegt Schlagwort-Register.md: je Schlagwort eine Zeile mit Links auf die
    tragenden Journal-Eintraege. Idempotent, best effort."""
    tags = []
    for w in (schlagworte or []):
        s = _slug(str(w).lstrip("#"))
        if s and s != "ohne-titel" and s not in tags:
            tags.append(s)
    if not (tags and journal_page):
        return
    p = ZK / _rel(basis, "Schlagwort-Register.md")
    try:
        text = p.read_text(encoding="utf-8") if p.exists() else REGISTER_HEADER
    except Exception:                                             # noqa: BLE001
        text = REGISTER_HEADER
    lines = text.split("\n")
    link = f"[[{journal_page}]]"
    for tag in tags:
        pref = f"- #{tag}:"
        for i, ln in enumerate(lines):
            if ln.startswith(pref):
                if link not in ln:
                    lines[i] = ln.rstrip() + " " + link
                break
        else:
            lines.append(pref + " " + link)
    _schreiben(p, "\n".join(lines).rstrip() + "\n")


def register_treffer(begriffe, basis: str = "", max_seiten: int = 6) -> list:
    """Unscharfe Schlagwort-Suche im Register -> Journal-Seitennamen (neueste zuletzt)."""
    p = ZK / _rel(basis, "Schlagwort-Register.md")
    if not p.exists():
        return []
    woerter = []
    for b in (begriffe or []):
        s = _slug(str(b).lstrip("#"))
        if s and s != "ohne-titel" and len(s) >= 3:
            woerter.append(s)
    if not woerter:
        return []
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:                                             # noqa: BLE001
        return []
    seiten = []
    for ln in text.split("\n"):
        m = re.match(r"- #([\w-]+):(.*)", ln)
        if not m:
            continue
        tag = m.group(1)
        if not any(w == tag or w in tag or tag in w for w in woerter):
            continue
        for pg in re.findall(r"\[\[([^\]|]+)\]\]", m.group(2)):
            if pg in seiten:
                seiten.remove(pg)
            seiten.append(pg)
    return seiten[-max_seiten:]


def register_material(begriffe, basis: str = "", maxchars: int = 7000) -> str:
    """Journal-Eintraege zu Schlagwort-Treffern als Textblock ('' wenn nichts)."""
    out = []
    for pg in register_treffer(begriffe, basis=basis):
        f = ZK / (pg + ".md")
        if f.exists():
            try:
                out.append(f.read_text(encoding="utf-8"))
            except Exception:                                     # noqa: BLE001
                pass
    return ("\n\n---\n\n".join(out))[-maxchars:]


def zettel_nachschlagen(thema: str, basis: str = "", maxchars: int = 9000):
    """Gemeinsamer Nachschlage-Einstieg: erst Dossier-Treffer, sonst
    Schlagwort-Register. -> (anzeige_name, material) oder ('', '')."""
    treffer = zettel_thema_aufloesen(thema, basis=basis)
    if treffer:
        return treffer, zettel_material(treffer, basis=basis, maxchars=maxchars)
    begriffe = re.split(r"[\s,;/]+", (thema or "").strip())
    mat = register_material(begriffe, basis=basis, maxchars=maxchars)
    if mat:
        return f"Schlagwort-Treffer zu „{thema}“", mat
    return "", ""


# ---------- Projekte (4. Regal) ----------

def projekt_basis(slug: str) -> str:
    return f"Projekte/{_slug(slug)}"


def projekt_liste() -> list:
    """[(slug, titel)] der bestehenden Projekte."""
    d = ZK / "Projekte"
    if not d.is_dir():
        return []
    out = []
    for sub in sorted(d.iterdir()):
        if not sub.is_dir():
            continue
        rm = sub / "Roadmap.md"
        titel = sub.name
        if rm.exists():
            try:
                titel = rm.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip() or sub.name
            except Exception:                                     # noqa: BLE001
                pass
        out.append((sub.name, titel))
    return out


def _projekt_skelett(basis: str, name: str) -> None:
    """Macht die Projekt-Uebersichten klickbar: Dossiers.md/Journal.md mit Kopf
    und Navigationszeile in der Roadmap. Idempotent."""
    rm = ZK / basis / "Roadmap.md"
    titel = name
    if rm.exists():
        try:
            titel = (rm.read_text(encoding="utf-8").splitlines()[0]
                     .lstrip("# ").strip() or name)
        except Exception:                                         # noqa: BLE001
            pass
    koepfe = (
        ("Dossiers.md", f"# Dossiers — {titel}\n\nTeilaspekt-Dossiers dieses "
         "Projekts: Stand / Gesichert / Offen / Ressourcen / Besuchs-Log.\n"),
        ("Journal.md", f"# Journal — {titel}\n\nGedankenstrom dieses Projekts, "
         "append-only — je Tag eine Seite.\n"),
    )
    for datei, kopf in koepfe:
        p = ZK / basis / datei
        try:
            alt = p.read_text(encoding="utf-8") if p.exists() else ""
        except Exception:                                         # noqa: BLE001
            continue
        if not alt.lstrip().startswith("# "):
            _schreiben(p, kopf + ("\n" + alt.lstrip("\n") if alt.strip() else ""))
    if rm.exists():
        try:
            txt = rm.read_text(encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            return
        if (f"[[{basis}/Journal|" not in txt
                and f"[[{basis}/Journal]]" not in txt):
            nav = f"[[{basis}/Journal|Journal]] · [[{basis}/Dossiers|Dossiers]]"
            k = txt.find("\n## ")
            if k >= 0:
                txt = txt[:k] + f"\n{nav}\n" + txt[k:]
            else:
                txt = txt.rstrip("\n") + f"\n\n{nav}\n"
            _schreiben(rm, txt)


def journal_portieren(thema: str, projekt: str) -> str:
    """Traegt alle Journal-Abschnitte zu einem Thema WOERTLICH ins Journal eines
    Projekts. Quelltage bleiben unangetastet, das Projekt-Journal ist
    append-only, die Quittung nennt Zahlen. Gesucht wird ZUERST: ohne
    Fundstellen wird nichts angelegt und nichts geschrieben."""
    th = (thema or "").strip().lower()
    if not th:
        return "⚠️ Portieren: kein Thema erkannt."
    quelle_dir = ZK / "Journal"
    abschnitte = []
    for f in sorted(quelle_dir.glob("*/*.md")):
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            continue
        if th not in txt.lower():
            continue
        datum = f.stem
        teile = re.split(r"(?m)^## ", txt)
        getroffen = False
        for t in teile[1:]:
            if th in t.lower():
                kopf, _, rest = t.partition("\n")
                abschnitte.append((datum, kopf.strip(), rest.strip()))
                getroffen = True
        if not getroffen and th in teile[0].lower():
            zeilen = [z for z in teile[0].splitlines()
                      if not z.startswith("# ")]
            abschnitte.append((datum, "", "\n".join(zeilen).strip()))
    if not abschnitte:
        return ("🔍 Portieren: im Journal nichts zu „%s“ gefunden — nichts "
                "angelegt, nichts geschrieben." % thema)
    DECKEL = 40
    rest_hinweis = ""
    if len(abschnitte) > DECKEL:
        rest_hinweis = (" ⚠️ %d weitere Fundstellen NICHT portiert "
                        "(Deckel %d) — bei Bedarf Thema enger fassen."
                        % (len(abschnitte) - DECKEL, DECKEL))
        abschnitte = abschnitte[:DECKEL]
    neu_angelegt = not projekt_besteht(projekt)
    slug = projekt_anlegen(projekt)
    basis = projekt_basis(slug)
    bloecke, tage = [], []
    for datum, kopf, text in abschnitte:
        if datum not in tage:
            tage.append(datum)
        link = f"[[Journal/{datum[:4]}/{datum}]]"
        titelzeile = (f"**{kopf}** — {link}") if kopf else f"**{link}**"
        bloecke.append(titelzeile + "\n\n" + text)
    inhalt = ("Wörtlich portiert aus dem Journal (Quelltage unangetastet):\n\n"
              + "\n\n---\n\n".join(bloecke))
    journal_append(inhalt, quelle="portiert",
                   titel=f"Portiert: „{thema}“ aus dem Journal", basis=basis)
    q = ("📦 %d Abschnitt(e) aus %d Journaltag(en) nach %s/Journal portiert "
         "(%s).%s" % (len(abschnitte), len(tage), basis,
                      ", ".join(f"{t[8:10]}.{t[5:7]}." for t in tage),
                      rest_hinweis))
    if neu_angelegt:
        q += " Projekt **" + projekt + "** war neu und wurde angelegt."
    return q


def projekt_besteht(name: str) -> bool:
    """Gibt es dieses Projekt schon? (Roadmap-Skelett vorhanden)"""
    return (ZK / f"Projekte/{_slug(name)}" / "Roadmap.md").exists()


def projekt_anlegen(name: str) -> str:
    """Legt ein Projekt an (Roadmap-Skelett + Registrierung im Projekte-Regal)."""
    slug = _slug(name)
    basis = f"Projekte/{slug}"
    rm = ZK / basis / "Roadmap.md"
    if not rm.exists():
        _schreiben(rm,
                   f"# {name}\n\nProjekt-Roadmap — der Plan & die gesicherte Richtung. "
                   "Teilaspekte liegen in den Dossiers, der Gedankenstrom im Journal.\n\n"
                   "## Ziel\n\n## Nächste Schritte\n\n## Entscheidungen\n")
    _index_link("Projekte.md", basis + "/Roadmap", name, "Projekte")
    _projekt_skelett(basis, name)
    return slug


def reindex_links() -> None:
    base = ZK / "Journal"
    for f in sorted(base.glob("*/*.md")):
        _index_link("Journal.md", f"Journal/{f.parent.name}/{f.stem}", f.stem, "Tage")
    dd = ZK / "Dossiers"
    for f in sorted(dd.glob("*.md")):
        try:
            thema = f.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip() or f.stem
        except Exception:                                         # noqa: BLE001
            thema = f.stem
        _index_link("Dossiers.md", f"Dossiers/{f.stem}", thema, "Akten")


def reindex_register() -> int:
    n = 0
    for f in sorted((ZK / "Journal").glob("*/*.md")):
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            continue
        page = pagename(f)
        for m in re.finditer(r"^Schlagworte:\s*(.+)$", txt, re.M):
            tags = re.findall(r"#([\w-]+)", m.group(1))
            if tags:
                register_eintragen(tags, page)
                n += 1
    return n


# ---------- Ablage (nach destille.zettelkasten) ----------

KREIS_INSTR = (
    "Hier sind die letzten Male, die zum selben Thema abgelegt wurde "
    "(älteste zuerst). Beurteile NÜCHTERN: gibt es ECHTEN Fortschritt (ein "
    "Delta) oder dreht es sich im Kreis? Erste Zeile: genau ein Wort, DELTA "
    "oder KREIS. Bei KREIS folgen zwei Zeilen: Zeile 2 = EIN Satz, der konkret "
    "benennt, WAS sich wiederholt — der Kern des Kreises, ohne Vorwurf. "
    "Zeile 3 = GENAU EIN konkreter Ausweg — präzise Was-Frage, kleiner "
    "nächster Schritt, oder bewusstes Parken.")

STAND_INSTR = (
    "Fasse den aktuellen STAND zum Thema zusammen — wo steht es, was ist "
    "gesichert, was ist offen? Nutze NUR die folgenden Notizen. Knapp, als "
    "Wiedereinstieg. Ist etwas offen, benenne EINEN kleinen nächsten Schritt. "
    "Kein Vorspann.")


def _ort(basis: str) -> str:
    if not basis:
        return "Journal"
    for sl, ti in projekt_liste():
        if basis.endswith("/" + sl):
            return ti
    return basis


def _kreis_check(thema: str, ergebnis, basis: str = "") -> str:
    """Ein Aufruf je Thema und Ablage-Vorgang. Gibt die Kreis-Pruefung als Text
    zurueck, sobald kreis_schwelle Ablagen beisammen sind, sonst ''."""
    texte = [ergebnis] if isinstance(ergebnis, str) else [t for t in ergebnis if t]
    if not texte:
        return ""
    schwelle = int(_zahl("kreis_schwelle", 3))
    key = f"{basis}::{thema}" if basis else thema
    datei = STATE / "kreis_state.json"
    try:
        state = json.loads(datei.read_text(encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        state = {}
    hist = state.get(key, [])
    hist.extend(texte)
    hist = hist[-schwelle:]
    state[key] = hist
    try:
        _schreiben(datei, json.dumps(state, ensure_ascii=False))
    except Exception:                                             # noqa: BLE001
        pass
    if len(hist) < schwelle:
        return ""
    return (f"🌀 Kreis-Prüfung für **{thema}** — jetzt im Chat urteilen.\n\n"
            f"{KREIS_INSTR}\n\n" + "\n\n---\n\n".join(hist) + "\n\n"
            f"Bei KREIS dem Nutzer melden: „🌀 Mir fällt auf: Beim Thema **{thema}** "
            "drehen wir uns gerade eher im Kreis als vorwärts. <Zeile 2> "
            "„Reflexion ohne Handlung ist Rumination.“ Ein Ausweg: <Zeile 3>“. "
            "Bei DELTA nichts melden.")


def ablegen(daten, eingabe=None):
    """Legt ab wie ::zettelkasten der Schreibstube. -> (anzahl, meldungen)."""
    if not isinstance(daten, dict):
        raise ValueError("Eingabe ist kein JSON-Objekt")
    projekt = str(daten.get("projekt") or "").strip()
    basis = projekt_basis(projekt_anlegen(projekt)) if projekt else ""
    quelle = str(daten.get("quelle") or "live").strip() or "live"

    abgelegt = []
    for e in (daten.get("eintraege") or [])[:6]:
        if not isinstance(e, dict):
            continue
        thema = re.sub(r'[."\'`*]', "", str(e.get("thema") or "")).strip()[:60] \
            or "Sonstiges"
        titel = str(e.get("titel") or thema).strip()[:80] or thema
        text = str(e.get("text") or "").strip()
        if not text:
            continue
        schlag = [str(x).strip() for x in (e.get("schlagworte") or [])
                  if str(x).strip()][:5]
        p = journal_append(text, quelle=quelle, titel=titel, schlagworte=schlag,
                           basis=basis)
        dossier_link(thema, pagename(p), schlag, basis=basis)
        try:
            register_eintragen(schlag, pagename(p), basis=basis)
        except Exception:                                         # noqa: BLE001
            pass
        abgelegt.append((p, titel, thema, text))
    if not abgelegt:
        return 0, ["⚠️ Da kam nichts Ablegbares heraus — nichts geschrieben."]

    meldungen = []
    dossiers = daten.get("dossiers") or {}
    if isinstance(dossiers, dict):
        for thema, sek in dossiers.items():
            if not isinstance(sek, dict):
                continue
            dossier_ensure(str(thema), basis)
            dossier_write_sections(str(thema), str(sek.get("stand") or ""),
                                   str(sek.get("gesichert") or ""),
                                   str(sek.get("offen") or ""), basis=basis)
    ressourcen = daten.get("ressourcen") or {}
    if isinstance(ressourcen, dict):
        for thema, zeilen in ressourcen.items():
            dossier_ensure(str(thema), basis)
            for z in (zeilen if isinstance(zeilen, list) else [zeilen]):
                if str(z).strip():
                    dossier_ressource(str(thema), str(z), basis=basis)

    neu = []
    if not basis:
        for z in (daten.get("erkenntnisse") or [])[:2]:
            z = " ".join(str(z).split()).strip('"').strip()
            if z:
                erkenntnis_append(z, basis=basis)
                neu.append(z)

    wo = f" [{_ort(basis)}]" if basis else ""
    if len(abgelegt) == 1:
        p, _ti, thema, _x = abgelegt[0]
        meldungen.append(f"📓 Abgelegt: Journal **{p.stem}** → Dossier **{thema}** "
                         f"aktualisiert{wo}.")
    else:
        zeilen = "\n".join(f"• **{ti}** → Dossier **{th}**"
                           for _p, ti, th, _x in abgelegt)
        meldungen.append(f"📓 {len(abgelegt)} Einträge abgelegt{wo}:\n{zeilen}")
    if neu:
        meldungen.append("💡 In den Erkenntnis-Index übernommen:\n"
                         + "\n".join("• „" + z + "“" for z in neu))

    je_thema = {}
    for _p, _ti, th, text in abgelegt:
        je_thema.setdefault(th, []).append(text)
    for th, texte in je_thema.items():
        k = _kreis_check(th, texte, basis=basis)
        if k:
            meldungen.append(k)

    if eingabe:
        try:
            ep = Path(eingabe).resolve()
            eing = (ZK / EINGANG).resolve()
            if eing in ep.parents:
                ziel = eing / "abgelegt" / ep.name
                _ensure_dir(ziel.parent)
                os.replace(ep, ziel)
        except Exception:                                         # noqa: BLE001
            pass
    return len(abgelegt), meldungen


def stand(thema: str = "", basis: str = "") -> str:
    """Material fuer den Wiedereinstieg (nach destille.stand, ohne Modellaufruf)."""
    thema = (thema or "").strip()
    if not thema:
        doss = existing_dossiers(basis=basis)
        refs = open_reflexionen(basis=basis)
        teile = ["Offene Themen: " + (", ".join(doss) if doss else "noch keine Dossiers")]
        if refs:
            teile.append("Offene Reflexionen: "
                         + "; ".join(f"{d} — {t[:50]}" for d, t in refs))
        return ("🧭 " + "\n".join(teile) + "\n\n(„zettel.py stand <thema>“ zieht den "
                "Stand zu einem Thema zusammen.)")
    dt = dossier_text(thema, basis=basis)
    jr = journal_recent(basis=basis)
    quelle = ((dt or "") + "\n\n" + (jr or "")).strip()
    if not quelle:
        return f"Zu „{thema}“ habe ich hier noch nichts gefunden."
    return f"{STAND_INSTR}\n\nThema: {thema}\n\n{quelle}"


# ---------- Suche und Lesen ----------

def volltext_treffer(begriffe, basis: str = "", bekannt=(), max_seiten: int = 0) -> list:
    """Zusatz gegenueber Ferradea: Seiten, in denen ein Begriff woertlich steht."""
    max_seiten = max_seiten or int(_zahl("zettel_volltext_seiten", 10))
    woerter = [str(b).strip().lower() for b in (begriffe or []) if len(str(b).strip()) >= 3]
    wurzel = ZK / basis if basis else ZK
    if not woerter or not wurzel.is_dir():
        return []
    treffer = []
    for f in sorted(wurzel.rglob("*.md"), reverse=True):
        name = pagename(f)
        if (name.startswith((ARCHIV + "/", EINGANG + "/")) or name in bekannt
                or name.split("/")[-1] == "Schlagwort-Register"):
            continue
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            continue
        if not any(w in txt.lower() for w in woerter):
            continue
        zeile = next((z.strip() for z in txt.splitlines()
                      if any(w in z.lower() for w in woerter)), "")
        treffer.append((name, zeile[:140]))
        if len(treffer) >= max_seiten:
            break
    return treffer


def suche(begriffe, basis: str = "") -> str:
    begriffe = [str(b) for b in (begriffe or []) if str(b).strip()]
    thema = " ".join(begriffe)
    zeilen, gesehen = [], set()

    dossier = ""
    for kandidat in [thema] + begriffe:
        if len(_slug(kandidat)) >= 3:
            dossier = zettel_thema_aufloesen(kandidat, basis=basis)
            if dossier:
                break
    if dossier:
        seite = _rel(basis, f"Dossiers/{_slug(dossier)}")
        satz = _erster_satz(_dossier_abschnitt(dossier_text(dossier, basis=basis), "Stand"))
        if satz.startswith("#"):
            satz = ""
        zeilen.append(f"Dossier   {seite}" + (f" — {satz}" if satz else ""))
        gesehen.add(seite)

    for pg in reversed(register_treffer(begriffe, basis=basis,
                                        max_seiten=int(_zahl("zettel_register_seiten", 6)))):
        if pg not in gesehen:
            zeilen.append(f"Journal   {pg} — Schlagwort-Treffer")
            gesehen.add(pg)

    for name, zeile in volltext_treffer(begriffe, basis=basis, bekannt=gesehen):
        zeilen.append(f"Volltext  {name} — {zeile}")
        gesehen.add(name)

    if not zeilen:
        doss = existing_dossiers(basis=basis)
        return (f"Kein Treffer zu „{thema}“. Vorhandene Dossiers: "
                + (", ".join(doss) if doss else "noch keine"))
    return (f"Treffer zu „{thema}“ ({len(zeilen)}):\n" + "\n".join(zeilen)
            + "\n\nGanz lesen: zettel.py lies <seite>")


def lies(ziel: str, basis: str = "") -> str:
    """Eine Seite im Ganzen, sonst das Material zum Thema."""
    ziel = (ziel or "").strip().strip("[]")
    if ziel.endswith(".md"):
        ziel = ziel[:-3]
    kandidaten = [ziel] + ([_rel(basis, ziel)] if basis else [])
    wurzel = ZK.resolve()
    for k in kandidaten:
        f = ZK / (k + ".md")
        try:
            if f.is_file() and wurzel in f.resolve().parents:
                return f"=== {k} ===\n\n" + f.read_text(encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            continue
    name, mat = zettel_nachschlagen(ziel, basis=basis,
                                    maxchars=int(_zahl("zettel_material_max", 9000)))
    if mat:
        return f"=== {name} ===\n\n{mat}"
    return f"Nichts gefunden zu „{ziel}“. Erst suchen: zettel.py suche <begriffe>"


def karte_text(basis: str = "", maxchars: int = 0) -> str:
    """Karte fuer den Kontext: je Dossier ein Satz, dazu die juengsten Erkenntnisse."""
    maxchars = maxchars or int(_zahl("karte_max_zeichen", 2500))
    k = karte_saetze(basis=basis, maxchars=maxchars)
    erk = erkenntnis_text(limit=int(_zahl("erkenntnisse_in_karte", 15)), basis=basis)
    teile = []
    if k:
        teile.append("Dossiers:\n" + k)
    if erk:
        teile.append(("Roadmap" if _ist_projekt(basis) else "Erkenntnis-Index")
                     + " (jüngste):\n" + erk)
    return "\n\n".join(teile)


# ---------- Hausmeister (nach journal_hausmeister) ----------

WURZEL_NAMEN = {"index", "Journal", "Dossiers", "Projekte", "Erkenntnis-Index",
                "Reflexionen", "Schlagwort-Register"}
WURZEL_SUFFIX = ("/Journal", "/Dossiers", "/Roadmap", "/Reflexionen",
                 "/Schlagwort-Register")
_LINK_RE = re.compile(r"\[\[([^\]|#]+)")


def _seiten():
    """Alle .md-Seiten als Seitennamen, ohne _Archiv und _eingang."""
    out = {}
    if not ZK.is_dir():
        return out
    for f in ZK.rglob("*.md"):
        rel = f.relative_to(ZK).as_posix()
        if rel.startswith(ARCHIV + "/") or rel.startswith(EINGANG + "/"):
            continue
        out[rel[:-3]] = f
    return out


def _links(f):
    try:
        txt = f.read_text(encoding="utf-8")
    except Exception:                                             # noqa: BLE001
        return set()
    return {l.strip().strip("/") for l in _LINK_RE.findall(txt)}


def _ist_wurzel(name):
    base = name.rsplit("/", 1)[-1]
    return (base in WURZEL_NAMEN or name in WURZEL_NAMEN
            or any(name.endswith(s) for s in WURZEL_SUFFIX))


def _erreichbar(seiten):
    graph = {name: _links(f) for name, f in seiten.items()}
    besucht = set()
    stack = [n for n in seiten if _ist_wurzel(n)]
    while stack:
        n = stack.pop()
        if n in besucht:
            continue
        besucht.add(n)
        for ziel in graph.get(n, ()):
            if ziel in seiten and ziel not in besucht:
                stack.append(ziel)
    return besucht


def waisen(seiten):
    err = _erreichbar(seiten)
    return sorted(n for n in seiten if n not in err and not _ist_wurzel(n))


def _archivierbar(name):
    """Journal-Strom ist heilig — nie archivieren."""
    return not (name.startswith("Journal/") or "/Journal/" in name)


def _archivieren(waisenliste, seiten):
    tag = _now().strftime("%Y-%m-%d")
    eintraege = []
    for i, name in enumerate(waisenliste, 1):
        original = name + ".md"
        archiv = ARCHIV + "/" + tag + "/" + original
        ziel = ZK / archiv
        _ensure_dir(ziel.parent)
        os.replace(seiten[name], ziel)
        eintraege.append({"id": i, "seite": name, "original": original,
                          "archiv": archiv, "aktion": "behalten"})
    if eintraege:
        _schreiben(ZK / ARCHIV / tag / "archiviert.json",
                   json.dumps(eintraege, ensure_ascii=False, indent=2))
    return eintraege


def hausmeister(archivieren: bool = False) -> str:
    seiten = _seiten()
    w = [n for n in waisen(seiten) if _archivierbar(n)]
    if not w:
        return "Hausmeister: keine verwaisten Seiten."
    if not archivieren:
        return ("Hausmeister: %d verwaiste Seite(n):\n" % len(w)
                + "\n".join("- " + n for n in w)
                + "\n\nArchivieren (verschiebt nach %s/<tag>/): "
                  "zettel.py hausmeister --archivieren" % ARCHIV)
    e = _archivieren(w, seiten)
    return "Hausmeister: %d Seite(n) nach %s/%s/ verschoben." % (
        len(e), ARCHIV, _now().strftime("%Y-%m-%d"))


# ---------- Aufruf ----------

def _textdatei(pfad):
    with open(pfad, "r", encoding="utf-8-sig") as f:
        return f.read()


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass
    gemeinsam = argparse.ArgumentParser(add_help=False)
    gemeinsam.add_argument("--projekt", default="")
    p = argparse.ArgumentParser(prog="zettel.py", description="Zettelkasten des Projekts")
    sub = p.add_subparsers(dest="befehl")
    a = sub.add_parser("ablegen", parents=[gemeinsam])
    a.add_argument("datei")
    s = sub.add_parser("suche", parents=[gemeinsam])
    s.add_argument("begriffe", nargs="+")
    li = sub.add_parser("lies", parents=[gemeinsam])
    li.add_argument("ziel", nargs="+")
    st = sub.add_parser("stand", parents=[gemeinsam])
    st.add_argument("thema", nargs="*")
    for name in ("karte", "landkarte", "fortschritt", "reflexionen"):
        sub.add_parser(name, parents=[gemeinsam])
    sub.add_parser("projekte")
    r = sub.add_parser("reflexion", parents=[gemeinsam])
    r.add_argument("datum")
    r.add_argument("datei")
    ro = sub.add_parser("roh", parents=[gemeinsam])
    ro.add_argument("datei")
    po = sub.add_parser("portieren")
    po.add_argument("thema")
    po.add_argument("projekt_name")
    h = sub.add_parser("hausmeister")
    h.add_argument("--archivieren", action="store_true")
    sub.add_parser("reindex")
    args = p.parse_args(argv)
    if not args.befehl:
        p.print_help()
        return 2

    basis = projekt_basis(args.projekt) if getattr(args, "projekt", "") else ""

    if args.befehl == "ablegen":
        try:
            daten = json.loads(_textdatei(args.datei))
            n, meldungen = ablegen(daten, eingabe=args.datei)
        except Exception as ex:                                   # noqa: BLE001
            print("⚠️ Ablage gescheitert: %s — nichts oder nur teilweise geschrieben." % ex)
            return 1
        print("\n\n".join(meldungen))
        return 0 if n else 1
    if args.befehl == "suche":
        print(suche(args.begriffe, basis=basis))
        return 0
    if args.befehl == "lies":
        print(lies(" ".join(args.ziel), basis=basis))
        return 0
    if args.befehl == "stand":
        print(stand(" ".join(args.thema), basis=basis))
        return 0
    if args.befehl == "karte":
        print(karte_text(basis=basis) or "Der Zettelkasten ist noch leer.")
        return 0
    if args.befehl == "landkarte":
        print(landkarte(basis=basis) or "Der Zettelkasten ist noch leer.")
        return 0
    if args.befehl == "fortschritt":
        print(fortschritt_material(basis=basis) or "Noch kein Fortschritt abgelegt.")
        return 0
    if args.befehl == "projekte":
        liste = projekt_liste()
        print("\n".join("%s — %s" % (sl, ti) for sl, ti in liste) or "Keine Projekte.")
        return 0
    if args.befehl == "reflexion":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.datum):
            print("Datum bitte als JJJJ-MM-TT.")
            return 1
        reflexion_append(_textdatei(args.datei), args.datum, basis=basis)
        print(f"🗓️ Reflexion für {args.datum} abgelegt.")
        return 0
    if args.befehl == "reflexionen":
        refs = open_reflexionen(basis=basis)
        print("\n".join(f"{d} — {t}" for d, t in refs) or "Keine offenen Reflexionen.")
        return 0
    if args.befehl == "roh":
        text = _textdatei(args.datei)
        if not text.strip():
            print("roh braucht Text — den lege ich dann unverändert ab.")
            return 1
        pfad = rawpush(text.strip(), basis=basis)
        print(f"📥 1:1 im Journal **{pfad.stem}** abgelegt.")
        return 0
    if args.befehl == "portieren":
        print(journal_portieren(args.thema, args.projekt_name))
        return 0
    if args.befehl == "hausmeister":
        print(hausmeister(archivieren=args.archivieren))
        return 0
    if args.befehl == "reindex":
        reindex_links()
        n = reindex_register()
        print("Übersichts-Links reindexiert.")
        print(f"Schlagwort-Register aus {n} Eintrags-Taglines aufgebaut.")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
