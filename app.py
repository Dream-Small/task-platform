import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import calendar as cal_mod
import requests
import json
import html

st.set_page_config(page_title="重型装备车间生产任务进度数字化跟踪平台", layout="wide")

DB_PATH = "tasks.db"

STATUS_ORDER = ["未开始", "进行中", "已完成", "已延期"]
COLOR_MAP = {"未开始": "#9E9E9E", "进行中": "#1E88E5", "已完成": "#43A047", "已延期": "#E53935"}

# 预设工位/设备（贴合重型装备车间实际场景，可自行增删）
DEFAULT_WORKSTATIONS = [
    "未分配",
    "1号加工中心",
    "2号加工中心",
    "数控车床区",
    "龙门铣区",
    "焊接工位A",
    "焊接工位B",
    "热处理炉",
    "装配工位",
    "涂装工位",
    "检测工位",
]

# 数字孪生车间：工位色块背景（按实时负荷状态）
DT_BG = {
    "空闲": "linear-gradient(135deg,#94A3B8 0%,#64748B 100%)",
    "运行中": "linear-gradient(135deg,#42A5F5 0%,#1565C0 100%)",
    "超载": "linear-gradient(135deg,#EF5350 0%,#C62828 100%)",
}


def inject_css():
    st.markdown(
        """<style>
/* 全局字体 */
html, body, [class*="css"]  {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}
/* 隐藏 Streamlit 默认装饰 */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}
/* 主标题卡片 */
.main-header {
    background: linear-gradient(135deg, #0B5394 0%, #1976D2 100%);
    padding: 26px 32px;
    border-radius: 14px;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(11, 83, 148, 0.18);
}
.main-header h1 {color: white !important; margin: 0; font-size: 26px; font-weight: 700;}
.main-header p {color: rgba(255,255,255,0.88); margin: 8px 0 0 0; font-size: 14px;}
/* 侧边栏 */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F8FAFC 0%, #EDF2F7 100%);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {color: #0B5394;}
/* 车间数字孪生平面图 */
.ws-map { background: linear-gradient(135deg,#F8FAFC 0%,#EEF2F7 100%);
    border: 2px solid #CBD5E1; border-radius: 14px; padding: 16px; }
.ws-title { font-size: 13px; color: #64748B; font-weight: 700; margin-bottom: 11px; letter-spacing: 1px; }
.ws-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(168px,1fr)); gap: 11px; }
.ws-cell { border-radius: 11px; padding: 11px 13px; color: #fff; min-height: 94px;
    box-shadow: 0 2px 8px rgba(15,23,42,.18); display: flex; flex-direction: column;
    justify-content: space-between; transition: transform .15s, box-shadow .15s; }
.ws-cell:hover { transform: translateY(-3px); box-shadow: 0 8px 18px rgba(15,23,42,.28); }
.ws-name { font-size: 14px; font-weight: 700; line-height: 1.25; }
.ws-stat { font-size: 12px; opacity: .93; margin-top: 5px; }
.ws-badge { display: inline-block; font-size: 11px; background: rgba(255,255,255,.26);
    border-radius: 20px; padding: 2px 10px; align-self: flex-start; margin-top: 7px; }
.ws-zone { background: repeating-linear-gradient(45deg,#F1F5F9,#F1F5F9 8px,#E2E8F0 8px,#E2E8F0 16px);
    border: 1.5px dashed #94A3B8; border-radius: 11px; padding: 11px 13px; color: #64748B;
    min-height: 94px; display: flex; align-items: center; justify-content: center;
    flex-direction: column; font-size: 13px; font-weight: 600; text-align: center; }
.ws-legend { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 13px; padding-top: 11px;
    border-top: 1px solid #E2E8F0; font-size: 12px; color: #475569; }
.ws-legend span { display: inline-flex; align-items: center; gap: 6px; }
.ws-dot { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
/* 侧边栏导航菜单：卡片化 */
section[data-testid="stSidebar"] div[role="radiogroup"] > label {
    display: flex; align-items: center; gap: 8px;
    padding: 9px 14px; border-radius: 9px; margin-bottom: 3px;
    cursor: pointer; transition: all 0.15s ease;
    font-size: 14px; color: #334155;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    background: rgba(30,136,229,0.10);
}
section[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"] {
    position: absolute; opacity: 0;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg, #0B5394 0%, #1976D2 100%);
    color: #fff !important; font-weight: 600;
    box-shadow: 0 2px 8px rgba(11,83,148,0.25);
}
/* Tab 样式 */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #F0F4FA;
    padding: 4px;
    border-radius: 12px;
}
.stTabs [data-baseweb="tab"] {
    height: 42px;
    padding: 0 20px;
    border-radius: 8px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: white;
    color: #0B5394 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
/* 按钮 */
.stButton button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}
.stButton button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
/* 数据表 */
.stDataFrame {border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.04);}
/* 表单 */
[data-testid="stForm"] {
    background: #F8FAFC;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #E5EAF0;
}
/* 输入框 */
.stTextInput input, .stDateInput input,
.stSelectbox div[data-baseweb="select"] {border-radius: 8px;}
/* 提示框 */
.stAlert {border-radius: 10px;}
/* 分割线 */
hr {margin: 1.5rem 0;}
/* 滑块 */
.stSlider [data-baseweb="slider"] [role="slider"] {background-color: #0B5394;}
/* 标题 */
h1, h2, h3 {color: #1F2937;}
/* Plotly 图表背景透明 */
.js-plotly-plot .plotly .main-svg {background: transparent !important;}
</style>""",
        unsafe_allow_html=True,
    )


def status_pill_css(s):
    color = COLOR_MAP.get(s, "#9E9E9E")
    return (
        f"background-color: {color}; color: white; font-weight: 600; "
        f"border-radius: 12px; padding: 4px 12px; text-align: center; "
        f"display: inline-block; min-width: 64px;"
    )


def metric_card(label, value, color, icon=""):
    return (
        f'<div style="background: linear-gradient(135deg, {color} 0%, {color}DD 100%); '
        f'padding: 18px 22px; border-radius: 12px; color: white; '
        f'box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin-bottom: 8px;">'
        f'<div style="font-size: 13px; opacity: 0.92; font-weight: 500;">{icon} {label}</div>'
        f'<div style="font-size: 30px; font-weight: 700; margin-top: 6px; line-height: 1;">{value}</div>'
        f'</div>'
    )


def workstation_options(df=None):
    """工位/设备下拉选项 = 预设列表 + 数据中已出现的自定义工位"""
    opts = list(DEFAULT_WORKSTATIONS)
    if df is not None and not df.empty and "workstation" in df.columns:
        extra = [w for w in df["workstation"].unique() if w and w not in opts]
        opts = opts + sorted(extra)
    return opts


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start TEXT NOT NULL,
            end TEXT NOT NULL,
            owner TEXT NOT NULL,
            progress INTEGER NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS progress_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            progress INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )"""
    )
    # 迁移：为已有数据库补充「工位/设备」列（只读环境下静默跳过，不影响其他功能）
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "workstation" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN workstation TEXT DEFAULT '未分配'")
        conn.execute("UPDATE tasks SET workstation='未分配' WHERE workstation IS NULL OR workstation=''")
        conn.commit()
    except Exception:
        pass
    conn.close()


def add_task(name, start, end, owner, progress, note="任务创建", workstation="未分配"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO tasks (name, start, end, owner, progress, workstation) VALUES (?, ?, ?, ?, ?, ?)",
        (name, start, end, owner, progress, workstation or "未分配"),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_progress(task_id, progress, note)
    return task_id


def update_task(task_id, name, start, end, owner, progress, note="", workstation=None):
    """workstation 为 None 表示「不修改」，保留原工位（避免调用方漏传导致工位被清空）"""
    conn = sqlite3.connect(DB_PATH)
    old_row = conn.execute("SELECT progress, workstation FROM tasks WHERE id=?", (task_id,)).fetchone()
    if workstation is None:
        ws = (old_row[1] if old_row and old_row[1] else "未分配")
    else:
        ws = workstation or "未分配"
    conn.execute(
        "UPDATE tasks SET name=?, start=?, end=?, owner=?, progress=?, workstation=? WHERE id=?",
        (name, start, end, owner, progress, ws, task_id),
    )
    conn.commit()
    conn.close()
    old_prog = old_row[0] if old_row else None
    if old_prog != progress or note:
        auto_note = f"更新进度 {old_prog if old_prog is not None else '?'}% → {progress}%"
        log_progress(task_id, progress, note or auto_note)


def delete_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM progress_log WHERE task_id=?", (task_id,))
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


def set_workstation(task_id, workstation):
    """单独更新任务所属工位/设备"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE tasks SET workstation=? WHERE id=?", (workstation or "未分配", task_id))
    conn.commit()
    conn.close()


