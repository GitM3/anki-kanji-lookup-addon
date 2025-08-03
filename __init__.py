"""
Anki add-on: Kanji Constituent Auto-Fill
======================================
Populates a vocab note with a list of each kanji it contains and the
kanji’s keyword/meaning pulled from a separate single-kanji deck.

* Works with **any number** of kanji.
* Supports **bulk fill** from the Browser.
* Includes an **Options** dialog (Tools ▸ Kanji Constituent Options…) with
  a toggle for **debug logging** that prints detailed steps to the terminal.
* Uses the current (non-deprecated) Anki API names (`find_notes`,
  `get_note`, `note.note_type`, `models.field_names`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Set

from aqt import mw
from aqt.qt import (
    QAction,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)
from aqt.utils import showInfo, tooltip
from anki.hooks import addHook

###############################################################################
# Configuration helpers
###############################################################################

ADDON_NAME = __name__  # folder name
ADDON_DIR = Path(mw.addonManager.addonsFolder()) / ADDON_NAME
CFG_FILE = ADDON_DIR / "config.json"


def _defaults() -> Dict[str, object]:
    return {
        "targetDeck": "Kanji_Deck",
        "searchField": "Expression",
        "additionalField": "keyword",
        "sourceField": "Expression",
        "destinationField": "Constituents",
        "lookupOnAdd": True,
        "noteTypes": "",              # comma-separated list
        "bulkActionLabel": "Bulk-add Constituents",
        "debug": False,
    }


def _load_cfg() -> Dict[str, object]:
    user = mw.addonManager.getConfig(ADDON_NAME) or {}
    return {**_defaults(), **user}


def _save_cfg(cfg: Dict[str, object]) -> None:
    mw.addonManager.writeConfig(ADDON_NAME, cfg)
    try:
        ADDON_DIR.mkdir(parents=True, exist_ok=True)
        CFG_FILE.write_text(json.dumps({"config": cfg}, ensure_ascii=False, indent=2))
    except Exception as e:
        print("[Kanji Constituent] couldn't write config.json:", e)


CFG: Dict[str, object] = _load_cfg()

###############################################################################
# Debug logging
###############################################################################

def log(*msg):
    if CFG.get("debug"):
        print("[Kanji Constituent]", *msg)

###############################################################################
# Kanji helpers
###############################################################################

KANJI_RE = re.compile(r"[\u4E00-\u9FFF]")


def extract_unique_kanji(text: str) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for ch in text:
        if KANJI_RE.fullmatch(ch) and ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


def lookup_meanings(kanji: List[str]) -> Dict[str, str]:
    deck = CFG["targetDeck"]
    s_field = CFG["searchField"]
    a_field = CFG["additionalField"]
    col = mw.col

    log("Searching deck:", deck)
    res: Dict[str, str] = {}
    for k in kanji:
        note_ids = col.find_notes(f'deck:"{deck}" "{k}"')
        log(" ├─", k, "→ nids", note_ids)
        for nid in note_ids:
            note = col.get_note(nid)
            try:
                if note[s_field].strip() == k:
                    try:
                        res[k] = note[a_field].strip()
                    except KeyError:
                        res[k] = ""
                    break
            except KeyError:
                pass
    log("Lookup result:", res)
    return res


def join_pairs(mapping: Dict[str, str]) -> str:
    return "\u3000".join(f"{k}: {v}".strip() for k, v in mapping.items() if v)

###############################################################################
# Populate one note
###############################################################################

def populate(note) -> bool:
    nt_filter = [t.strip().lower() for t in str(CFG["noteTypes"]).split(",") if t.strip()]
    if nt_filter and not any(t in note.note_type()["name"].lower() for t in nt_filter):
        log("Skip – note-type filtered:", note.note_type()["name"])
        return False

    src = CFG["sourceField"]
    dst = CFG["destinationField"]
    if src not in note or dst not in note:
        log("Skip – missing src/dst fields")
        return False

    expr = mw.col.media.strip(note[src]).strip()
    if not expr:
        log("Skip – empty expression")
        return False

    kanji = extract_unique_kanji(expr)
    if not kanji:
        log("Skip – no kanji in", expr)
        return False

    mapping = lookup_meanings(kanji)
    if not mapping:
        log("Skip – no mapping found for", kanji)
        return False

    note[dst] = join_pairs(mapping)
    log("Populated →", note[dst])
    return True

###############################################################################
# Hooks – automatic fill on field defocus
###############################################################################

def on_edit_focus(flag, note, field_idx):
    if not CFG["lookupOnAdd"]:
        return flag
    col = mw.col
    try:
        src_idx = col.models.field_names(note.note_type()).index(CFG["sourceField"])
    except ValueError:
        return flag

    if field_idx == src_idx:
        log("Field defocus – trying note id", note.id)
        populate(note)
    return flag

if CFG["lookupOnAdd"]:
    addHook("editFocusLost", on_edit_focus)

###############################################################################
# Bulk action (Browser)
###############################################################################

def bulk_add(nids: List[int]):
    global CFG
    CFG = _load_cfg()  # refresh settings each run
    if not nids:
        tooltip("No notes selected")
        return

    col = mw.col
    changed = 0
    for nid in nids:
        note = col.get_note(nid)
        if populate(note):
            note.flush()
            changed += 1
    tooltip(f"Updated {changed} notes" if changed else "No notes needed")
    log("Bulk finished –", changed, "of", len(nids))


def browser_menu(browser):
    act = QAction(CFG["bulkActionLabel"], browser)
    act.triggered.connect(lambda _, b=browser: bulk_add(b.selectedNotes()))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(act)

addHook("browser.setupMenus", browser_menu)

###############################################################################
# Options dialog
###############################################################################

def show_options():
    global CFG
    CFG = _load_cfg()

    dlg = QDialog(mw)
    dlg.setWindowTitle("Kanji Constituent Options")
    lay = QFormLayout(dlg)

    w_target = QLineEdit(str(CFG["targetDeck"]))
    w_search = QLineEdit(str(CFG["searchField"]))
    w_add = QLineEdit(str(CFG["additionalField"]))
    w_source = QLineEdit(str(CFG["sourceField"]))
    w_dest = QLineEdit(str(CFG["destinationField"]))
    w_types = QLineEdit(str(CFG["noteTypes"]))
    w_lookup = QCheckBox("Populate when leaving expression field")
    w_lookup.setChecked(bool(CFG["lookupOnAdd"]))
    w_debug = QCheckBox("Enable debug logging (print to console)")
    w_debug.setChecked(bool(CFG["debug"]))

    lay.addRow("Target deck:", w_target)
    lay.addRow("Kanji search field:", w_search)
    lay.addRow("Additional field:", w_add)
    lay.addRow("Source field:", w_source)
    lay.addRow("Destination field:", w_dest)
    lay.addRow("Note-type filter (comma):", w_types)
    lay.addRow(w_lookup)
    lay.addRow(w_debug)

    try:
        std = QDialogButtonBox.StandardButton
        btns = QDialogButtonBox(std.Ok | std.Cancel)
    except AttributeError:
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    lay.addRow(btns)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    if not dlg.exec():
        return

    new_cfg = {
        "targetDeck": w_target.text().strip() or "Kanji_Deck",
        "searchField": w_search.text().strip() or "Expression",
        "additionalField": w_add.text().strip() or "keyword",
        "sourceField": w_source.text().strip() or "Expression",
        "destinationField": w_dest.text().strip() or "Constituents",
        "noteTypes": w_types.text().strip(),
        "lookupOnAdd": w_lookup.isChecked(),
        "bulkActionLabel": CFG["bulkActionLabel"],
        "debug": w_debug.isChecked(),
    }

    _save_cfg(new_cfg)
    CFG = _load_cfg()
    showInfo("Kanji Constituent settings saved.")


menu_act = QAction("Kanji Constituent Options…", mw)
menu_act.triggered.connect(show_options)
mw.form.menuTools.addSeparator()
mw.form.menuTools.addAction(menu_act)

###############################################################################
# End of file
###############################################################################
