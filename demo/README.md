# 演示数据（虚构）

这里是一份**冻结的、虚构的**演示数据，用来快速看到程序"用了一年多"之后的样子。
里面所有领域、进程、线程、活动记录和日记都是编出来的，不含任何真实个人信息。

- `demo-data.sqlite3`：2025-07 到 2026-10 的数据库快照（8 个领域、19 个进程、40 个线程、1500+ 条活动记录）
- `diary.md`：同期的日记文件（约 170 天）

## 怎么用

**方式一：恢复（推荐）**

1. 先正常启动一次程序（`启动.pyw`），让它建好 `data/` 目录；
2. 关闭程序；
3. 把 `demo-data.sqlite3` 复制到 `data/backups/demo-data.sqlite3`；
4. 打开程序 →「数据」→ 选中这份备份 →「从选中备份恢复…」；
5. 想让日记也一起对上，再把 `diary.md` 复制到 `data/diary.md`（覆盖前建议先备份你原来的）。

**方式二：直接替换**

关闭程序后，用 `demo-data.sqlite3` 覆盖 `data/process_manager.sqlite3`，用 `diary.md` 覆盖 `data/diary.md`。

**方式三：重新生成**

```
.venv\Scripts\python.exe tools\seed_demo.py --force
```

按运行当天重新铺一遍数据，会清空并重建当前数据库。

> 注意：恢复或替换都会覆盖你当前的记录，操作前请先在「数据」页手动备份一次。
> 想回到空白状态：关闭程序，删掉 `data/process_manager.sqlite3` 与 `data/diary.md`，再启动即可（只建表，不写任何分类）。