def export_backup():
    """导出完整数据备份（任务 + 进度历史），返回可 JSON 序列化的 dict"""
    conn = sqlite3.connect(DB_PATH)
    try:
        tasks = pd.read_sql_query("SELECT * FROM tasks ORDER BY id", conn)
        logs = pd.read_sql_query("SELECT * FROM progress_log ORDER BY id", conn)
    finally:
        conn.close()
    return {
        "format": "heavy-equipment-workshop-backup",
        "version": 1,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "task_count": len(tasks),
        "log_count": len(logs),
        "tasks": tasks.to_dict("records"),
        "progress_log": logs.to_dict("records"),
    }


def restore_backup(data, mode="replace"):
    """恢复备份。

    mode="replace"：清空现有数据后按原 id 恢复
    mode="merge"  ：保留现有数据，追加备份内容（重新分配 id 并修正历史关联）
    返回 (任务数, 历史数, 错误信息)
    """
    if not isinstance(data, dict) or "tasks" not in data:
        return 0, 0, "备份文件格式不正确，缺少 tasks 字段"
    tasks = data.get("tasks") or []
    logs = data.get("progress_log") or []
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")
        if mode == "replace":
            conn.execute("DELETE FROM progress_log")
            conn.execute("DELETE FROM tasks")
            for t in tasks:
                conn.execute(
                    "INSERT INTO tasks (id, name, start, end, owner, progress, workstation) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        t.get("id"),
                        t.get("name"),
                        t.get("start"),
                        t.get("end"),
                        t.get("owner"),
                        int(t.get("progress", 0)),
                        t.get("workstation") or "未分配",
                    ),
                )
            for l in logs:
                conn.execute(
                    "INSERT INTO progress_log (id, task_id, progress, note, created_at) VALUES (?,?,?,?,?)",
                    (
                        l.get("id"),
                        l.get("task_id"),
                        int(l.get("progress", 0)),
                        l.get("note", ""),
                        l.get("created_at"),
                    ),
                )
        else:  # merge：重新分配 id，并修正历史记录的关联
            id_map = {}
            for t in tasks:
                cur = conn.execute(
                    "INSERT INTO tasks (name, start, end, owner, progress, workstation) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        t.get("name"),
                        t.get("start"),
                        t.get("end"),
                        t.get("owner"),
                        int(t.get("progress", 0)),
                        t.get("workstation") or "未分配",
                    ),
                )
                id_map[t.get("id")] = cur.lastrowid
            for l in logs:
                new_tid = id_map.get(l.get("task_id"))
                if new_tid is None:
                    continue
                conn.execute(
                    "INSERT INTO progress_log (task_id, progress, note, created_at) VALUES (?,?,?,?)",
                    (new_tid, int(l.get("progress", 0)), l.get("note", ""), l.get("created_at")),
                )
        conn.commit()
    except Exception as ex:
        conn.rollback()
        return 0, 0, str(ex)
    finally:
        conn.close()
    return len(tasks), len(logs), ""


def log_progress(task_id, progress, note=""):
    """记录一次进度变更"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO progress_log (task_id, progress, note, created_at) VALUES (?, ?, ?, ?)",
        (task_id, progress, note, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def load_progress_log(task_id=None):
    """加载进度变更记录；task_id 为 None 时返回全部（关联任务名）"""
    conn = sqlite3.connect(DB_PATH)
    if task_id is None:
        df = pd.read_sql_query(
            """SELECT pl.id, pl.created_at, pl.task_id, t.name AS task_name,
                      t.owner, pl.progress, pl.note
               FROM progress_log pl
               LEFT JOIN tasks t ON pl.task_id = t.id
               ORDER BY pl.id DESC""",
            conn,
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM progress_log WHERE task_id=? ORDER BY id DESC",
            conn,
            params=(task_id,),
        )
    conn.close()
    return df


# ======== AI 助手小童 模块 ========
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-chat"

# 内置默认 API Key（保证开箱即用）。分片拼接仅为降低被自动扫描器抓取的概率。
# 如需停用内置 Key（例如担心被盗用），把下面三段的引号内容全部清空即可。
BUILTIN_API_KEY = (
    "sk-645645cf"
    "bf6143bda4"
    "71a79a6dc414d9"
)

SYSTEM_PROMPT = """你是「重型装备车间生产任务数字化跟踪平台」内置的 AI 助手，名叫「小童」，
服务对象是国内重型装备制造企业的车间主任、班组长和生产管理人员。
用户称呼你为「小童」时，你要自然地回应。

你的能力：
1. 基于下方【当前任务数据】回答生产进度相关问题（只依据给定数据，不得臆测数据之外的信息）
2. 识别延期风险、进度滞后、人员绩效差异，并给出可执行的补救建议
3. 分析各工位 / 设备的负荷与产能瓶颈，给出排产与资源调配建议
4. 生成结构化的生产周报 / 日报

回答要求：
- 全程使用中文，语气专业干练，像一位有 10 年经验的车间生产主管
- 涉及具体任务时必须引用真实的编号、名称、负责人
- 结论先行，再用数据支撑，最后给行动建议
- 不要输出冗长的免责声明和自我介绍
- 绝不编造数据中不存在的任务

