#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""installieren.py — das Paket in ein Projekt installieren oder dort ersetzen.

Laeuft aus dem entpackten Paket oder aus dem Repository heraus.

Aufrufe:
    installieren.py --manifest                          PRUEFSUMMEN.json neu schreiben
    installieren.py --projekt P --pruefen               zeigen, was geschaehe
    installieren.py --projekt P --erstinstallation      Projekt ohne installiert.json
    installieren.py --projekt P --update                bestehende Installation ersetzen
Optionen:
    --quelle <paketordner>   Vorgabe: der Ordner dieser Datei
    --einstellungen          fehlende Hook-Eintraege in .claude/settings.json ergaenzen
    --ohne-abnahme           Pruefstand nach dem Schreiben auslassen (nur Proben)
Exit: 0 installiert oder nichts zu tun · 1 abgebrochen oder zurueckgerollt

Was wohin kommt:
    hooks/<datei>    -> .claude/hooks/<datei>       (hooks.json nicht)
    skills/<pfad>    -> .claude/skills/<pfad>
    agents/<datei>   -> .claude/agents/<datei>
    alles andere     -> .claude/infinite-accuracy/paket/<pfad>
Ausnahmen je Projekt: .claude/infinite-accuracy/installation.json
    {"ausnahmen": ["skills/einrichten"]}

Begruendungen und Fallen: skills/kaskade/doku/aktualisierung.md
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
MANIFEST = "PRUEFSUMMEN.json"
VERSION_DATEI = "version.json"
PLUGIN_DATEI = ".claude-plugin/plugin.json"
META = ".claude/infinite-accuracy"
NICHT_INSTALLIEREN = ("hooks/hooks.json",)
SPERRE_MINUTEN = 30
HOOK_BEFEHL = (
    "python -c \"import os,sys,runpy;h=sys.argv[1];"
    "k=[os.path.join(os.getcwd(),*([os.pardir]*i),'.claude','hooks',h) for i in range(8)];"
    "t=[x for x in k if os.path.isfile(x)];sys.argv[:]=t[:1];"
    "runpy.run_path(t[0],run_name='__main__') if t else sys.exit('Hook nicht gefunden: '+h)\" "
)


def _abs(wurzel, rel):
    return os.path.join(wurzel, *rel.split("/"))


def _tupel(text):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def sha256(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def paket_dateien(quelle):
    raus = []
    for wurzel, dirs, files in os.walk(quelle):
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", ".git"))
        for name in sorted(files):
            if name.endswith(".pyc") or name.endswith(".ia-neu"):
                continue
            rel = os.path.relpath(os.path.join(wurzel, name), quelle).replace(os.sep, "/")
            if rel != MANIFEST:
                raus.append(rel)
    return raus


def _json_lesen(pfad):
    with open(pfad, "r", encoding="utf-8") as f:
        return json.load(f)


def _json_schreiben(pfad, daten):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    tmp = pfad + ".ia-neu"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, pfad)


def _kopieren(quelle, ziel):
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    shutil.copy2(quelle, ziel)


def _kopieren_atomar(quelle, ziel):
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    tmp = ziel + ".ia-neu"
    shutil.copyfile(quelle, tmp)
    os.replace(tmp, ziel)


def version_lesen(quelle):
    return str(_json_lesen(_abs(quelle, VERSION_DATEI)).get("version") or "")


def manifest_schreiben(quelle):
    version = version_lesen(quelle)
    plugin = _json_lesen(_abs(quelle, PLUGIN_DATEI)).get("version")
    if plugin != version:
        raise ValueError("plugin.json traegt %s, version.json %s" % (plugin, version))
    vj_pfad = _abs(quelle, VERSION_DATEI)
    vj = _json_lesen(vj_pfad)
    groesse = sum(os.path.getsize(_abs(quelle, r)) for r in paket_dateien(quelle)
                  if r != VERSION_DATEI)
    if vj.get("groesse_bytes") != groesse:
        vj["groesse_bytes"] = groesse
        _json_schreiben(vj_pfad, vj)
    dateien = {}
    for rel in paket_dateien(quelle):
        pfad = _abs(quelle, rel)
        dateien[rel] = {"sha256": sha256(pfad), "bytes": os.path.getsize(pfad)}
    _json_schreiben(_abs(quelle, MANIFEST), {"version": version, "dateien": dateien})
    return len(dateien)


