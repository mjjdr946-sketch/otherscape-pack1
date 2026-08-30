#!/usr/bin/env python3
"""Validateur de compendium Otherscape Character Pack.
Compare le fichier Markdown source avec actors.db NDJSON.

Usage:
    python3 scripts/validate_characters.py                  # validation complète
    python3 scripts/validate_characters.py --json           # sortie JSON (CI)
"""
import json, os, re, sys, unicodedata
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_MD = os.path.join(REPO_ROOT, "Otherscape_Personnages_FR.md")
ACTORS_DB = os.path.join(REPO_ROOT, "packs", "actors.db")
MANIFEST_JSON = os.path.join(REPO_ROOT, "scripts", "characters_manifest.json")

CAT2TB = {
    "ÉSOTÉRISME": ("Esoterica", "f0Hldws5yB2ezw1Z"),
    "EXPOSURE": ("Exposure", "5CG8unkzHqU6xuQW"),
    "EXPOSITION": ("Exposure", "5CG8unkzHqU6xuQW"),
    "PASSÉ TROUBLE": ("Troubled Past", "snHXQlSZdGALWPNq"),
    "EXPERTISE": ("Expertise", "FUhv3c81M1tcVSJD"),
    "CYBERESPACE": ("Cyberspace", "D88XNZrAQ5oMfsFW"),
    "ASSETS": ("Assets", "m7aMSrzoz8iEjrXi"),
    "PERSONNALITÉ": ("Personality", "FW5g6LLhbaf5BFFm"),
    "DRONES": ("Drones", "3i6BJjmC1oKKQvCV"),
    "ARTEFACT": ("Artifact", "NgbUT22G4qsBqSwn"),
    "AFFILIATION": ("Affiliation", "noqoLlmqIwjirJ52"),
    "AUGMENTATION": ("Augmentation", "K3rvh4bMi0L6S4lS"),
    "CUTTING EDGE": ("Cutting Edge", "eSg1666zWlbhuoyl"),
    "COMPAGNON": ("Companion", "K1T0cmc315lR55ql"),
    "HORIZON": ("Horizon", "WQ1gYMo8oWoiPX2a"),
}

def normalize_name(name):
    name = re.sub(r'\([^)]*\)', '', name)
    nfkd = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    name = re.sub(r'[^a-zA-Z0-9\s\'-]', '', name)
    return name.strip().lower()

def compute_essence(m, s, n):
    return "Mythos" if m > s else ("Logos" if s > m else "Nexus")

def parse_markdown(fp):
    with open(fp, encoding='utf-8') as f:
        md = f.read()
    manifest = {}
    for char_block in re.split(r'\n(?=#\s+\d+\.\s+)', md):
        char_block = char_block.strip()
        if not char_block:
            continue
        m = re.match(r'#\s+(\d+)\.\s+(.+?)\n', char_block)
        if not m:
            continue
        raw_name = m.group(2).strip()
        ms = re.search(r'\*\*Mythos\s*:\*\*\s*(\d+)\s*\|\s*\*\*Self\s*:\*\*\s*(\d+)\s*\|\s*\*\*Noise\s*:\*\*\s*(\d+)', char_block)
        if not ms:
            continue
        my, se, no = int(ms.group(1)), int(ms.group(2)), int(ms.group(3))
        cd = {"number": int(m.group(1)), "name": raw_name,
              "name_norm": normalize_name(raw_name),
              "essence": compute_essence(my, se, no),
              "stats": {"mythos": my, "self": se, "noise": no},
              "themes": [], "loadout": []}
        ts = re.search(r'### 🎭 Thèmes de Personnage\s*\n(.*?)(?=### 🎒|### ⚡\s*|$)', char_block, re.DOTALL)
        if ts:
            for tb in re.split(r'\n(?=####\s+\d+\.)', ts.group(1)):
                tb = tb.strip()
                if not tb:
                    continue
                lines = tb.split('\n')
                hdr = lines[0]
                body = '\n'.join(lines[1:])
                mh = re.match(r'####\s+\d+\.\s+(.+?)\s+\((.+?)\)\s*:\s*(.+)$', hdr)
                if not mh:
                    continue
                cat = mh.group(1).strip().upper()
                etype = mh.group(2).strip()
                tn_raw = mh.group(3).strip()
                tn = re.sub(r'\s*\*\(.*?\)\*\s*$', '', tn_raw).strip().replace('**', '').strip()
                if cat in CAT2TB:
                    tbn, tbi = CAT2TB[cat]
                else:
                    tbn, tbi = cat, "UNKNOWN"
                powers, weaknesses, options = [], [], []
                for line in body.split('\n'):
                    line = line.strip()
                    for tag_type, emoji, lst in [("ACTIF", "🟢", powers), ("FAIBLESSE", "🔴", weaknesses), ("Option", "⚪", options)]:
                        p = re.compile(r'\*\s*\*{0,2}\s*\[' + re.escape(tag_type) +
                                       r'\]\s*\*{0,2}\s*' + re.escape(emoji) +
                                       r'\s*\*{0,2}\s*(.+?)(?:\s*\*\(.*?\)\*)?\s*$')
                        pm = p.match(line)
                        if pm:
                            lst.append({"name": pm.group(1).strip().rstrip('*').strip()})
                            break
                mystery = ""
                for label in ["Rituel", "Identité", "Pulsion (Itch)", "Pulsion"]:
                    mm = re.search(r'\*\*' + re.escape(label) + r'\s*:\*\*\s*\*?«(.+?)»\*?', body, re.DOTALL)
                    if mm:
                        mystery = mm.group(1).strip()
                        break
                cd["themes"].append({"name": tn, "category": cat, "themebook_name": tbn,
                                     "themebook_id": tbi, "essence_type": etype,
                                     "mystery": mystery, "powers": powers,
                                     "weaknesses": weaknesses, "options": options})
        ls = re.search(r'### 🎒 Matériel & Équipement \(Loadout\)\s*\n(.*?)(?=### ⚡\s*|$)', char_block, re.DOTALL)
        if ls:
            for match in re.finditer(r'\*\s*\[(ÉQUIPÉ|Réserve)\]\s*(.+?)\s*(?:\(.*?\))?\s*$', ls.group(1), re.MULTILINE):
                cd["loadout"].append({"type": match.group(1).strip(), "name": match.group(2).strip()})
        manifest[normalize_name(raw_name)] = cd
    return manifest

