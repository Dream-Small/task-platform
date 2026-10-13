import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

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
    conn.commit()
    conn.close()


def add_task(name, start, end, owner, progress):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO tasks (name, start, end, owner, progress) VALUES (?, ?, ?, ?, ?)",
        (name, start, end, owner, progress),
    )
    conn.commit()
    conn.close()


def update_task(task_id, name, start, end, owner, progress):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE tasks SET name=?, start=?, end=?, owner=?, progress=? WHERE id=?",
        (name, start, end, owner, progress, task_id),
    )
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


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
        add_task(name, start.isoformat(), end.isoformat(), owner, progress)
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

    if df_all.empty:
        df = df_all

    tab1, tab2, tab3, tab4 = st.tabs(["任务管理", "进度甘特图", "预警清单", "统计分析"])

    with tab1:
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
                    c1, c2 = st.columns(2)
                    do_update = c1.form_submit_button("保存修改", use_container_width=True)
                    do_delete = c2.form_submit_button("删除任务", use_container_width=True)
                    if do_update:
                        if not e_name or not e_owner:
                            st.error("任务名称和负责人不能为空")
                        elif e_end < e_start:
                            st.error("结束时间不能早于开始时间")
                        else:
                            update_task(task_id, e_name, e_start.isoformat(), e_end.isoformat(), e_owner, e_progress)
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

    with tab2:
        st.markdown("#### 📅 任务时间线")
        if df.empty:
            st.info("暂无任务数据，请先录入任务")
        else:
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

    with tab3:
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

    with tab4:
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

    st.markdown("---")
    st.markdown(
        '<div style="text-align:center; color:#94A3B8; font-size:13px; padding:8px 0;">'
        '🏭 重型装备车间生产任务进度数字化跟踪平台 · Powered by Streamlit'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
