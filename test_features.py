# 测试新增的 3 大功能
import os, tempfile, sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TEST_DB = os.path.join(tempfile.gettempdir(), "test_big.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

import app
app.DB_PATH = TEST_DB
app.init_db()

# 1. 测试数据库迁移
conn = __import__("sqlite3").connect(TEST_DB)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
conn.close()
assert "progress_log" in tables
print("[OK] progress_log table created")

# 2. add_task 自动记录
tid = app.add_task("主轴加工", "2026-10-01", "2026-10-15", "张三", 30, "任务创建")
log_df = app.load_progress_log(tid)
assert len(log_df) == 1
assert log_df.iloc[0]["progress"] == 30
assert log_df.iloc[0]["note"] == "任务创建"
print(f"[OK] add_task auto-logged: note={log_df.iloc[0]['note']!r}")

# 3. update_task with note
app.update_task(tid, "主轴加工", "2026-10-01", "2026-10-15", "张三", 60, "完成粗车")
log_df = app.load_progress_log(tid)
assert len(log_df) == 2
assert int(log_df.iloc[0]["progress"]) == 60
assert log_df.iloc[0]["note"] == "完成粗车"
print("[OK] update_task with note recorded")

# 4. update without progress change does NOT log
app.update_task(tid, "主轴加工", "2026-10-01", "2026-10-15", "张三", 60, "")
log_df = app.load_progress_log(tid)
assert len(log_df) == 2, f"no change should not log, got {len(log_df)}"
print("[OK] no-change update does not duplicate log")

# 5. auto-generate note
app.update_task(tid, "主轴加工", "2026-10-01", "2026-10-15", "张三", 80, "")
log_df = app.load_progress_log(tid)
assert len(log_df) == 3
assert "更新进度" in log_df.iloc[0]["note"]
print(f"[OK] auto-generated note: {log_df.iloc[0]['note']!r}")

# 6. batch import logs
import pandas as pd
batch_df = pd.DataFrame({
    "name": ["A", "B"],
    "start": ["2026-10-05", "2026-10-06"],
    "end": ["2026-10-10", "2026-10-12"],
    "owner": ["李四", "王五"],
    "progress": [0, 0],
})
app.import_tasks(batch_df)
all_logs = app.load_progress_log()
batch_logs = all_logs[all_logs["note"] == "批量导入"]
assert len(batch_logs) == 2
print(f"[OK] batch import logged ({len(batch_logs)} entries)")

# 7. CASCADE delete
app.delete_task(tid)
log_after = app.load_progress_log(tid)
assert log_after.empty
print("[OK] task delete cascades to history")

# 8. render_calendar
df = app.load_tasks()
html = app.render_calendar(2026, 10, df)
assert "周" in html and "任务" in html
print(f"[OK] render_calendar HTML generated (len={len(html)})")

# 9. JOIN query
all_logs = app.load_progress_log()
assert "task_name" in all_logs.columns
print(f"[OK] load_progress_log JOIN works ({len(all_logs)} rows)")

print("\n=== ALL 9 TESTS PASSED ===")
os.remove(TEST_DB)