def parse_actors_db(fp):
    with open(fp, encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    actors = {}
    db_errors = []
    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            db_errors.append(f"Ligne {i+1}: JSON invalide — {e}")
            continue
        name = obj.get("name", f"UNNAMED_{i}")
        if obj.get("type") != "character":
            db_errors.append(f"{name}: type '{obj.get('type')}' au lieu de 'character'")
        essence = obj.get("system", {}).get("essence", {}).get("systemName", "")
        items = obj.get("items", [])
        themes = [it for it in items if it.get("type") == "theme"]
        tags = [it for it in items if it.get("type") == "tag"]
        tbt = defaultdict(list)
        for t in tags:
            tbt[t.get("system", {}).get("theme_id", "")].append(t)
        ad = {"db_name": name, "name_norm": normalize_name(name), "essence": essence, "themes": []}
        for t in themes:
            if t["name"] == "__LOADOUT__":
                continue
            tid = t.get("_id", "")
            tt = tbt.get(tid, [])
            ad["themes"].append({"name": t["name"], "theme_id": tid,
                                 "themebook_id": t.get("system", {}).get("themebook_id", ""),
                                 "themebook_name": t.get("system", {}).get("themebook_name", ""),
                                 "mystery": t.get("system", {}).get("mystery", ""),
                                 "tags": [{"name": tg["name"],
                                           "type": tg.get("system", {}).get("subtype", ""),
                                           "letter": tg.get("system", {}).get("question_letter", ""),
                                           "question": tg.get("system", {}).get("question", "")}
                                          for tg in tt]})
        actors[normalize_name(name)] = ad
    return actors, db_errors

def validate(manifest, actors):
    errs, warns = [], []
    mn = set(manifest.keys())
    an = set(actors.keys())
    for m in sorted(mn - an):
        errs.append(f"Personnage manquant dans actors.db: '{manifest[m]['name']}'")
    for a in sorted(an - mn):
        errs.append(f"Personnage en trop dans actors.db: '{actors[a]['db_name']}'")
    for nn in mn & an:
        m, a = manifest[nn], actors[nn]
        if m["essence"].upper() != a["essence"].upper():
            s = m["stats"]
            errs.append(f"[{m['name']}] Essence: attendu '{m['essence']}' (M{s['mythos']}/S{s['self']}/N{s['noise']}), trouvé '{a['essence']}'")
        mt, at = m["themes"], a["themes"]
        if len(mt) != len(at):
            errs.append(f"[{m['name']}] {len(mt)} thèmes dans la source vs {len(at)} dans la DB")
            continue
        for i in range(len(mt)):
            mt_i, at_i = mt[i], at[i]
            if mt_i["name"].upper() != at_i["name"].upper():
                errs.append(f"[{m['name']}] Thème #{i+1}: attendu '{mt_i['name']}', trouvé '{at_i['name']}'")
            if mt_i["themebook_id"] != at_i["themebook_id"]:
                errs.append(f"[{m['name']}] Thème '{mt_i['name']}': themebook_id {mt_i['themebook_id']} attendu, {at_i['themebook_id']} trouvé")
            if mt_i["themebook_name"].upper() != at_i.get("themebook_name", "").upper():
                errs.append(f"[{m['name']}] Thème '{mt_i['name']}': themebook_name attendu '{mt_i['themebook_name']}', trouvé '{at_i.get('themebook_name','?')}'")
            ap = [t for t in at_i["tags"] if t["type"] == "power"]
            aw = [t for t in at_i["tags"] if t["type"] == "weakness"]
            if len(mt_i["powers"]) != len(ap):
                errs.append(f"[{m['name']}] Thème '{mt_i['name']}': {len(mt_i['powers'])} pouvoirs attendus, {len(ap)} trouvés")
            if len(mt_i["weaknesses"]) != len(aw):
                errs.append(f"[{m['name']}] Thème '{mt_i['name']}': {len(mt_i['weaknesses'])} faiblesses attendues, {len(aw)} trouvées")
            for j in range(min(len(mt_i["powers"]), len(ap))):
                if mt_i["powers"][j]["name"].upper() != ap[j]["name"].upper():
                    errs.append(f"[{m['name']}] Thème '{mt_i['name']}', pouvoir #{j+1}: attendu '{mt_i['powers'][j]['name']}', trouvé '{ap[j]['name']}'")
            for j in range(min(len(mt_i["weaknesses"]), len(aw))):
                if mt_i["weaknesses"][j]["name"].upper() != aw[j]["name"].upper():
                    errs.append(f"[{m['name']}] Thème '{mt_i['name']}', faiblesse #{j+1}: attendu '{mt_i['weaknesses'][j]['name']}', trouvé '{aw[j]['name']}'")
            # Mystères
            mm = re.sub(r'\s+', ' ', mt_i["mystery"]).strip().lower() if mt_i["mystery"] else ""
            am_raw = at_i["mystery"] if at_i["mystery"] else ""
            am_clean = am_raw
            mdb = re.match(r'\s*\*\s*\*\*.*?\*\*\s*:\s*\*?«(.+?)»\*?\s*$', am_raw)
            if mdb:
                am_clean = mdb.group(1).strip()
            am = re.sub(r'\s+', ' ', am_clean).strip().lower() if am_clean else ""
            if mm and am and mm not in am and am not in mm:
                common = sum(1 for a, b in zip(mm, am) if a == b)
                if common < 30:
                    warns.append(f"[{m['name']}] Thème '{mt_i['name']}': mystère différent — source: \"{mt_i['mystery'][:60]}...\", DB: \"{am_raw[:60]}...\"")
            elif mm and not am:
                errs.append(f"[{m['name']}] Thème '{mt_i['name']}': mystère manquant dans la DB")
            elif not mm and am:
                warns.append(f"[{m['name']}] Thème '{mt_i['name']}': mystère présent dans la DB mais absent de la source")
    return errs, warns

def print_report(manifest, actors, errs, warns, fmt):
    if fmt == "json":
        print(json.dumps({"status": "PASS" if not errs else "FAIL",
                          "source_count": len(manifest), "db_count": len(actors),
                          "error_count": len(errs), "warning_count": len(warns),
                          "errors": errs, "warnings": warns}, ensure_ascii=False, indent=2))
        return 1 if errs else 0
    print("=" * 60)
    print("📋 RAPPORT — Otherscape Character Pack")
    print("=" * 60)
    print(f"Source: {len(manifest)} pers. | DB: {len(actors)} pers.\n")
    if not errs and not warns:
        print("✅  VALIDATION PASSÉE")
        return 0
    if errs:
        print(f"❌  {len(errs)} ERREUR(S):")
        for e in errs:
            print(f"   • {e}")
    if warns:
        print(f"\n⚠️   {len(warns)} AVERTISSEMENT(S):")
        for w in warns:
            print(f"   • {w}")
    print(f"\n{'🔴' if errs else '🟡'} BILAN: {len(errs)} erreur(s), {len(warns)} avertissement(s)")
    return 1 if errs else 0

def main():
    mode, fmt = "validate", "text"
    for arg in sys.argv[1:]:
        if arg == "--json":
            fmt = "json"
        elif arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]
    actors, db_err = parse_actors_db(ACTORS_DB)
    if mode == "db-only":
        return print_report({}, actors, db_err, [], fmt)
    manifest = parse_markdown(SOURCE_MD)
    json.dump({"version":"1.0","character_count":len(manifest),"characters":manifest},
              open(MANIFEST_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    errs, warns = validate(manifest, actors)
    return print_report(manifest, actors, db_err + errs, warns, fmt)

if __name__ == "__main__":
    sys.exit(main())