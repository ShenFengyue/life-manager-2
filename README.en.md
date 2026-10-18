# Life Manager 2

[简体中文](README.md) | English

> Version history: [CHANGELOG.md](CHANGELOG.md). App version **1.34.0**, schema version **v4**
> (older databases upgrade automatically on start, with a backup taken first).

A single-user, fully local Windows desktop app that **externalises, structures and visualises**
the things you are pushing forward at the same time.

A tree gives you order, the mind map gives you speed, the calendar gives you time, and the heatmaps
show what actually happened. The pinned "current focus" decides what you do today.

It is not a to-do list, not a web app, and not a collaboration tool.

---

## Screenshots

Everything below is a real screenshot of the running app. The data comes from
`tools/seed_demo.py` — about 15 months and 1,500+ records of a fictional user — not from a real person.

**Overview**: the large calendar at the top is the global heatmap (all areas and processes combined),
followed by the current focus, quick capture, per-area heatmaps and recent activity.

![Overview](docs/screenshots/overview.png)

| Heatmaps: areas → processes → threads | Mind map: click a card to log something |
|---|---|
| ![Heatmaps](docs/screenshots/heatmaps.png) | ![Mind map](docs/screenshots/mindmap.png) |

| Activity list: grouped by day, editable, deletable | Process tree: three levels + change history |
|---|---|
| ![Activity](docs/screenshots/activity.png) | ![Process tree](docs/screenshots/processes.png) |

| Journal: one entry per day, stored as Markdown | Data: backup / restore / JSON / CSV export |
|---|---|
| ![Journal](docs/screenshots/diary.png) | ![Data](docs/screenshots/data.png) |

**Open any heatmap** — click a day and that day's records appear underneath it (editable, deletable):

![Heatmap detail](docs/screenshots/heatmap-detail.png)

**Dark mode** (switch at the bottom of the sidebar, palette aligned with GitHub Dark):

| Overview | Heatmaps |
|---|---|
| ![Dark overview](docs/screenshots/dark-overview.png) | ![Dark heatmaps](docs/screenshots/dark-heatmaps.png) |

**`Ctrl+N` quick capture**: fuzzy-match a node, press Enter, type a note, press Enter again.
One input box, nothing else.

![Quick capture](docs/screenshots/quick-capture.png)

---

## 1. Quick start

### Everyday launch

Double-click `启动.pyw` in the project root.

- Opens a standalone desktop window; no console window flashes up;
- no browser, no local web server;
- no commands to type;
- closing the window quits and saves.

### First run: environment setup

The first double-click shows a small setup wizard (because `PySide6` is not installed yet).
Click **Start** and the wizard creates a project-local `.venv` and installs the dependency.
It takes one to three minutes and happens only once.

Requirements: Windows 10/11 and Python 3.9+ on the machine (used only to build the `.venv`).

---

## 2. The five pages

The sidebar has seven entries: **Overview · Heatmaps · Mind map · Process tree · Activity · Journal · Data**,
each one an independent rounded button. The whole sidebar can be collapsed with the `☰` button in the header.
`Ctrl+1` … `Ctrl+7` jumps straight to a page. Light/dark switch sits at the bottom left.

Extra shortcuts: **`Ctrl+N`** logs one activity, **`Ctrl+M`** writes one journal line. Both are minimal dialogs.

