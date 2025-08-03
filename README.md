# Kanji Constituent Auto‑Fill

> **Anki add‑on** that automatically appends the meaning of every kanji inside a vocabulary expression to the note itself.

---

## ✨ Features

|                            |                                                                |
| -------------------------- | -------------------------------------------------------------- |
| **Unlimited kanji**        | Handles any length expression; de‑duplicates characters.       |
| **Single‑click bulk fill** | Browser ▶︎ *Edit ▸ Bulk‑add Constituents*.                     |
| **Live auto‑fill**         | Populates on field defocus while editing a note.               |
| **Config dialog**          | *Tools ▸ Kanji Constituent Options…* (no JSON editing).        |
| **Debug mode**             | Optional verbose console log for troubleshooting.              |
| **Modern API**             | Uses non‑deprecated Anki 2.1.65+ methods (`find_notes`, etc.). |

---

## 🛠️ Installation

1. Clone or download this repo into your Anki `addons21` folder.  The final tree should look like:

```
addons21/
└── kanji_constituent/
    ├── __init__.py
    ├── README.md
    └── config.json   ← optional, created automatically
```

2. Restart Anki.
3. Verify that **Kanji Constituent Auto‑Fill** appears under *Tools ▸ Add‑ons*.

---

## ⚙️ Configuration

Open *Tools ▸ Kanji Constituent Options…* to adjust settings:

| Setting                | Purpose                                      | Default        |
| ---------------------- | -------------------------------------------- | -------------- |
| **Target deck**        | Deck that stores *single‑kanji* notes        | `Kanji_Deck`   |
| **Kanji search field** | Field on that note containing the character  | `Expression`   |
| **Additional field**   | Field whose value is copied (e.g. `keyword`) | `keyword`      |
| **Source field**       | Field on the vocab note with the expression  | `Expression`   |
| **Destination field**  | Field to receive the joined string           | `Constituents` |
| **Note‑type filter**   | Comma‑separated substrings (optional)        | *(empty)*      |
| **Populate on edit**   | Auto‑fill when leaving the source field      | ✓              |
| **Debug logging**      | Print step‑by‑step info to terminal          | ✗              |

A human‑readable **`config.json`** is stored alongside the add‑on for easy backup or manual tweaking.

---

## 🚀 Usage

### Auto‑fill while editing

1. Create or edit a vocab note.
2. Enter the expression (e.g. `国家`).
3. When you tab out of the expression field, the add‑on writes:

```
国: country　家: house
```

into your *Destination field*.

### Bulk fill existing notes

1. Open the **Browser**.
2. Select any number of vocab notes.
3. *Edit ▸ Bulk‑add Constituents*.
4. A tooltip shows how many notes were updated.

---

## 🐞 Debugging

Enable **Debug logging** in the options dialog and start Anki from a terminal.  You’ll see output like:

```
[Kanji Constituent] Field defocus – trying note id 1529598156213
[Kanji Constituent] Searching deck: 3)日常::漢字
[Kanji Constituent]  ├─ 国 → nids [1354715366501]
[Kanji Constituent] Lookup result: {'国': 'country', '家': 'house'}
[Kanji Constituent] Populated → 国: country　家: house
```

This helps diagnose missing fields, deck typos, etc.

---

