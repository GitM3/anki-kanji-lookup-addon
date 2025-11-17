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
import os
import re
from pathlib import Path
from typing import Dict, List, Set

from anki.hooks import addHook
from aqt import clayout, gui_hooks, mw
from aqt import reviewer as aqt_reviewer
from aqt.qt import (QAction, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                    QLineEdit)
from aqt.utils import showInfo, tooltip

try:
    from aqt.previewer import Previewer  # Anki 2.1.60+
except Exception:
    Previewer = None

###############################################################################
# Configuration helpers
###############################################################################

ADDON_NAME = __name__  # folder name
ADDON_DIR = Path(mw.addonManager.addonsFolder()) / ADDON_NAME
CFG_FILE = ADDON_DIR / "config.json"
CACHE_FILE = ADDON_DIR / "kanji_cache.json"


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
        "hoverFontSize": "auto",
        "hoverOffset":"0"
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
            col.update_note(note)
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
    w_hover_font = QLineEdit(str(CFG.get("hoverFontSize", "auto")))
    w_hover_offset = QLineEdit(str(CFG.get("hoverOffset", "0")))
    w_debug = QCheckBox("Enable debug logging (print to console)")
    w_debug.setChecked(bool(CFG["debug"]))

    lay.addRow("Target deck:", w_target)
    lay.addRow("Kanji search field:", w_search)
    lay.addRow("Additional field:", w_add)
    lay.addRow("Source field:", w_source)
    lay.addRow("Destination field:", w_dest)
    lay.addRow("Note-type filter (comma):", w_types)
    lay.addRow("Hover font size (px or 'auto'):", w_hover_font)
    lay.addRow("Hover offset from top (px'):", w_hover_offset)
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
        "hoverFontSize": w_hover_font.text().strip() or "auto",
        "hoverOffset": w_hover_offset.text().strip() or "0",
        "debug": w_debug.isChecked(),
    }

    _save_cfg(new_cfg)
    CFG = _load_cfg()
    showInfo("Kanji Constituent settings saved.")

def load_cache() -> Dict[str, str]:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("[Kanji Constituent] Cache load failed:", e)
    return {}


def save_cache(cache: Dict[str, str]) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[Kanji Constituent] Cache write failed:", e)


KANJI_CACHE = load_cache()


def lookup_with_cache(word: str) -> Dict[str, str]:
    global KANJI_CACHE

    kanji_list = extract_unique_kanji(word)
    result: Dict[str, str] = {}
    new_kanji: List[str] = []

    # Step 1: Check cache
    log("Checking cache")
    for k in kanji_list:
        if k in KANJI_CACHE:
            result[k] = KANJI_CACHE[k]
            log("Found in cache")
        else:
            new_kanji.append(k)

    # Step 2: Deck lookup for missing ones
    if new_kanji:
        log("Not found in cache, looking up")
        meanings = lookup_meanings(new_kanji)
        result.update(meanings)
        # Update cache
        KANJI_CACHE.update(meanings)
        save_cache(KANJI_CACHE)

    return result