def manifest_pruefen(quelle):
    """Liste der Abweichungen; leer = Paket vollstaendig und unveraendert."""
    pfad = _abs(quelle, MANIFEST)
    if not os.path.isfile(pfad):
        return ["PRUEFSUMMEN.json fehlt"]
    try:
        m = _json_lesen(pfad)
        version = version_lesen(quelle)
    except Exception as ex:                                       # noqa: BLE001
        return ["Pruefsummen oder version.json unlesbar: %s" % ex]
    fehler = []
    if m.get("version") != version:
        fehler.append("Pruefsummen gelten fuer %s, version.json sagt %s"
                      % (m.get("version"), version))
    soll = m.get("dateien") or {}
    for rel, info in sorted(soll.items()):
        p = _abs(quelle, rel)
        if not os.path.isfile(p):
            fehler.append("fehlt: %s" % rel)
        elif sha256(p) != (info or {}).get("sha256"):
            fehler.append("abweichend: %s" % rel)
    for rel in sorted(set(paket_dateien(quelle)) - set(soll)):
        fehler.append("nicht verzeichnet: %s" % rel)
    return fehler


def ziel_rel(rel):
    kopf, _, rest = rel.partition("/")
    if kopf == "hooks":
        return ".claude/hooks/" + rest
    if kopf in ("skills", "agents"):
        return ".claude/" + rel
    return META + "/paket/" + rel


def ausnahmen_lesen(projekt):
    try:
        d = _json_lesen(_abs(projekt, META + "/installation.json"))
        return [str(x).strip("/") for x in (d.get("ausnahmen") or []) if str(x).strip()]
    except Exception:                                             # noqa: BLE001
        return []


def _ausgenommen(rel, ausnahmen):
    return rel in NICHT_INSTALLIEREN or any(
        rel == a or rel.startswith(a + "/") for a in ausnahmen)


def planen(quelle, projekt, ausnahmen):
    plan = []
    for rel in paket_dateien(quelle):
        if _ausgenommen(rel, ausnahmen):
            continue
        ziel = ziel_rel(rel)
        zabs = _abs(projekt, ziel)
        qabs = _abs(quelle, rel)
        qsha = sha256(qabs)
        if not os.path.exists(zabs):
            art = "neu"
        elif sha256(zabs) == qsha:
            art = "gleich"
        else:
            art = "anders"
        plan.append({"rel": rel, "ziel": ziel, "abs": zabs, "quelle": qabs,
                     "sha": qsha, "art": art})
    return plan


def installiert_lesen(projekt):
    try:
        d = _json_lesen(_abs(projekt, META + "/installiert.json"))
        return d if isinstance(d, dict) else None
    except Exception:                                             # noqa: BLE001
        return None


def hooks_soll(quelle):
    try:
        d = _json_lesen(_abs(quelle, "hooks/hooks.json"))
    except Exception:                                             # noqa: BLE001
        return {}
    soll = {}
    for ereignis, gruppen in (d.get("hooks") or {}).items():
        for gruppe in gruppen:
            for h in gruppe.get("hooks", []):
                m = re.search(r"hooks/([\w.-]+\.py)", h.get("command", ""))
                if m:
                    soll.setdefault(ereignis, []).append((m.group(1), h.get("timeout", 60)))
    return soll