| Page | What is there |
| --- | --- |
| **Overview** | The global heatmap (all areas and processes, placed first and rendered larger than the rest), up to 3 pinned focus cards, quick capture, per-area heatmaps, recent activity |
| **Heatmaps** | One row per node (area → process → thread) with a colour bar, the name, a one-line stat and its own heatmap. Clicking a row opens a full-window version; clicking a day there lists that day's records below the grid |
| **Mind map** | XMind-style canvas. **Left-click a card = log an activity** (the dialog opens with today's date; nothing is written until you press Record). **Middle-click = that node's heatmap.** **Right-click = rename / create / move / pin / archive / delete.** Drag with the right button (or left button on empty space) to pan. `Ctrl+wheel` zooms. |
| **Process tree** | The full Area → Process → Thread tree. Reorder siblings by dragging (order is shared with the mind map and heatmaps). Create / rename / move / associate / pin / change status / archive. The right panel shows ownership, associations, next action, recent activity and the full change history |
| **Activity** | Reverse-chronological list, filterable by area / process / thread, date range and keyword. Each row keeps the ownership snapshot taken when it was recorded |
| **Journal** | One entry per day, optional. Writes into a single Markdown file (`data/diary.md`), newest first, with a year/month jump table at the top. "Open journal" opens that file in your default editor |
| **Data** | Database location, manual backup, restore, JSON import/export, CSV export of any node's history, slogan history, integrity check |

The heatmap follows GitHub's contribution graph: 11 px cells, 3 px gaps, 2 px radius, weeks across,
weekdays down, 52 weeks by default with paging back in time, and the same five-step green scale
(`0 / 1 / 2 / 3 / 4+` records). Hover shows the date and count; clicking a cell shows that day's records.

---

## 3. Concepts

**Area → Process → Thread.** Areas are the big life domains (work, health, relationships…).
Processes are ongoing efforts inside a domain. Threads are the concrete lines you actually touch day to day.
Activities can be recorded on processes or threads, never on areas.

**Association is not ownership.** A thread can be associated with several processes, but a record is
counted only where it was logged. Associations never change statistics.

**Ownership is snapshotted.** Every activity stores the area / process / thread path at the moment it was
recorded. Moving or renaming a node later never rewrites old records — the history stays true.

**Deletion has three different meanings, and each one is deliberate:**

| Action | What happens | Recoverable |
|---|---|---|
| Delete an activity | Removed completely, the heatmap for that day loses one | No |
| Delete a change-history event | Removed completely, activity data unaffected | No |
| Delete a node (thread / process / area) | Moved to a "Deleted" list; **activities, heatmaps and history are all kept** | Yes, any time |
| Archive a node | Stays in the tree, greyed out, hidden unless "show archived" is ticked | Yes |

---

## 4. Time

Everything is **Beijing time (UTC+8)**. The only source of time is `app/clock.py`; a test scans the
source tree and fails if any other module calls `datetime.now()` or `date.today()` directly.
The app does not calibrate over the network — it reads the system clock and converts it to UTC+8,
so the accuracy depends on Windows' own time sync.

---

## 5. Blank start

This repository starts **empty**: the first launch creates the schema (Area → Process → Thread,
activities, change history, associations, slogans) and writes **no** areas, processes, threads,
associations or sample activities.

Want a populated demo instead? Run this from the project folder:

```
.venv\Scripts\python.exe tools\seed_demo.py --force
```

It builds about 8 areas, 19 processes, 40 threads and ~1,500 activities spread over the last
15 months, plus a journal. **It wipes and rebuilds the current database**, so never run it on data
you care about.

---

## 6. Where the data lives

Everything sits inside the project folder — no registry, no `AppData`, no network calls:

```
data/
├── process_manager.sqlite3     database (WAL mode)
├── diary.md                    the whole journal, one Markdown file
├── backups/                    auto-<date>.sqlite3, manual-*, pre-migration-*, pre-restore-*
├── exports/                    JSON / CSV exports
├── logs/                       life_manager.log
└── config.json                 window geometry, theme, last page
```

`data/` is in `.gitignore` and must stay there — the repository is public, and
`tests/test_repo_hygiene.py` enforces it.

**Backups**: one automatic backup on the first launch of each day, containing the database and the
journal. The app never deletes backups on its own; deleting them is a manual decision.

---

## 7. Database schema

| Table | Purpose |
| --- | --- |
| `nodes` | Area / process / thread: id, name, parent, status, pinned, next action, description |
| `associations` | Thread ↔ process links, with start and end time (ended links are kept) |
| `activities` | id, target node, date, created time, note, **ownership snapshot** (area / process / thread + full path as JSON) |
| `events` | Append-only change history: type, before value, after value, timestamp |
| `meta` | Schema version and initialisation flags |

Rules: every object is addressed by id, never by name; ownership snapshots are immutable once written;
all writes go through a transaction (`BEGIN IMMEDIATE` → `COMMIT`, rollback on error); a corrupted
database is never silently wiped.

---

## 8. Common tasks

| I want to… | Do this |
| --- | --- |
| Log an activity | Header "Record activity", the overview quick capture, or the process-tree detail panel |
| Log one fast | Mind map → left-click a card → type a note → Record |
| Change the structure | Right-click a card on the mind map, or use the process tree toolbar |
| Move a thread to another process | Process tree → "Move to…" → pick the target. Earlier records keep their original ownership |
| Pin today's focus | Select a process or thread → "Pin" (max 3) |
| Add a note under a process heatmap | Heatmaps page → **right-click the process title** → type one line. Processes without a note leave no gap |
| Pause / finish / archive | Select a node → "Status ▾". Archiving is soft: nothing is deleted |
| Delete a node | Select → "Delete". It moves to the Deleted list and can be restored |
| Edit a record | Activity page → select → "Edit" (note and date; the ownership snapshot is immutable) |
| Delete a record | Activity page → select → "Delete", or right-click a row anywhere it is listed |
| Delete a journal day | Journal → right-click the day in "Days written" → delete. The Markdown section is removed too |
| Back up / restore | Data page. A restore first saves the current database as `pre-restore-*` |

---

## 9. Tests

```
.venv\Scripts\python.exe -m unittest discover -s tests -t . -p "test_*.py"
```

218 tests cover the data model, ownership snapshots, moving nodes without rewriting history,
delete/restore semantics, archiving, backups and restores, JSON import/export, the Beijing-time rule,
the journal format, the heatmap bucketing, the mind map interactions and a set of UI smoke checks.

To render the UI into `.preview/`:

```
.venv\Scripts\python.exe tools\render_preview.py
```

---

## 10. Moving to another computer

Copy the whole folder (including `data/`) to keep every record and setting, then double-click `启动.pyw`;
if the `.venv` was built on a different machine, delete it and let the wizard rebuild it.
Without `data/` you get a blank app — which is exactly what this repository ships.

---

## 11. Project layout

```
Life-Manager-2/
├── 启动.pyw                 double-click entry point (env check + no console)
├── requirements.txt
├── app/
│   ├── main.py              startup, single window, theme rebuild
│   ├── main_window.py       navigation, shortcuts, page switching
│   ├── services.py          business layer: nodes, activities, history, backup
│   ├── storage.py           SQLite schema, migrations, backups
│   ├── heatmap.py           bucketing and statistics
│   ├── diary.py             Markdown journal parser/renderer
│   ├── clock.py             the only place that reads the system clock
│   ├── theme.py             light/dark palettes and stylesheet
│   ├── pages/               six pages
│   └── widgets/             shared widgets (heatmap calendar, tables, dialogs)
├── tests/                   218 tests
├── tools/                   preview renderer, icon builder, demo data seeder
├── docs/screenshots/        the images above
└── data/                    created at runtime, never committed
```

---

## 12. Deliberately not in v1

- No accounts, no sync, no multi-device, no collaboration;
- no AI features (a design sketch lives in `docs/AI-功能草案.md`);
- no notifications or reminders;
- no mobile app or web UI.
