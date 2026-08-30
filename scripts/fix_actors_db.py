#!/usr/bin/env python3
"""Corrige les erreurs détectées dans actors.db : essences + mystères manquants.
Usage: python3 scripts/fix_actors_db.py
"""
import json, os, re, sys, unicodedata
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "packs", "actors.db")
SRC = os.path.join(REPO, "Otherscape_Personnages_FR.md")

CAT2TB = {
    "ÉSOTÉRISME": "Esoterica", "EXPOSURE": "Exposure", "EXPOSITION": "Exposure",
    "PASSÉ TROUBLE": "Troubled Past", "EXPERTISE": "Expertise", "CYBERESPACE": "Cyberspace",
    "ASSETS": "Assets", "PERSONNALITÉ": "Personality", "DRONES": "Drones",
    "ARTEFACT": "Artifact", "AFFILIATION": "Affiliation", "AUGMENTATION": "Augmentation",
    "CUTTING EDGE": "Cutting Edge", "COMPAGNON": "Companion", "HORIZON": "Horizon",
}

def norm(name):
    name = re.sub(r'\([^)]*\)', '', name)
    nfkd = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'[^a-zA-Z0-9\s\'-]', '', name).strip().lower()

def essence(m, s, n):
    return "Mythos" if m > s else ("Logos" if s > m else "Nexus")

# Parse source markdown
with open(SRC, encoding='utf-8') as f:
    md = f.read()

source = {}
for block in re.split(r'\n(?=#\s+\d+\.\s+)', md):
    block = block.strip()
    if not block or not re.match(r'#\s+\d+\.\s+', block):
        continue
    m = re.match(r'#\s+\d+\.\s+(.+?)(?:\n|$)', block)
    if not m:
        continue
    raw_name = m.group(1).strip()
    ms = re.search(r'\*\*Mythos\s*:\*\*\s*(\d+)\s*\|\s*\*\*Self\s*:\*\*\s*(\d+)\s*\|\s*\*\*Noise\s*:\*\*\s*(\d+)', block)
    if not ms:
        continue
    my, se, no = int(ms.group(1)), int(ms.group(2)), int(ms.group(3))
    ess = essence(my, se, no)
    
    themes = {}
    ts = re.search(r'### 🎭 Thèmes de Personnage\s*\n(.*?)(?=### 🎒|### ⚡\s*|$)', block, re.DOTALL)
    if ts:
        for tb in re.split(r'\n(?=####\s+\d+\.)', ts.group(1)):
            tb = tb.strip()
            if not tb:
                continue
            mh = re.match(r'####\s+\d+\.\s+(.+?)\s+\(.+?\)\s*:\s*(.+)$', tb.split('\n')[0])
            if not mh:
                continue
            theme_name = re.sub(r'\*\s*\(.*?\)\*\s*$', '', mh.group(2)).replace('**', '').strip()
            
            # Mystery
            mystery_text = ""
            mystery_label = ""
            for label in ["Rituel", "Identité", "Pulsion (Itch)", "Pulsion"]:
                mm = re.search(r'\*\*' + re.escape(label) + r'\s*:\*\*\s*\*?«(.+?)»\*?', tb, re.DOTALL)
                if mm:
                    mystery_text = mm.group(1).strip()
                    mystery_label = label
                    break
            
            themes[theme_name.upper()] = {
                "mystery_text": mystery_text,
                "mystery_label": mystery_label,
            }
    
    source[norm(raw_name)] = {
        "name": raw_name,
        "essence": ess,
        "themes": themes,
    }

# Parse & fix DB
with open(DB, encoding='utf-8') as f:
    lines = [l.strip() for l in f if l.strip()]

fixed_count = 0
essence_fixes = 0
mystery_fixes = 0
new_lines = []

for line in lines:
    obj = json.loads(line)
    name = obj.get("name", "")
    nn = norm(name)
    
    if nn not in source:
        new_lines.append(line)
        continue
    
    src = source[nn]
    changed = False
    
    # Fix essence
    current_essence = obj.get("system", {}).get("essence", {}).get("systemName", "")
    if current_essence.upper() != src["essence"].upper():
        obj["system"]["essence"]["systemName"] = src["essence"]
        print(f"  🔧 {name}: essence {current_essence} → {src['essence']}")
        essence_fixes += 1
        changed = True
    
    # Fix mysteries
    for item in obj.get("items", []):
        if item.get("type") != "theme" or item["name"] == "__LOADOUT__":
            continue
        
        tname = item["name"].upper()
        if tname in src["themes"]:
            theme_src = src["themes"][tname]
            if theme_src["mystery_text"]:
                current = item.get("system", {}).get("mystery", "")
                if not current:
                    # Store in the same format as existing DB entries
                    label = theme_src["mystery_label"]
                    mystery_val = f"* **{label} :** *« {theme_src['mystery_text']} »*"
                    item["system"]["mystery"] = mystery_val
                    print(f"  🔧 {name} / {item['name']}: mystère ajouté")
                    mystery_fixes += 1
                    changed = True
    
    if changed:
        fixed_count += 1
    
    new_lines.append(json.dumps(obj, ensure_ascii=False))

# Write back
with open(DB, 'w', encoding='utf-8') as f:
    for line in new_lines:
        f.write(line + '\n')

print(f"\n✅ {fixed_count} personnages corrigés")
print(f"   Essences : {essence_fixes} corrections")
print(f"   Mystères : {mystery_fixes} ajouts")
print(f"   Fichier: {DB}")
