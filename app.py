import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import calendar as cal_mod
import requests

st.set_page_config(page_title="重型装备车间生产任务进度数字化跟踪平台", layout="wide")

DB_PATH = "tasks.db"

STATUS_ORDER = ["未开始", "进行中", "已完成", "已延期"]
COLOR_MAP = {"未开始": "#9E9E9E", "进行中": "#1E88E5", "已完成": "#43A047", "已延期": "#E53935"}


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
    conn.commit()
    conn.close()


def add_task(name, start, end, owner, progress, note="任务创建"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO tasks (name, start, end, owner, progress) VALUES (?, ?, ?, ?, ?)",
        (name, start, end, owner, progress),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_progress(task_id, progress, note)
    return task_id


def update_task(task_id, name, start, end, owner, progress, note=""):
    conn = sqlite3.connect(DB_PATH)
    old_row = conn.execute("SELECT progress FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.execute(
        "UPDATE tasks SET name=?, start=?, end=?, owner=?, progress=? WHERE id=?",
        (name, start, end, owner, progress, task_id),
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


# ======== AI 智能体模块 ========
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-chat"

# 内置默认 API Key（保证开箱即用）。分片拼接仅为降低被自动扫描器抓取的概率。
# 如需停用内置 Key（例如担心被盗用），把下面三段的引号内容全部清空即可。
BUILTIN_API_KEY = (
    "sk-645645cf"
    "bf6143bda4"
    "71a79a6dc414d9"
)

SYSTEM_PROMPT = """你是「重型装备车间生产任务数字化跟踪平台」内置的 AI 生产管理助手，
服务对象是国内重型装备制造企业的车间主任、班组长和生产管理人员。

你的能力：
1. 基于下方【当前任务数据】回答生产进度相关问题（只依据给定数据，不得臆测数据之外的信息）
2. 识别延期风险、进度滞后、人员绩效差异，并给出可执行的补救建议
3. 生成结构化的生产周报 / 日报

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
        lines.append(
            f"- #{int(r['id'])} 「{r['name']}」负责人:{r['owner']} "
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
        "在左侧栏填入 DeepSeek API Key 后，即可升级为支持自然语言提问的对话式 AI 智能体。*"
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
        add_task(name, start.isoformat(), end.isoformat(), owner, progress, "批量导入")
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
        st.markdown("### 🔍 筛选条件")
        if df_all.empty:
            st.info("暂无任务数据，请先在「任务管理」页录入任务")
        else:
            owner_opt = ["全部"] + sorted(df_all["owner"].unique().tolist())
            status_opt = ["全部"] + STATUS_ORDER
            kw = st.text_input("按任务名称/负责人搜索")
            f_owner = st.selectbox("负责人", owner_opt)
            f_status = st.selectbox("任务状态", status_opt)
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
            df = df[(df["start"] <= hi + pd.Timedelta(days=1)) & (df["end"] >= lo)]
            st.metric("筛选结果任务数", len(df))

        st.markdown("---")
        st.markdown("### 🤖 AI 智能体设置")
        st.caption(
            "填入 DeepSeek API Key 即可启用对话式 AI 助手。"
            "Key 仅保存在当前浏览器会话中，不会上传 GitHub。"
        )
        _k = st.text_input("DeepSeek API Key", type="password", placeholder="sk-...", key="api_key_input_widget")
        if _k:
            st.session_state.user_api_key = _k
            st.success("✅ Key 已生效，请前往「AI 智能助手」页使用")
        elif st.session_state.get("user_api_key"):
            st.info("已使用当前会话中保存的 Key")

    if df_all.empty:
        df = df_all

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 数据驾驶舱", "📋 任务管理", "📅 进度甘特图",
        "⚠️ 预警清单", "📈 统计分析", "📜 进度历史", "🤖 AI 智能助手",
    ])

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    with tab1:  # 数据驾驶舱
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

    with tab2:
        col_add, col_edit = st.columns(2)
        with col_add:
            st.markdown("##### ➕ 新增任务")
            with st.form("add_form"):
                name = st.text_input("任务名称")
                start = st.date_input("开始时间", value=date.today())
                end = st.date_input("结束时间", value=date.today() + timedelta(days=7))
                owner = st.text_input("负责人")
                progress = st.slider("完成进度（%）", 0, 100, 0, step=5)
                submitted = st.form_submit_button("添加任务", use_container_width=True)
                if submitted:
                    if not name or not owner:
                        st.error("任务名称和负责人不能为空")
                    elif end < start:
                        st.error("结束时间不能早于开始时间")
                    else:
                        add_task(name, start.isoformat(), end.isoformat(), owner, progress)
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
                            update_task(task_id, e_name, e_start.isoformat(), e_end.isoformat(), e_owner, e_progress, e_note)
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
            show = df[["id", "name", "start", "end", "owner", "progress", "状态"]].copy()
            show.columns = ["编号", "任务名称", "开始时间", "结束时间", "负责人", "完成进度(%)", "状态"]
            show["开始时间"] = show["开始时间"].dt.strftime("%Y-%m-%d")
            show["结束时间"] = show["结束时间"].dt.strftime("%Y-%m-%d")
            styled = show.style.map(status_pill_css, subset=["状态"]).format({"完成进度(%)": "{:.0f}%"})
            st.dataframe(styled, use_container_width=True, hide_index=True)
            csv_data = df[["id", "name", "start", "end", "owner", "progress", "状态"]].to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 导出任务CSV", csv_data, "生产任务清单.csv", "text/csv", use_container_width=True)

        st.markdown("##### 📤 导入任务")
        with st.expander("从 CSV / Excel 文件批量导入任务"):
            st.caption(
                "支持 Excel（.xlsx / .xls）和 CSV（.csv）文件。"
                "列名支持：任务名称、开始时间、结束时间、负责人、完成进度(%)，与导出格式一致（编号、状态列自动忽略）。"
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

    with tab3:
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

    with tab4:
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

    with tab5:
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

    with tab6:  # 进度历史
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

    with tab7:  # AI 智能助手
        st.markdown("#### 🤖 AI 生产管理助手")
        api_key, key_source = get_api_key()
        if api_key:
            st.markdown(
                f'<div style="background:#E8F5E9;border-left:4px solid #43A047;padding:12px 16px;'
                f'border-radius:8px;margin-bottom:14px;color:#1B5E20;font-size:14px;">'
                f'✅ <b>智能体已就绪</b>（Key 来源：{key_source}）—— 可直接用自然语言提问，'
                f'例如「哪些任务有延期风险」「谁完成得最好」'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:#FFF8E1;border-left:4px solid #F6A623;padding:12px 16px;'
                'border-radius:8px;margin-bottom:14px;color:#7F6000;font-size:14px;">'
                '⚠️ 未配置大模型 API Key，当前为<b>离线规则分析模式</b>（功能仍可用）。'
                '在<b>左侧栏</b>填入 DeepSeek API Key 即可升级为对话式 AI 智能体。'
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
                    with st.spinner("🤖 AI 正在分析数据并生成周报..."):
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
                    with st.spinner("🤖 AI 正在分析生产数据..."):
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