def inject_hover_script(web_content, context):
    """Injects JS for Ctrl+K and context menu in reviewer/previewer."""
    cname = type(context).__name__
    print("[HoverDebug] injecting into:", cname)

    # Allow reviewer, previewer, card layout (and bottom bar to be safe)
    allowed_types = [aqt_reviewer.Reviewer, clayout.CardLayout]
    if Previewer:
        allowed_types.append(Previewer)

    # Some builds pass a ReviewerBottomBar; allow by class name
    allowed_classnames = {"ReviewerBottomBar"}

    if not (
        isinstance(context, tuple(allowed_types))
        or cname in allowed_classnames
    ):
        return
    font_size = str(CFG.get("hoverFontSize", "auto"))
    hover_offset = str(CFG.get("hoverOffset", "0"))
    js = f"""
    <script>
    (function() {{
        if (window.__KANJI_LOOKUP_INJECTED__) return;
        window.__KANJI_LOOKUP_INJECTED__ = true;

        const HOVER_FONT_SIZE = "{font_size}";
        const HOVER_OFFSET = "{hover_offset}";

        function sendLookup(text) {{
            if (!text) return;
            try {{ pycmd('kanjiLookup:' + text); }} catch (e) {{ console.log(e); }}
        }}

        function getFrameDoc() {{
            const iframe = document.querySelector('#qa');
            if (iframe && iframe.contentDocument) return iframe.contentDocument;
            return document;
        }}

        function getSelectionRect(doc) {{
            if (!doc) return null;
            const sel = doc.getSelection ? doc.getSelection() : null;
            if (!sel || !sel.rangeCount) return null;
            return sel.getRangeAt(0).getBoundingClientRect();
        }}

        function detectFontSize(doc) {{
            const sel = doc.getSelection();
            if (!sel || sel.rangeCount === 0) return null;
            const node = sel.anchorNode && sel.anchorNode.parentElement;
            if (!node) return null;
            const style = doc.defaultView.getComputedStyle(node);
            return style.fontSize || null;
        }}

        function showLookupTooltip(text, html) {{
            const doc = getFrameDoc();
            const rect = getSelectionRect(doc);
            if (!rect) return;

            const tip = doc.createElement('div');
            tip.className = 'kanji-tooltip';
            tip.innerHTML = html;

            let fs = HOVER_FONT_SIZE;
            if (fs === "auto") {{
                const detected = detectFontSize(doc);
                if (detected) fs = detected;
                else fs = "16px";
            }} else {{
                fs = fs.replace(/[^0-9.]/g, '') + 'px';
            }}

            Object.assign(tip.style, {{
                position: 'absolute',
                left: rect.left + 'px',
                top: (rect.top + doc.documentElement.scrollTop - 40 + HOVER_OFFSET) + 'px',
                background: 'rgba(20,20,20,0.95)',
                color: 'white',
                padding: '6px 10px',
                borderRadius: '8px',
                fontSize: fs,
                lineHeight: '1.4',
                zIndex: 99999,
                boxShadow: '0 2px 10px rgba(0,0,0,0.4)',
                pointerEvents: 'none',
                maxWidth: '90%',
                wordWrap: 'break-word',
                opacity: '0',
                transition: 'opacity 0.15s ease-in'
            }});

            doc.body.appendChild(tip);
            requestAnimationFrame(() => {{ tip.style.opacity = '1'; }});
            setTimeout(() => {{
                tip.style.opacity = '0';
                setTimeout(() => tip.remove(), 200);
            }}, 5000);
        }}

        window.AnkiHoverShow = showLookupTooltip;

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'F9' || (e.ctrlKey && e.key.toLowerCase() === 'k')) {{
                const doc = getFrameDoc();
                const sel = doc.getSelection ? doc.getSelection().toString().trim() : '';
                if (!sel) return;
                sendLookup(sel);
                e.preventDefault();
                e.stopPropagation();
            }}
        }}, {{capture: true}});

        console.log('[KanjiHover] script injected (font size aware)');
    }})();
    </script>
    """
    web_content.head += js


def on_js_command(handled, cmd, context):
    if cmd.startswith("kanjiLookup:"):
        word = cmd.split(":", 1)[1]
        meanings = lookup_with_cache(word)
        log(f"Meaning found:{meanings}")
        html = "<br>".join(f"{k}: {v}" for k, v in meanings.items() if v) or f"No kanji found in '{word}'."
        js = f"if (window.AnkiHoverShow) window.AnkiHoverShow({json.dumps(word)}, {json.dumps(html)});"
        context.web.eval(js)
        return (True, None)
    return handled


gui_hooks.webview_will_set_content.append(inject_hover_script)
gui_hooks.webview_did_receive_js_message.append(on_js_command)

print("[Kanji Constituent] Reviewer hover lookup loaded (Ctrl+K or right-click to use).")

menu_act = QAction("Kanji Constituent Options…", mw)
menu_act.triggered.connect(show_options)
mw.form.menuTools.addSeparator()
mw.form.menuTools.addAction(menu_act)