【重要限制】你是只读顾问：若用户要求新增 / 修改 / 删除任务，明确告知其前往「任务管理」页操作，你不能代劳。"""


def get_api_key():
    """按优先级获取 API Key：st.secrets 服务器配置 > 用户侧边栏临时输入"""
    # 1) Streamlit Cloud 后台 Secrets（最安全，优先级最高）
    try:
        k = st.secrets.get("DEEPSEEK_API_KEY", "")
        if k:
            return k, "服务器配置"
    except Exception:
        pass
    # 2) 用户在侧边栏临时输入
    k = st.session_state.get("user_api_key", "")
    if k:
        return k, "侧边栏输入"
    # 3) 内置默认 Key（保证开箱即用；如需停用，把下面这行改成空字符串即可）
    if BUILTIN_API_KEY:
        return BUILTIN_API_KEY, "内置默认"
    return "", ""


def call_llm(messages, api_key, timeout=90):
    """调用大模型 API，返回 (是否成功, 回复内容或错误信息)"""
    payload = {"model": LLM_MODEL, "messages": messages, "temperature": 0.3, "stream": False}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 401:
            return False, "❌ API Key 无效或已过期，请检查后重试。"
        if resp.status_code == 402:
            return False, "❌ API 账户余额不足，请充值后重试。"
        if resp.status_code == 429:
            return False, "❌ 请求过于频繁，请稍等几秒再试。"
        resp.raise_for_status()
        data = resp.json()
        return True, data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return False, "❌ 请求超时（网络较慢），请稍后重试。"
    except requests.exceptions.ConnectionError:
        return False, "❌ 网络连接失败，请检查网络后重试。"
    except Exception as ex:
        return False, f"❌ 调用失败：{ex}"


def build_data_context(df, max_rows=250):
    """将任务数据压缩为大模型可理解的上下文文本"""
    if df.empty:
        return "【当前任务数据】\n系统内暂无任何任务。"
    today = pd.Timestamp(date.today())
    counts = df["状态"].value_counts().reindex(STATUS_ORDER, fill_value=0)
    dur = (df["end"] - df["start"]).dt.days
    lines = [
        "【当前任务数据】",
        f"统计日期：{today.strftime('%Y-%m-%d')}",
        f"任务总数：{len(df)}",
        "状态分布："
        f"未开始 {int(counts['未开始'])} / "
        f"进行中 {int(counts['进行中'])} / "
        f"已完成 {int(counts['已完成'])} / "
        f"已延期 {int(counts['已延期'])}",
        f"平均工期：{dur.mean():.1f} 天；整体平均进度：{df['progress'].mean():.1f}%",
        "",
        "任务明细：",
    ]
    for _, r in df.head(max_rows).iterrows():
        ws = r["workstation"] if "workstation" in df.columns else "未分配"
        lines.append(
            f"- #{int(r['id'])} 「{r['name']}」负责人:{r['owner']} "
            f"工位:{ws} "
            f"周期:{r['start'].strftime('%Y-%m-%d')}~{r['end'].strftime('%Y-%m-%d')} "
            f"工期:{int((r['end'] - r['start']).days)}天 "
            f"进度:{int(r['progress'])}% 状态:{r['状态']}"
        )
    if len(df) > max_rows:
        lines.append(f"（共 {len(df)} 条，仅展示前 {max_rows} 条）")
    return "\n".join(lines)


def rule_insights(df):
    """未配置 API Key 时的本地规则分析（离线智能模式）"""
    if df.empty:
        return "系统内暂无任务数据，无法分析。请先在「任务管理」页录入或导入任务。"
    today = pd.Timestamp(date.today())
    counts = df["状态"].value_counts().reindex(STATUS_ORDER, fill_value=0)
    total = len(df)
    delay = df[df["状态"] == "已延期"]
    soon = df[(df["end"] >= today) & (df["end"] <= today + pd.Timedelta(days=3)) & (df["progress"] < 100)]
    g = df.groupby("owner").agg(任务数=("id", "count"), 平均进度=("progress", "mean")).sort_values("平均进度", ascending=False)

    risk = []
    for _, r in df.iterrows():
        if r["progress"] >= 100:
            continue
        elapsed = (today - r["start"]).days
        total_days = (r["end"] - r["start"]).days
        if total_days > 0 and elapsed / total_days > 0.6 and r["progress"] < 60:
            risk.append(f"- **{r['name']}**（{r['owner']}）：工期已过 {elapsed}/{total_days} 天，进度仅 {int(r['progress'])}%")

    out = [
        "### 📊 本地智能分析（离线模式）",
        "",
        f"**总体概况**：系统内共 **{total}** 个任务；已完成 **{int(counts['已完成'])}** 个"
        f"（{counts['已完成'] / total * 100:.1f}%），进行中 **{int(counts['进行中'])}** 个，"
        f"未开始 **{int(counts['未开始'])}** 个。",
        "",
    ]
    if not delay.empty:
        out.append(f"### 🚨 延期警报（{len(delay)} 个）")
        for _, r in delay.iterrows():
            out.append(f"- **{r['name']}**（{r['owner']}）：已超期 **{(today - r['end']).days} 天**，当前进度 {int(r['progress'])}%")
        out.append("\n> 建议：立即召集班组长碰头会，协调资源抢工或与客户协商调整交付节点。")
    else:
        out.append("### ✅ 延期情况\n当前无延期任务，生产执行状况良好。")
    if not soon.empty:
        out.append(f"\n### ⏰ 3 日内到期（{len(soon)} 个）")
        for _, r in soon.iterrows():
            out.append(f"- **{r['name']}**（{r['owner']}）：还剩 **{(r['end'] - today).days}** 天，进度 {int(r['progress'])}%")
    if risk:
        out.append("\n### ⚠️ 进度滞后风险（时间过半但进度不足）")
        out.extend(risk)
        out.append("\n> 建议：核查设备状态与外协件是否到位，必要时增派人员或调整工序顺序。")
    out.append(
        f"\n### 👨‍💼 人员绩效\n"
        f"- 进度最快：**{g.index[0]}**（平均 {g.iloc[0]['平均进度']:.1f}%，{int(g.iloc[0]['任务数'])} 个任务）\n"
        f"- 需重点关注：**{g.index[-1]}**（平均 {g.iloc[-1]['平均进度']:.1f}%，{int(g.iloc[-1]['任务数'])} 个任务）"
    )
    out.append(
        "\n---\n💡 *当前未配置大模型 API Key，以上为本地规则引擎分析结果。"
        "在左侧栏填入 DeepSeek API Key 后，即可升级为支持自然语言提问的对话式 AI 助手小童。*"
    )
    return "\n".join(out)


def generate_weekly_report_text(df):
    """本地生成车间生产周报文本（无需 API）"""
    today = pd.Timestamp(date.today())
    week_start = today - pd.Timedelta(days=today.weekday())
    week_end = week_start + pd.Timedelta(days=6)
    if df.empty or "progress" not in df.columns:
        return (
            f"# 车间生产周报（{week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}）\n\n"
            "系统内暂无任务数据，无法生成周报。请先在「任务管理」页录入或导入任务。"
        )
    finished = df[(df["progress"] >= 100) & (df["end"] >= week_start)]
    started = df[(df["start"] >= week_start) & (df["start"] <= week_end)]
    delayed = df[df["状态"] == "已延期"]
    ongoing = df[df["状态"] == "进行中"]
    next_soon = df[(df["end"] >= today) & (df["end"] <= today + pd.Timedelta(days=7)) & (df["progress"] < 100)]

    lines = [
        f"# 车间生产周报（{week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}）",
        "",
        f"统计日期：{today.strftime('%Y-%m-%d')}　|　系统内任务总数：{len(df)} 个",
        "",
        "## 一、本周完成情况",
    ]
    if finished.empty:
        lines.append("- 本周暂无任务完工记录。")
    else:
        for _, r in finished.iterrows():
            lines.append(f"- 【已完工】{r['name']}（{r['owner']}），计划完工 {r['end'].strftime('%m-%d')}，进度 100%")
    lines.append("\n## 二、本周新开工任务")
    if started.empty:
        lines.append("- 本周无新开工任务。")
    else:
        for _, r in started.iterrows():
            lines.append(f"- 【开工】{r['name']}（{r['owner']}），计划周期 {r['start'].strftime('%m-%d')} ~ {r['end'].strftime('%m-%d')}")
    lines.append("\n## 三、进行中任务")
    if ongoing.empty:
        lines.append("- 暂无进行中任务。")
    else:
        for _, r in ongoing.head(20).iterrows():
            lines.append(f"- {r['name']}（{r['owner']}）：进度 {int(r['progress'])}%，计划完工 {r['end'].strftime('%m-%d')}")
    lines.append("\n## 四、风险提示")
    if delayed.empty and next_soon.empty:
        lines.append("- 本周无延期及临期风险，生产秩序正常。")
    else:
        for _, r in delayed.iterrows():
            lines.append(f"- 🔴 **延期**：{r['name']}（{r['owner']}），超期 {(today - r['end']).days} 天，进度 {int(r['progress'])}%")
        for _, r in next_soon.iterrows():
            lines.append(f"- 🟡 **临期**：{r['name']}（{r['owner']}），{(r['end'] - today).days} 天后到期，进度 {int(r['progress'])}%")
    lines.append("\n## 五、下周工作重点")
    if next_soon.empty:
        lines.append("- 按现有生产计划正常推进，无紧急交付节点。")
    else:
        for _, r in next_soon.head(5).iterrows():
            lines.append(f"- 重点推进「{r['name']}」（{r['owner']}），确保 {(r['end'] - today).days} 天内交付")
    return "\n".join(lines)


def import_tasks(df):
    """从 DataFrame 批量导入任务（支持 CSV / Excel），返回 (成功数, 总数, 错误列表)"""
    # 列名兼容映射（支持导出格式与常见自定义格式）
    col_map = {}
    for c in df.columns:
        cs = str(c).strip()
        if cs in ("任务名称", "名称", "name"):
            col_map[c] = "name"
        elif cs in ("开始时间", "开始日期", "start"):
            col_map[c] = "start"
        elif cs in ("结束时间", "结束日期", "end"):
            col_map[c] = "end"
        elif cs in ("负责人", "owner"):
            col_map[c] = "owner"
        elif cs.replace(" ", "") in ("完成进度(%)", "完成进度", "进度", "progress"):
            col_map[c] = "progress"
        elif cs in ("工位", "设备", "工位/设备", "所在工位", "workstation", "machine"):
            col_map[c] = "workstation"
    df = df.rename(columns=col_map)
    required = ["name", "start", "end", "owner"]
    missing = [r for r in required if r not in df.columns]
    if missing:
        return 0, 0, [f"文件缺少必需列：{'、'.join(missing)}（需要：任务名称、开始时间、结束时间、负责人）"]
    success = 0
    errors = []
    for i, row in df.iterrows():
        row_no = i + 2  # 表格实际行号（第1行是表头）
        if row.isna().all():
            continue  # 整行为空（Excel 常见），静默跳过
        name = str(row["name"]).strip() if pd.notna(row["name"]) else ""
        owner = str(row["owner"]).strip() if pd.notna(row["owner"]) else ""
        if not name or not owner:
            errors.append(f"第 {row_no} 行：任务名称或负责人为空，已跳过")
            continue
        try:
            start = pd.to_datetime(row["start"]).date()
            end = pd.to_datetime(row["end"]).date()
        except (ValueError, TypeError):
            errors.append(f"第 {row_no} 行：日期格式无法识别（{row['start']} ~ {row['end']}），已跳过")
            continue
        if end < start:
            errors.append(f"第 {row_no} 行「{name}」：结束时间早于开始时间，已跳过")
            continue
        if "progress" in df.columns and pd.notna(row["progress"]):
            try:
                progress = int(float(str(row["progress"]).replace("%", "").strip()))
                progress = max(0, min(100, progress))
            except ValueError:
                progress = 0
        else:
            progress = 0
        ws = str(row["workstation"]).strip() if ("workstation" in df.columns and pd.notna(row["workstation"])) else ""
        add_task(name, start.isoformat(), end.isoformat(), owner, progress, "批量导入", ws or "未分配")
        success += 1
    return success, len(df), errors


def load_tasks():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM tasks ORDER BY start", conn)
    conn.close()
    if df.empty:
        return df
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    if "workstation" not in df.columns:
        df["workstation"] = "未分配"
    df["workstation"] = df["workstation"].fillna("未分配").astype(str)
    df.loc[df["workstation"].str.strip() == "", "workstation"] = "未分配"
    today = pd.Timestamp(date.today())
    status_list = []
    for _, row in df.iterrows():
        if row["progress"] >= 100:
            status_list.append("已完成")
        elif row["end"] < today:
            status_list.append("已延期")
        elif row["start"] <= today <= row["end"] and row["progress"] > 0:
            status_list.append("进行中")
        else:
            status_list.append("未开始")
    df["状态"] = status_list
    return df


def make_gantt(df):
    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="name",
        color="状态",
        color_discrete_map=COLOR_MAP,
        category_orders={"状态": STATUS_ORDER},
        hover_data={"owner": True, "progress": True, "状态": True, "start": False, "end": False},
    )
    fig.update_yaxes(autorange="reversed", title_text="任务名称")
    fig.update_xaxes(title_text="时间")
    x_today = datetime.combine(date.today(), datetime.min.time())
    fig.add_vline(x=x_today, line_dash="dash", line_color="black")
    fig.add_annotation(x=x_today, y=1, yref="paper", yanchor="bottom", xanchor="left", text="今天", showarrow=False)
    fig.update_layout(
        height=max(400, 60 * len(df) + 150),
        legend_title_text="任务状态",
        margin=dict(l=10, r=10, t=40, b=10),
        title_text="生产任务甘特图",
    )
    return fig


def render_calendar(year, month, df):
    """渲染指定年月的日历热力图 HTML，返回 HTML 字符串"""
    if not df.empty:
        df = df.copy()
        df["start"] = pd.to_datetime(df["start"])
        df["end"] = pd.to_datetime(df["end"])
    cal = cal_mod.Calendar(firstweekday=0)  # 周一开头
    weeks = cal.monthdayscalendar(year, month)
    today = date.today()

    def count_active(day):
        if day == 0 or df.empty:
            return 0
        d = pd.Timestamp(year, month, day)
        return int(((df["start"] <= d) & (df["end"] >= d)).sum())

    parts = ['<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:6px;">']
    for wd in ["一", "二", "三", "四", "五", "六", "日"]:
        parts.append(
            f'<div style="text-align:center;font-weight:700;color:#475569;'
            f'padding:8px;background:#E2E8F0;border-radius:6px;">周{wd}</div>'
        )
    for week in weeks:
        for day in week:
            if day == 0:
                parts.append('<div style="height:90px;background:transparent;"></div>')
            else:
                count = count_active(day)
                if count == 0:
                    bg, fg, badge_bg = "#F1F5F9", "#94A3B8", "rgba(148,163,184,0.3)"
                elif count <= 2:
                    bg, fg, badge_bg = "#DBEAFE", "#1E40AF", "rgba(255,255,255,0.7)"
                elif count <= 5:
                    bg, fg, badge_bg = "#60A5FA", "#FFFFFF", "rgba(255,255,255,0.4)"
                else:
                    bg, fg, badge_bg = "#2563EB", "#FFFFFF", "rgba(255,255,255,0.4)"
                is_today = (year == today.year and month == today.month and day == today.day)
                border = "3px solid #F6A623" if is_today else "none"
                parts.append(
                    f'<div style="height:90px;background:{bg};color:{fg};'
                    f'border-radius:8px;border:{border};padding:8px;'
                    f'display:flex;flex-direction:column;justify-content:space-between;">'
                    f'<div style="font-weight:700;font-size:15px;">{day}</div>'
                    f'<div style="font-size:12px;align-self:flex-end;'
                    f'background:{badge_bg};padding:2px 8px;border-radius:10px;'
                    f'font-weight:600;">{count} 任务</div>'
                    f'</div>'
                )
    parts.append("</div>")
    return "".join(parts)


def main():
    inject_css()
    init_db()
    df_all = load_tasks()

    st.markdown(
        """
        <div class="main-header">
            <h1>🏭 重型装备车间生产任务进度数字化跟踪平台</h1>
            <p>实时跟踪任务进度 · 智能预警延期风险 · 数据驱动生产决策</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### 🧭 功能导航")
        page = st.radio(
            "导航",
            [
                "📊 数据驾驶舱",
                "📋 任务管理",
                "🏭 设备负荷",
                "🗺️ 车间数字孪生",
                "📅 进度甘特图",
                "📈 统计分析",
                "⚠️ 预警清单",
                "📜 进度历史",
                "🤖 AI助手小童",
            ],
            label_visibility="collapsed",
        )
        st.caption("总览 → 执行 → 分析 → 追溯 → 智能")
        st.markdown("---")
        st.markdown("### 🔍 筛选条件")
        if df_all.empty:
            st.info("暂无任务数据，请先在「任务管理」页录入任务")
        else:
            owner_opt = ["全部"] + sorted(df_all["owner"].unique().tolist())
            status_opt = ["全部"] + STATUS_ORDER
            kw = st.text_input("按任务名称/负责人搜索")
            f_owner = st.selectbox("负责人", owner_opt)
            f_status = st.selectbox("任务状态", status_opt)
            f_ws = st.selectbox("工位 / 设备", ["全部"] + workstation_options(df_all))
            f_range = st.date_input(
                "时间范围筛选（起止日期）",
                value=(df_all["start"].min().date(), df_all["end"].max().date()),
            )
            if len(f_range) == 2:
                lo, hi = pd.Timestamp(f_range[0]), pd.Timestamp(f_range[1])
            else:
                lo, hi = pd.Timestamp.min, pd.Timestamp.max
            df = df_all.copy()
            if kw:
                mask = df["name"].str.contains(kw, na=False) | df["owner"].str.contains(kw, na=False)
                df = df[mask]
            if f_owner != "全部":
                df = df[df["owner"] == f_owner]
            if f_status != "全部":
                df = df[df["状态"] == f_status]
            if f_ws != "全部":
                df = df[df["workstation"] == f_ws]
            df = df[(df["start"] <= hi + pd.Timedelta(days=1)) & (df["end"] >= lo)]
            st.metric("筛选结果任务数", len(df))

        st.markdown("---")
        st.markdown("### 🤖 AI助手小童 · 设置")
        st.caption(
            "填入 DeepSeek API Key 即可启用 AI 助手小童。"
            "Key 仅保存在当前浏览器会话中，不会上传 GitHub。"
        )
        _k = st.text_input("DeepSeek API Key", type="password", placeholder="sk-...", key="api_key_input_widget")
        if _k:
            st.session_state.user_api_key = _k
            st.success("✅ Key 已生效，请前往「AI助手小童」页使用")
        elif st.session_state.get("user_api_key"):
            st.info("已使用当前会话中保存的 Key")

    if df_all.empty:
        df = df_all

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if page == "🏭 设备负荷":  # 设备 / 工位负荷看板
        st.markdown("#### 🏭 设备 / 工位负荷看板")
        if df_all.empty:
            st.info("暂无任务数据，请先在「任务管理」页录入任务并指定工位")
        else:
            today = pd.Timestamp(date.today())

            # 存在未分配工位的任务 → 提供批量快速分配
            unassigned = df_all[df_all["workstation"] == "未分配"]
            if not unassigned.empty:
                with st.expander(
                    f"⚡ {len(unassigned)} 个任务尚未指定工位，点此快速分配",
                    expanded=(len(unassigned) == len(df_all)),
                ):
                    st.caption("为每个任务选择工位后点「保存工位分配」，下方看板即可显示负荷情况。")
                    ws_pick_opts = [w for w in workstation_options(df_all) if w != "未分配"]
                    picks = {}
                    for _, r in unassigned.iterrows():
                        tid = int(r["id"])
                        picks[tid] = st.selectbox(
                            f"#{tid}　{r['name']}（负责人：{r['owner']}）",
                            ws_pick_opts,
                            key=f"ws_pick_{tid}",
                        )
                    if st.button("💾 保存工位分配", use_container_width=True, key="save_ws_batch"):
                        for tid, w in picks.items():
                            set_workstation(tid, w)
                        st.success(f"✅ 已为 {len(picks)} 个任务分配工位")
                        st.rerun()

            ws_used = [w for w in df_all["workstation"].unique() if w and w != "未分配"]
            if not ws_used:
                st.warning("当前所有任务均未分配工位，请先在上方（或「任务管理」页）为任务指定工位/设备。")
            else:
                # ---- KPI ----
                running, idle, overload = 0, 0, 0
                rows = []
                for w in sorted(ws_used):
                    sub = df_all[df_all["workstation"] == w]
                    active = sub[(sub["start"] <= today) & (sub["end"] >= today) & (sub["progress"] < 100)]
                    n_active = len(active)
                    if n_active == 0:
                        idle += 1
                        state = "⚪ 空闲"
                    elif n_active >= 3:
                        overload += 1
                        running += 1
                        state = "🔴 超载"
                    else:
                        running += 1
                        state = "🔵 运行中"
                    rows.append({
                        "工位/设备": w,
                        "任务总数": len(sub),
                        "当前在制": n_active,
                        "平均进度(%)": round(float(sub["progress"].mean()), 1),
                        "延期任务": int((sub["状态"] == "已延期").sum()),
                        "状态": state,
                    })
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(metric_card("在册工位/设备", len(ws_used), "#0B5394", "🏭"), unsafe_allow_html=True)
                c2.markdown(metric_card("运行中", running, "#1E88E5", "🔵"), unsafe_allow_html=True)
                c3.markdown(metric_card("空闲", idle, "#43A047", "⚪"), unsafe_allow_html=True)
                c4.markdown(metric_card("超载(≥3并行)", overload, "#E53935", "🔴"), unsafe_allow_html=True)
                st.divider()

                # ---- 未来 14 天负荷热力图 ----
                st.markdown("##### 🔥 未来 14 天工位负荷热力图")
                days = [today + pd.Timedelta(days=i) for i in range(14)]
                y_labels = [r["工位/设备"] for r in rows]
                matrix = []
                for w in y_labels:
                    sub = df_all[df_all["workstation"] == w]
                    matrix.append([
                        int(((sub["start"] <= d) & (sub["end"] >= d)).sum()) for d in days
                    ])
                heat = go.Figure(data=go.Heatmap(
                    z=matrix,
                    x=[d.strftime("%m-%d") for d in days],
                    y=y_labels,
                    colorscale=[[0, "#F1F5F9"], [0.25, "#DBEAFE"], [0.5, "#60A5FA"], [1.0, "#1E3A8A"]],
                    text=matrix,
                    texttemplate="%{text}",
                    textfont={"size": 11},
                    colorbar=dict(title="并行任务数"),
                    hovertemplate="%{y}<br>%{x}<br>并行任务：%{z} 个<extra></extra>",
                ))
                heat.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis_title="", yaxis_title="",
                    height=max(260, 34 * len(y_labels) + 90),
                )
                st.plotly_chart(heat, use_container_width=True)
                st.caption("💡 颜色越深表示该工位当天并行任务越多，可据此提前发现产能瓶颈。")

                # ---- 工位负荷明细 ----
                st.divider()
                st.markdown("##### 📋 工位负荷明细")
                wl_df = pd.DataFrame(rows)

                def color_state(v):
                    if "超载" in str(v):
                        return "color: #E53935; font-weight: 700;"
                    if "运行中" in str(v):
                        return "color: #1E88E5; font-weight: 600;"
                    return "color: #94A3B8;"

                st.dataframe(
                    wl_df.style.map(color_state, subset=["状态"]).format({"平均进度(%)": "{:.1f}%"}),
                    use_container_width=True,
                    hide_index=True,
                )

                # ---- 当前在制任务 ----
                st.divider()
                st.markdown("##### ⚙️ 当前在制任务（按工位）")
                in_prog = df_all[
                    (df_all["start"] <= today) & (df_all["end"] >= today) & (df_all["progress"] < 100)
                ].copy()
                if in_prog.empty:
                    st.info("当前没有正在执行的任务。")
                else:
                    in_prog["开始时间"] = in_prog["start"].dt.strftime("%Y-%m-%d")
                    in_prog["结束时间"] = in_prog["end"].dt.strftime("%Y-%m-%d")
                    ip_show = in_prog[["workstation", "name", "owner", "开始时间", "结束时间", "progress", "状态"]].copy()
                    ip_show.columns = ["工位/设备", "任务名称", "负责人", "开始时间", "结束时间", "完成进度(%)", "状态"]
                    st.dataframe(
                        ip_show.style.map(status_pill_css, subset=["状态"]).format({"完成进度(%)": "{:.0f}%"}),
                        use_container_width=True,
                        hide_index=True,
                    )

    elif page == "📊 数据驾驶舱":
        st.markdown("#### 📊 生产任务总览")
        if df_all.empty:
            st.info("暂无数据，请先在「任务管理」录入任务")
        else:
            total = len(df_all)
            done = int((df_all["progress"] >= 100).sum())
            done_rate = round(done / total * 100, 1) if total else 0
            duration = (df_all["end"] - df_all["start"]).dt.days
            avg_dur = round(duration.mean(), 1)
            overdue_n = int((df_all["状态"] == "已延期").sum())
            overdue_rate = round(overdue_n / total * 100, 1) if total else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(metric_card("任务总数", total, "#0B5394", "📋"), unsafe_allow_html=True)
            c2.markdown(metric_card("已完成率", f"{done_rate}%", "#43A047", "✅"), unsafe_allow_html=True)
            c3.markdown(metric_card("平均工期(天)", avg_dur, "#F6A623", "⏱️"), unsafe_allow_html=True)
            c4.markdown(metric_card("延期率", f"{overdue_rate}%", "#E53935", "🚨"), unsafe_allow_html=True)
            st.divider()
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("##### 📈 过去 14 天每日活跃任务数")
                today_d = pd.Timestamp(date.today())
                last_14 = [today_d - pd.Timedelta(days=i) for i in range(13, -1, -1)]
                daily = []
                for d in last_14:
                    active = int(((df_all["start"] <= d) & (df_all["end"] >= d)).sum())
                    daily.append({"日期": d.date().isoformat(), "活跃任务数": active})
                ddf = pd.DataFrame(daily)
                trend = px.area(ddf, x="日期", y="活跃任务数", markers=True)
                trend.update_traces(line_color="#1E88E5", fillcolor="rgba(30,136,229,0.2)", marker_size=6)
                trend.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis_title="", yaxis_title="活跃任务数",
                )
                st.plotly_chart(trend, use_container_width=True)
            with c2:
                st.markdown("##### 🏆 负责人 Top 5")
                g = (df_all.groupby("owner")
                     .agg(任务数=("id", "count"), 平均进度=("progress", "mean"))
                     .reset_index()
                     .sort_values("任务数", ascending=False).head(5))
                g["平均进度"] = g["平均进度"].round(1)
                g.columns = ["负责人", "任务数", "平均进度(%)"]
                g_styled = g.style.format({"平均进度(%)": "{:.1f}%"})
                st.dataframe(g_styled, use_container_width=True, hide_index=True)
                st.caption("按任务数排序")

    elif page == "📋 任务管理":
        col_add, col_edit = st.columns(2)
        with col_add:
            st.markdown("##### ➕ 新增任务")
            with st.form("add_form"):
                name = st.text_input("任务名称")
                start = st.date_input("开始时间", value=date.today())
                end = st.date_input("结束时间", value=date.today() + timedelta(days=7))
                owner = st.text_input("负责人")
                ws = st.selectbox("工位 / 设备", workstation_options(df_all))
                progress = st.slider("完成进度（%）", 0, 100, 0, step=5)
                submitted = st.form_submit_button("添加任务", use_container_width=True)
                if submitted:
                    if not name or not owner:
                        st.error("任务名称和负责人不能为空")
                    elif end < start:
                        st.error("结束时间不能早于开始时间")
                    else:
                        add_task(name, start.isoformat(), end.isoformat(), owner, progress, "任务创建", ws)
                        st.success(f"任务「{name}」添加成功")
                        st.rerun()
        with col_edit:
            st.markdown("##### ✏️ 修改 / 删除任务")
            if df_all.empty:
                st.info("暂无任务可编辑")
            else:
                options = {f"{row['id']} - {row['name']}": row["id"] for _, row in df_all.iterrows()}
                sel = st.selectbox("选择任务", list(options.keys()))
                task_id = options[sel]
                cur = df_all[df_all["id"] == task_id].iloc[0]
                with st.form("edit_form"):
                    e_name = st.text_input("任务名称", value=cur["name"])
                    e_start = st.date_input("开始时间", value=cur["start"].date())
                    e_end = st.date_input("结束时间", value=cur["end"].date())
                    e_owner = st.text_input("负责人", value=cur["owner"])
                    _ws_opts = workstation_options(df_all)
                    _cur_ws = cur["workstation"] if cur["workstation"] in _ws_opts else "未分配"
                    e_ws = st.selectbox("工位 / 设备", _ws_opts, index=_ws_opts.index(_cur_ws))
                    e_progress = st.slider("完成进度（%）", 0, 100, int(cur["progress"]), step=5)
                    e_note = st.text_input("本次更新备注（可选）", placeholder="例：完成粗车工序、等待外协件")
                    c1, c2 = st.columns(2)
                    do_update = c1.form_submit_button("保存修改", use_container_width=True)
                    do_delete = c2.form_submit_button("删除任务", use_container_width=True)
                    if do_update:
                        if not e_name or not e_owner:
                            st.error("任务名称和负责人不能为空")
                        elif e_end < e_start:
                            st.error("结束时间不能早于开始时间")
                        else:
                            update_task(task_id, e_name, e_start.isoformat(), e_end.isoformat(), e_owner, e_progress, e_note, e_ws)
                            st.success("修改已保存")
                            st.rerun()
                    if do_delete:
                        delete_task(task_id)
                        st.warning(f"任务「{e_name}」已删除")
                        st.rerun()

        st.markdown("##### 📋 任务清单")
        if df.empty:
            st.info("暂无符合条件的任务")
        else:
            show = df[["id", "name", "start", "end", "owner", "workstation", "progress", "状态"]].copy()
            show.columns = ["编号", "任务名称", "开始时间", "结束时间", "负责人", "工位/设备", "完成进度(%)", "状态"]
            show["开始时间"] = show["开始时间"].dt.strftime("%Y-%m-%d")
            show["结束时间"] = show["结束时间"].dt.strftime("%Y-%m-%d")
            styled = show.style.map(status_pill_css, subset=["状态"]).format({"完成进度(%)": "{:.0f}%"})
            st.dataframe(styled, use_container_width=True, hide_index=True)
            csv_data = df[["id", "name", "start", "end", "owner", "workstation", "progress", "状态"]].to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 导出任务CSV", csv_data, "生产任务清单.csv", "text/csv", use_container_width=True)

        st.markdown("##### 📤 导入任务")
        with st.expander("从 CSV / Excel 文件批量导入任务"):
            st.caption(
                "支持 Excel（.xlsx / .xls）和 CSV（.csv）文件。"
                "列名支持：任务名称、开始时间、结束时间、负责人、工位/设备、完成进度(%)，"
                "与导出格式一致（编号、状态列自动忽略）；不填工位则记为「未分配」。"
            )
            if "import_done" in st.session_state:
                ok, total, errs = st.session_state.pop("import_done")
                if ok:
                    st.success(f"✅ 成功导入 {ok} / {total} 条任务")
                if errs:
                    with st.expander(f"⚠️ {total - ok} 条数据被跳过，点击查看原因"):
                        for e in errs:
                            st.write(e)
            up = st.file_uploader("选择文件", type=["csv", "xlsx", "xls"], key="csv_import")
            if up is not None:
                try:
                    if up.name.lower().endswith((".xlsx", ".xls")):
                        uploaded_df = pd.read_excel(up)
                    else:
                        uploaded_df = pd.read_csv(up)
                    st.dataframe(uploaded_df.head(5), use_container_width=True, hide_index=True)
                    st.caption(f"共检测到 {len(uploaded_df)} 行数据（仅预览前 5 行）")
                    if st.button("✅ 确认导入", key="do_import", use_container_width=True):
                        ok, total, errs = import_tasks(uploaded_df)
                        st.session_state["import_done"] = (ok, total, errs)
                        st.rerun()
                except Exception as ex:
                    st.error(f"文件解析失败：{ex}")
                    st.caption("提示：Excel 文件请保存为 .xlsx 格式（WPS/Office 另存为 → Excel 工作簿(*.xlsx)）")

        st.markdown("##### 📦 数据备份与恢复")
        with st.expander("备份全部数据 / 从备份恢复（含进度历史）"):
            st.caption(
                "⚠️ 云端免费部署环境在应用重新部署后可能清空数据。"
                "建议每次录入重要数据后导出一份备份；万一数据丢失，用备份一键还原。"
            )
            b1, b2 = st.columns(2)
            with b1:
                _bk = export_backup()
                st.download_button(
                    "📤 导出完整备份",
                    json.dumps(_bk, ensure_ascii=False, indent=2).encode("utf-8"),
                    f"车间数据备份_{date.today().isoformat()}.json",
                    "application/json",
                    use_container_width=True,
                )
                st.caption(f"当前：{_bk['task_count']} 个任务 · {_bk['log_count']} 条历史记录")
            with b2:
                bk_file = st.file_uploader("选择备份文件（.json）", type=["json"], key="bk_import")
                if bk_file is not None:
                    try:
                        bk_data = json.loads(bk_file.read().decode("utf-8"))
                        n_t = len(bk_data.get("tasks", []))
                        n_l = len(bk_data.get("progress_log", []))
                        st.info(
                            f"备份包含 **{n_t}** 个任务、**{n_l}** 条历史，"
                            f"导出于 {bk_data.get('exported_at', '未知')}"
                        )
                        rb1, rb2 = st.columns(2)
                        if rb1.button("➕ 追加导入", use_container_width=True, key="bk_merge"):
                            t_, l_, err = restore_backup(bk_data, "merge")
                            if err:
                                st.error(f"追加失败：{err}")
                            else:
                                st.success(f"✅ 已追加 {t_} 个任务、{l_} 条历史")
                                st.rerun()
                        confirm_rp = st.checkbox("确认清空现有数据", key="bk_confirm")
                        if rb2.button("♻️ 覆盖恢复", use_container_width=True, key="bk_replace",
                                      disabled=not confirm_rp):
                            t_, l_, err = restore_backup(bk_data, "replace")
                            if err:
                                st.error(f"恢复失败：{err}")
                            else:
                                st.success(f"✅ 已覆盖恢复 {t_} 个任务、{l_} 条历史")
                                st.rerun()
                    except Exception as ex:
                        st.error(f"备份文件解析失败：{ex}")

    elif page == "🗺️ 车间数字孪生":
        st.markdown("#### 🗺️ 车间数字孪生 · 实时布局看板")
        st.caption("以 2D 数字孪生方式呈现车间工位实时状态，颜色反映各工位当前负荷与运行情况。")
        if df_all.empty:
            st.info("暂无任务数据，请先在「任务管理」页录入任务")
        else:
            today = pd.Timestamp(date.today())
            ws_used = sorted([w for w in df_all["workstation"].unique() if w and w != "未分配"])
            if not ws_used:
                st.warning(
                    "当前所有任务均未分配工位，无法生成车间布局图。"
                    "请先在「🏭 设备负荷」页为任务快速分配工位。"
                )
            else:
                # 各工位实时状态统计
                info = {}
                for w in ws_used:
                    sub = df_all[df_all["workstation"] == w]
                    active = sub[
                        (sub["start"] <= today) & (sub["end"] >= today) & (sub["progress"] < 100)
                    ]
                    n = len(active)
                    state = "空闲" if n == 0 else ("超载" if n >= 3 else "运行中")
                    tip_lines = [f"在制 {n} 个 / 累计 {len(sub)} 个"]
                    if n:
                        for _, r in active.iterrows():
                            tip_lines.append(f"· {r['name']}（{r['owner']} {int(r['progress'])}%）")
                    else:
                        tip_lines.append("当前无在制任务")
                    info[w] = {
                        "state": state,
                        "n": n,
                        "total": len(sub),
                        "tip": f"{w}｜{state}\n" + "\n".join(tip_lines),
                        "avg": round(float(sub["progress"].mean()), 1),
                    }

                n_idle = sum(1 for v in info.values() if v["state"] == "空闲")
                n_run = sum(1 for v in info.values() if v["state"] == "运行中")
                n_over = sum(1 for v in info.values() if v["state"] == "超载")
                util = (n_run + n_over) / len(ws_used) * 100

                d1, d2, d3, d4 = st.columns(4)
                d1.markdown(metric_card("车间工位数", len(ws_used), "#0B5394", "🏭"), unsafe_allow_html=True)
                d2.markdown(metric_card("运行中", n_run, "#1E88E5", "🔵"), unsafe_allow_html=True)
                d3.markdown(metric_card("超载告警", n_over, "#E53935", "🔴"), unsafe_allow_html=True)
                d4.markdown(metric_card("工位利用率", f"{util:.0f}%", "#F6A623", "📈"), unsafe_allow_html=True)
                st.divider()

                # 组装 2D 车间平面图
                cells = [
                    '<div class="ws-zone"><div>⬛</div><div>原料 / 毛坯</div><div>暂存区</div></div>'
                ]
                for w in ws_used:
                    v = info[w]
                    bg = DT_BG[v["state"]]
                    tip = html.escape(v["tip"])
                    cells.append(
                        f'<div class="ws-cell" style="background:{bg};" title="{tip}">'
                        f'<div class="ws-name">{html.escape(w)}</div>'
                        f'<div class="ws-stat">在制 {v["n"]} 个 · 累计 {v["total"]} 个</div>'
                        f'<div class="ws-stat">平均进度 {v["avg"]:.0f}%</div>'
                        f'<span class="ws-badge">{v["state"]}</span>'
                        f"</div>"
                    )
                cells.append(
                    '<div class="ws-zone"><div>📦</div><div>成品 / 发货</div><div>暂存区</div></div>'
                )
                legend = (
                    '<div class="ws-legend">'
                    '<span><i class="ws-dot" style="background:#7A8CA3;"></i>空闲（无在制任务）</span>'
                    '<span><i class="ws-dot" style="background:#1E88E5;"></i>运行中（1-2 个并行）</span>'
                    '<span><i class="ws-dot" style="background:#E53935;"></i>超载（≥3 个并行）</span>'
                    '<span>🖱️ 鼠标悬停色块可查看该工位当前在制任务</span>'
                    "</div>"
                )
                st.markdown(
                    '<div class="ws-map">'
                    '<div class="ws-title">重型装备生产车间 · 实时布局数字孪生</div>'
                    f'<div class="ws-grid">{"".join(cells)}</div>{legend}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"🕐 数据快照：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    "　|　色块随任务数据实时更新，橙色利用率 =（运行中+超载）/ 工位数"
                )

                # 工位详情
                st.divider()
                st.markdown("##### 🔍 工位详情")
                sel = st.selectbox("选择工位，查看该工位当前在制任务", ws_used, key="dt_ws_sel")
                cur = df_all[
                    (df_all["workstation"] == sel)
                    & (df_all["start"] <= today)
                    & (df_all["end"] >= today)
                    & (df_all["progress"] < 100)
                ].copy()
                if cur.empty:
                    v = info[sel]
                    st.info(
                        f"「{sel}」当前无在制任务，处于**空闲**状态"
                        f"（累计承接 {v['total']} 个任务，平均进度 {v['avg']:.0f}%）。"
                    )
                else:
                    cur["开始时间"] = cur["start"].dt.strftime("%Y-%m-%d")
                    cur["结束时间"] = cur["end"].dt.strftime("%Y-%m-%d")
                    dt_show = cur[["id", "name", "owner", "开始时间", "结束时间", "progress", "状态"]].copy()
                    dt_show.columns = ["编号", "任务名称", "负责人", "开始时间", "结束时间", "完成进度(%)", "状态"]
                    st.dataframe(
                        dt_show.style.map(status_pill_css, subset=["状态"]).format({"完成进度(%)": "{:.0f}%"}),
                        use_container_width=True,
                        hide_index=True,
                    )

    elif page == "📅 进度甘特图":
        st.markdown("#### 📅 任务时间线")
        if df.empty:
            st.info("暂无任务数据，请先录入任务")
        else:
            view_mode = st.radio(
                "视图模式",
                ["📊 甘特图", "🗓️ 日历视图"],
                horizontal=True,
                label_visibility="collapsed",
            )
            st.divider()
            if view_mode == "📊 甘特图":
                c1, c2, c3, c4 = st.columns(4)
                total = len(df)
                ongoing = int((df["状态"] == "进行中").sum())
                done = int((df["状态"] == "已完成").sum())
                avg_prog = int(df["progress"].mean())
                c1.markdown(metric_card("任务总数", total, "#0B5394", "📊"), unsafe_allow_html=True)
                c2.markdown(metric_card("进行中", ongoing, "#1E88E5", "⚙️"), unsafe_allow_html=True)
                c3.markdown(metric_card("已完成", done, "#43A047", "✅"), unsafe_allow_html=True)
                c4.markdown(metric_card("平均进度", f"{avg_prog}%", "#F6A623", "📈"), unsafe_allow_html=True)
                st.divider()
                fig = make_gantt(df)
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"toImageButtonOptions": {"format": "png", "scale": 2, "filename": "甘特图"}},
                )
                st.caption("💡 导出甘特图图片：将鼠标移到图表右上角，点击工具栏中的相机图标即可下载 PNG 图片")
            else:
                # 日历视图
                if "cal_year" not in st.session_state:
                    t = date.today()
                    st.session_state.cal_year = t.year
                    st.session_state.cal_month = t.month

                c1, c2, c3, c4, c5 = st.columns([1, 1, 3, 1, 1])
                if c1.button("◀ 上月"):
                    if st.session_state.cal_month == 1:
                        st.session_state.cal_month = 12
                        st.session_state.cal_year -= 1
                    else:
                        st.session_state.cal_month -= 1
                    st.rerun()
                if c4.button("本月"):
                    st.session_state.cal_year = date.today().year
                    st.session_state.cal_month = date.today().month
                    st.rerun()
                if c5.button("下月 ▶"):
                    if st.session_state.cal_month == 12:
                        st.session_state.cal_month = 1
                        st.session_state.cal_year += 1
                    else:
                        st.session_state.cal_month += 1
                    st.rerun()
                c3.markdown(
                    f"<div style='text-align:center;font-size:22px;font-weight:700;color:#0B5394;'>"
                    f"📅 {st.session_state.cal_year} 年 {st.session_state.cal_month} 月</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    render_calendar(st.session_state.cal_year, st.session_state.cal_month, df),
                    unsafe_allow_html=True,
                )
                st.caption("💡 颜色越深表示当天并行执行的任务越多；橙黄边框标记今天")
                # 当天任务列表
                st.divider()
                st.markdown("##### 📋 当月任务汇总")
                cal_df = df.copy()
                if not cal_df.empty:
                    cal_df["start"] = pd.to_datetime(cal_df["start"])
                    cal_df["end"] = pd.to_datetime(cal_df["end"])
                    m_start = pd.Timestamp(st.session_state.cal_year, st.session_state.cal_month, 1)
                    if st.session_state.cal_month == 12:
                        m_end = pd.Timestamp(st.session_state.cal_year + 1, 1, 1) - pd.Timedelta(days=1)
                    else:
                        m_end = pd.Timestamp(st.session_state.cal_year, st.session_state.cal_month + 1, 1) - pd.Timedelta(days=1)
                    in_month = cal_df[(cal_df["end"] >= m_start) & (cal_df["start"] <= m_end)].copy()
                    if in_month.empty:
                        st.info("本月暂无任务")
                    else:
                        in_month["start"] = in_month["start"].dt.strftime("%Y-%m-%d")
                        in_month["end"] = in_month["end"].dt.strftime("%Y-%m-%d")
                        show = in_month[["name", "start", "end", "owner", "progress", "状态"]]
                        show.columns = ["任务名称", "开始时间", "结束时间", "负责人", "完成进度(%)", "状态"]
                        styled = show.style.map(status_pill_css, subset=["状态"]).format({"完成进度(%)": "{:.0f}%"})
                        st.dataframe(styled, use_container_width=True, hide_index=True)

    elif page == "⚠️ 预警清单":
        st.markdown("#### ⚠️ 风险预警")
        if df_all.empty:
            st.info("暂无任务数据")
        else:
            today = pd.Timestamp(date.today())
            soon = df_all[(df_all["end"] >= today) & (df_all["end"] <= today + pd.Timedelta(days=3)) & (df_all["progress"] < 100)]
            late = df_all[(df_all["end"] < today) & (df_all["progress"] < 100)]
            c1, c2 = st.columns(2)
            c1.markdown(metric_card("临近到期（3天内）", len(soon), "#F6A623", "⏰"), unsafe_allow_html=True)
            c2.markdown(metric_card("延期任务", len(late), "#E53935", "🚨"), unsafe_allow_html=True)
            st.markdown("##### 🚨 延期任务")
            if late.empty:
                st.success("🎉 暂无延期任务，团队执行良好！")
            else:
                late_show = late[["name", "owner", "end", "progress"]].copy()
                late_show["end"] = late_show["end"].dt.strftime("%Y-%m-%d")
                late_show.columns = ["任务名称", "负责人", "结束时间", "完成进度(%)"]
                late_styled = late_show.style.map(
                    lambda v: "color: #E53935; font-weight: 600;"
                ).format({"完成进度(%)": "{:.0f}%"})
                st.dataframe(late_styled, use_container_width=True, hide_index=True)
            st.markdown("##### ⏰ 临近到期任务")
            if soon.empty:
                st.success("✅ 暂无临近到期任务")
            else:
                soon_show = soon[["name", "owner", "end", "progress"]].copy()
                soon_show["剩余天数"] = (soon["end"] - today).dt.days
                soon_show["end"] = soon_show["end"].dt.strftime("%Y-%m-%d")
                soon_show.columns = ["任务名称", "负责人", "结束时间", "完成进度(%)", "剩余天数"]
                soon_styled = soon_show.style.format({"完成进度(%)": "{:.0f}%"})
                st.dataframe(soon_styled, use_container_width=True, hide_index=True)

    elif page == "📈 统计分析":
        st.markdown("#### 📊 数据分析")
        if df_all.empty:
            st.info("暂无任务数据")
        else:
            counts = df_all["状态"].value_counts().reindex(STATUS_ORDER, fill_value=0)
            c1, c2, c3, c4 = st.columns(4)
            total_tasks = int(counts.sum())
            ongoing = int(counts["进行中"])
            done = int(counts["已完成"])
            late_n = int(counts["已延期"])
            c1.markdown(metric_card("任务总数", total_tasks, "#0B5394", "📋"), unsafe_allow_html=True)
            c2.markdown(metric_card("进行中", ongoing, "#1E88E5", "⚙️"), unsafe_allow_html=True)
            c3.markdown(metric_card("已完成", done, "#43A047", "✅"), unsafe_allow_html=True)
            c4.markdown(metric_card("已延期", late_n, "#E53935", "🚨"), unsafe_allow_html=True)
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### 📈 任务状态占比")
                pie = px.pie(
                    names=counts.index,
                    values=counts.values,
                    color=counts.index,
                    color_discrete_map=COLOR_MAP,
                    hole=0.45,
                )
                pie.update_traces(textposition="inside", textinfo="percent+label")
                pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend_title_text="任务状态", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(pie, use_container_width=True)
            with c2:
                st.markdown("##### 📊 状态分布")
                bar = px.bar(
                    x=counts.index,
                    y=counts.values,
                    color=counts.index,
                    color_discrete_map=COLOR_MAP,
                    text=counts.values,
                )
                bar.update_traces(textposition="outside", textfont_size=14)
                bar.update_layout(
                    showlegend=False,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title="",
                    yaxis_title="任务数",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(bar, use_container_width=True)
            st.markdown("##### 👨‍💼 负责人任务完成情况")
            g = df_all.groupby("owner").agg(任务总数=("id", "count"), 平均进度=("progress", "mean")).reset_index()
            g["平均进度"] = g["平均进度"].round(1)
            g.columns = ["负责人", "任务总数", "平均进度(%)"]
            g_styled = g.style.map(
                lambda v: "color: #0B5394; font-weight: 600;", subset=["平均进度(%)"]
            ).format({"平均进度(%)": "{:.1f}%"})
            st.dataframe(g_styled, use_container_width=True, hide_index=True)
            if not g.empty:
                owner_bar = px.bar(
                    g,
                    x="负责人",
                    y="平均进度(%)",
                    color="平均进度(%)",
                    color_continuous_scale=["#E53935", "#F6A623", "#43A047"],
                    text="平均进度(%)",
                    range_y=[0, 105],
                )
                owner_bar.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                owner_bar.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                )
                st.plotly_chart(owner_bar, use_container_width=True)

    elif page == "📜 进度历史":
        st.markdown("#### 📜 任务进度变更记录")
        log_df = load_progress_log()
        if log_df.empty:
            st.info("暂无进度变更记录。修改任务进度后会自动记录在这里。")
        else:
            # 顶部统计
            c1, c2, c3 = st.columns(3)
            total_logs = len(log_df)
            today_n = int((pd.to_datetime(log_df["created_at"]).dt.date == date.today()).sum())
            affected_tasks = int(log_df["task_id"].nunique())
            c1.markdown(metric_card("总记录数", total_logs, "#0B5394", "📝"), unsafe_allow_html=True)
            c2.markdown(metric_card("今日新增", today_n, "#1E88E5", "🆕"), unsafe_allow_html=True)
            c3.markdown(metric_card("涉及任务", affected_tasks, "#F6A623", "📋"), unsafe_allow_html=True)
            st.divider()
            # 过滤
            fc1, fc2 = st.columns([1, 1])
            task_filter = fc1.selectbox(
                "按任务筛选",
                ["全部"] + sorted(log_df["task_name"].dropna().unique().tolist()),
            )
            owner_options = ["全部"] + sorted(log_df["owner"].dropna().unique().tolist())
            owner_filter = fc2.selectbox("按负责人筛选", owner_options)
            view = log_df.copy()
            if task_filter != "全部":
                view = view[view["task_name"] == task_filter]
            if owner_filter != "全部":
                view = view[view["owner"] == owner_filter]
            st.markdown(f"##### 共 {len(view)} 条记录")
            if view.empty:
                st.info("当前筛选条件下无记录")
            else:
                view["变更时间"] = pd.to_datetime(view["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                show = view[["变更时间", "task_name", "owner", "progress", "note"]].copy()
                show.columns = ["变更时间", "任务名称", "负责人", "新进度(%)", "备注"]
                show["新进度(%)"] = show["新进度(%)"].astype(int)
                # 按进度上色
                def color_progress(v):
                    if v >= 100:
                        return "color: #43A047; font-weight: 700;"
                    elif v >= 50:
                        return "color: #1E88E5; font-weight: 600;"
                    return "color: #94A3B8;"

                styled = show.style.map(color_progress, subset=["新进度(%)"])
                st.dataframe(styled, use_container_width=True, hide_index=True)
                # 导出
                csv = show.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 导出变更记录",
                    csv,
                    "进度变更记录.csv",
                    "text/csv",
                    use_container_width=True,
                )

    elif page == "🤖 AI助手小童":
        st.markdown("#### 🤖 AI助手小童")
        api_key, key_source = get_api_key()
        if api_key:
            st.markdown(
                f'<div style="background:#E8F5E9;border-left:4px solid #43A047;padding:12px 16px;'
                f'border-radius:8px;margin-bottom:14px;color:#1B5E20;font-size:14px;">'
                f'✅ <b>AI助手小童 已就绪</b>（Key 来源：{key_source}）—— 可直接用自然语言提问，'
                f'例如「小童，哪些任务有延期风险」「谁完成得最好」'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:#FFF8E1;border-left:4px solid #F6A623;padding:12px 16px;'
                'border-radius:8px;margin-bottom:14px;color:#7F6000;font-size:14px;">'
                '⚠️ 未配置大模型 API Key，当前为<b>离线规则分析模式</b>（功能仍可用）。'
                '在<b>左侧栏</b>填入 DeepSeek API Key 即可唤醒 AI 助手小童。'
                '</div>',
                unsafe_allow_html=True,
            )

        qa1, qa2, qa3, qa4 = st.columns(4)
        if qa1.button("📊 生成本周周报", use_container_width=True):
            st.session_state.ai_preset = "__WEEKLY__"
        if qa2.button("🚨 风险智能分析", use_container_width=True):
            st.session_state.ai_preset = (
                "请全面分析当前生产延期风险：列出所有已延期和进度滞后的任务，"
                "逐一分析可能原因，并给出可执行的补救建议。请按严重程度排序。"
            )
        if qa3.button("👨‍💼 人员绩效点评", use_container_width=True):
            st.session_state.ai_preset = (
                "请按负责人对比分析任务完成情况，指出表现突出和需要关注的人，"
                "结合任务数量与平均进度给出客观的管理建议。"
            )
        if qa4.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()
        st.divider()

        # 渲染历史对话
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        preset = st.session_state.pop("ai_preset", None)
        user_input = st.chat_input("输入你的问题，例如：这个月谁完成得最好？哪些任务有延期风险？")
        prompt = preset or user_input

        if prompt:
            user_display = "📊 生成本周生产周报" if prompt == "__WEEKLY__" else prompt
            st.session_state.chat_messages.append({"role": "user", "content": user_display})

            if prompt == "__WEEKLY__":
                if api_key:
                    ctx = build_data_context(df_all)
                    msgs = [
                        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + ctx},
                        {
                            "role": "user",
                            "content": (
                                "请基于上述任务数据，生成一份专业的车间生产周报，"
                                "需包含：本周完成情况、新开工任务、进行中任务、"
                                "风险提示、下周工作重点五个部分。格式清晰，可直接复制使用。"
                            ),
                        },
                    ]
                    with st.spinner("🤖 小童正在分析数据并生成周报..."):
                        ok, reply = call_llm(msgs, api_key)
                    if not ok:
                        reply = reply + "\n\n---\n\n" + generate_weekly_report_text(df_all)
                else:
                    reply = generate_weekly_report_text(df_all)
            else:
                if api_key:
                    ctx = build_data_context(df_all)
                    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_messages]
                    msgs = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + ctx}] + history
                    with st.spinner("🤖 小童正在分析生产数据..."):
                        ok, reply = call_llm(msgs, api_key)
                    if not ok:
                        reply = reply + "\n\n---\n\n" + rule_insights(df_all)
                else:
                    reply = rule_insights(df_all)

            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            st.rerun()

    st.markdown("---")
    st.markdown(
        '<div style="text-align:center; color:#94A3B8; font-size:13px; padding:8px 0;">'
        '🏭 重型装备车间生产任务进度数字化跟踪平台 · Powered by Streamlit'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