def einstellungen_fehlend(quelle, projekt):
    try:
        s = _json_lesen(_abs(projekt, ".claude/settings.json"))
    except Exception:                                             # noqa: BLE001
        s = {}
    haken = s.get("hooks") or {}
    fehlend = []
    for ereignis, eintraege in hooks_soll(quelle).items():
        befehle = [h.get("command", "") for g in (haken.get(ereignis) or [])
                   for h in g.get("hooks", [])]
        for datei, timeout in eintraege:
            if not any(datei in b for b in befehle):
                fehlend.append((ereignis, datei, timeout))
    return fehlend


def einstellungen_ergaenzen(projekt, fehlend, sicherung):
    pfad = _abs(projekt, ".claude/settings.json")
    s = {}
    if os.path.isfile(pfad):
        _kopieren(pfad, _abs(sicherung, ".claude/settings.json"))
        s = _json_lesen(pfad)
    haken = s.setdefault("hooks", {})
    for ereignis, datei, timeout in fehlend:
        haken.setdefault(ereignis, []).append(
            {"hooks": [{"type": "command", "command": HOOK_BEFEHL + datei,
                        "timeout": timeout}]})
    _json_schreiben(pfad, s)


def abnahme(projekt, hooks):
    """Pruefstand im Projekt und echter Import je Hook."""
    bericht, ok = [], True
    env = dict(os.environ, CLAUDE_PROJECT_DIR=projekt, PYTHONIOENCODING="utf-8")
    pruef = _abs(projekt, ".claude/skills/kaskade/pruefstand.py")
    if os.path.isfile(pruef):
        p = subprocess.run([sys.executable, "-X", "utf8", pruef], cwd=projekt, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           encoding="utf-8", errors="replace", timeout=900)
        zeilen = [z for z in p.stdout.splitlines()
                  if z.startswith(("Pruefprotokoll", "STATUS", "NICHT ERFUELLT"))]
        bericht += zeilen[-15:]
        ok = ok and p.returncode == 0
    else:
        bericht.append("pruefstand.py fehlt im Projekt")
        ok = False
    hookdir = _abs(projekt, ".claude/hooks")
    for name in sorted(set(hooks)):
        p = subprocess.run([sys.executable, "-X", "utf8", "-c",
                            "import sys; sys.path.insert(0, sys.argv[1]); import %s" % name[:-3],
                            hookdir], cwd=projekt, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                           timeout=60)
        if p.returncode != 0:
            ok = False
            bericht.append("Import %s scheitert: %s" % (name, (p.stderr or "").strip()[-200:]))
    if ok:
        bericht.append("Import aller %d Hooks: in Ordnung" % len(set(hooks)))
    return ok, bericht


def _sperren(projekt):
    pfad = _abs(projekt, META + "/state/installation.lock")
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    if os.path.exists(pfad) and time.time() - os.path.getmtime(pfad) < SPERRE_MINUTEN * 60:
        return None
    with open(pfad, "w") as f:
        f.write(str(os.getpid()))
    return pfad


def ausfuehren(quelle, projekt, modus, einstellungen=False, ohne_abnahme=False,
               ausgabe=print):
    quelle = os.path.abspath(quelle)
    projekt = os.path.abspath(projekt)
    if not os.path.isdir(_abs(projekt, ".claude")):
        ausgabe("ABGEBROCHEN — %s hat keinen .claude-Ordner." % projekt)
        return 1
    fehler = manifest_pruefen(quelle)
    if fehler:
        ausgabe("ABGEBROCHEN — Paket unvollstaendig oder veraendert:")
        for f in fehler[:20]:
            ausgabe("  " + f)
        return 1
    version = version_lesen(quelle)
    inst = installiert_lesen(projekt)
    if modus == "update" and not inst:
        ausgabe("ABGEBROCHEN — keine Installation gefunden (%s/installiert.json). "
                "Erstinstallation: --erstinstallation" % META)
        return 1
    if modus == "erstinstallation" and inst:
        ausgabe("ABGEBROCHEN — hier ist %s schon installiert. Ersetzen: --update"
                % inst.get("version"))
        return 1
    if inst and modus == "update":
        alt, neu = _tupel(inst.get("version")), _tupel(version)
        if alt and neu and neu < alt:
            ausgabe("ABGEBROCHEN — %s ist aelter als die installierte %s."
                    % (version, inst.get("version")))
            return 1

    plan = planen(quelle, projekt, ausnahmen_lesen(projekt))
    aufgezeichnet = (inst or {}).get("dateien") or {}
    ziele = {e["ziel"] for e in plan}
    veraendert, fremd, entfallen = [], [], []
    for e in plan:
        if e["art"] != "anders":
            continue
        alt = aufgezeichnet.get(e["ziel"])
        if alt is None:
            if modus == "update":
                fremd.append(e["ziel"])
        elif sha256(e["abs"]) != alt:
            veraendert.append(e["ziel"])
    for ziel, alt in sorted(aufgezeichnet.items()):
        zabs = _abs(projekt, ziel)
        if ziel in ziele or not os.path.isfile(zabs):
            continue
        if sha256(zabs) != alt:
            veraendert.append(ziel)
        else:
            entfallen.append(ziel)
    zahl = {a: sum(1 for e in plan if e["art"] == a) for a in ("neu", "anders", "gleich")}
    fehlend = einstellungen_fehlend(quelle, projekt)

    ausgabe("infinite-accuracy %s -> %s  (%s)"
            % ((inst or {}).get("version") or "nicht installiert", version, projekt))
    ausgabe("| neu | ersetzt | gleich | entfaellt |")
    ausgabe("|---:|---:|---:|---:|")
    ausgabe("| %d | %d | %d | %d |" % (zahl["neu"], zahl["anders"], zahl["gleich"],
                                       len(entfallen)))

    if modus == "pruefen":
        for e in plan:
            if e["art"] != "gleich":
                ausgabe("  %-8s %s" % (e["art"], e["ziel"]))
        for z in entfallen:
            ausgabe("  entfaellt %s" % z)
        for z in veraendert:
            ausgabe("  LOKAL VERAENDERT %s" % z)
        for z in fremd:
            ausgabe("  NICHT AUS DIESEM PAKET %s" % z)
        for ereignis, datei, _ in fehlend:
            ausgabe("  Einstellung fehlt: %s -> %s" % (ereignis, datei))
        return 0

    if veraendert or fremd:
        ausgabe("ABGEBROCHEN — seit der Installation veraendert oder nicht aus diesem "
                "Paket; nichts geschrieben:")
        for z in veraendert:
            ausgabe("  lokal veraendert: %s" % z)
        for z in fremd:
            ausgabe("  nicht aus diesem Paket: %s" % z)
        return 1

    if (inst and inst.get("version") == version and not zahl["neu"]
            and not zahl["anders"] and not entfallen):
        ausgabe("Nichts zu tun: %s ist installiert und unveraendert." % version)
        for ereignis, datei, _ in fehlend:
            ausgabe("  Einstellung fehlt: %s -> %s" % (ereignis, datei))
        return 0

    sperre = _sperren(projekt)
    if not sperre:
        ausgabe("ABGEBROCHEN — eine andere Installation laeuft (Sperre juenger als %d min)."
                % SPERRE_MINUTEN)
        return 1
    sicherung = _abs(projekt, "%s/sicherung/vor-%s-%s"
                     % (META, version, time.strftime("%Y%m%d-%H%M%S")))
    inst_pfad = _abs(projekt, META + "/installiert.json")
    gesichert, angelegt = [], []
    try:
        for e in plan:
            if e["art"] == "anders":
                ziel = _abs(sicherung, e["ziel"])
                _kopieren(e["abs"], ziel)
                gesichert.append((e["abs"], ziel))
        for z in entfallen:
            ziel = _abs(sicherung, z)
            _kopieren(_abs(projekt, z), ziel)
            gesichert.append((_abs(projekt, z), ziel))
        if os.path.isfile(inst_pfad):
            _kopieren(inst_pfad, _abs(sicherung, META + "/installiert.json"))

        for e in plan:
            if e["art"] in ("neu", "anders"):
                _kopieren_atomar(e["quelle"], e["abs"])
                if e["art"] == "neu":
                    angelegt.append(e["abs"])
        for z in entfallen:
            os.remove(_abs(projekt, z))
        _json_schreiben(inst_pfad, {
            "paket": "infinite-accuracy",
            "version": version,
            "installiert_am": time.strftime("%Y-%m-%d %H:%M:%S"),
            "quelle": quelle,
            "dateien": {e["ziel"]: e["sha"] for e in plan},
        })
        if einstellungen and fehlend:
            einstellungen_ergaenzen(projekt, fehlend, sicherung)
            fehlend = []
        if not ohne_abnahme:
            hooks = [e["ziel"].rsplit("/", 1)[1] for e in plan
                     if e["ziel"].startswith(".claude/hooks/") and e["ziel"].endswith(".py")]
            ok, bericht = abnahme(projekt, hooks)
            for z in bericht:
                ausgabe("  " + z)
            if not ok:
                raise RuntimeError("Abnahme rot")
    except Exception as ex:                                       # noqa: BLE001
        ausgabe("FEHLER: %s — die vorige Fassung wird zurueckgespielt." % ex)
        for ziel_abs, sicher_abs in gesichert:
            try:
                _kopieren_atomar(sicher_abs, ziel_abs)
            except Exception:                                     # noqa: BLE001
                ausgabe("  NICHT zurueckgespielt: %s" % ziel_abs)
        for pfad in angelegt:
            try:
                os.remove(pfad)
            except Exception:                                     # noqa: BLE001
                pass
        alt_inst = _abs(sicherung, META + "/installiert.json")
        try:
            if os.path.isfile(alt_inst):
                _kopieren_atomar(alt_inst, inst_pfad)
            elif os.path.isfile(inst_pfad):
                os.remove(inst_pfad)
            alt_settings = _abs(sicherung, ".claude/settings.json")
            if os.path.isfile(alt_settings):
                _kopieren_atomar(alt_settings, _abs(projekt, ".claude/settings.json"))
        except Exception:                                         # noqa: BLE001
            pass
        ausgabe("ZURUECKGEROLLT. Sicherung: %s" % sicherung)
        return 1
    finally:
        try:
            os.remove(sperre)
        except Exception:                                         # noqa: BLE001
            pass

    ausgabe("INSTALLIERT: %s — Sicherung: %s"
            % (version, sicherung if gesichert else "keine noetig"))
    for ereignis, datei, _ in fehlend:
        ausgabe("  Einstellung fehlt: %s -> %s (mit --einstellungen ergaenzen)"
                % (ereignis, datei))
    return 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass
    p = argparse.ArgumentParser(prog="installieren.py")
    p.add_argument("--manifest", action="store_true")
    p.add_argument("--projekt")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--pruefen", action="store_true")
    g.add_argument("--erstinstallation", action="store_true")
    g.add_argument("--update", action="store_true")
    p.add_argument("--quelle", default=HIER)
    p.add_argument("--einstellungen", action="store_true")
    p.add_argument("--ohne-abnahme", action="store_true")
    args = p.parse_args(argv)
    if args.manifest:
        try:
            n = manifest_schreiben(args.quelle)
        except Exception as ex:                                   # noqa: BLE001
            print("PRUEFSUMMEN.json nicht geschrieben: %s" % ex)
            return 1
        print("PRUEFSUMMEN.json: %d Dateien, Version %s" % (n, version_lesen(args.quelle)))
        return 0
    if not args.projekt:
        p.error("--projekt fehlt")
    modus = ("pruefen" if args.pruefen else "erstinstallation" if args.erstinstallation
             else "update" if args.update else None)
    if not modus:
        p.error("--pruefen, --erstinstallation oder --update angeben")
    return ausfuehren(args.quelle, args.projekt, modus, args.einstellungen, args.ohne_abnahme)


if __name__ == "__main__":
    sys.exit(main())
