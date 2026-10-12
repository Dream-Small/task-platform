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
    st.title("重型装备车间生产任务进度数字化跟踪平台")
    init_db()
    df_all = load_tasks()

    with st.sidebar:
        st.header("筛选条件")
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
            st.subheader("新增任务")
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
            st.subheader("修改 / 删除任务")
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

        st.subheader("任务清单")
        if df.empty:
            st.info("暂无符合条件的任务")
        else:
            show = df[["id", "name", "start", "end", "owner", "progress", "状态"]].copy()
            show.columns = ["编号", "任务名称", "开始时间", "结束时间", "负责人", "完成进度(%)", "状态"]
            show["开始时间"] = show["开始时间"].dt.strftime("%Y-%m-%d")
            show["结束时间"] = show["结束时间"].dt.strftime("%Y-%m-%d")
            st.dataframe(show, use_container_width=True, hide_index=True)
            csv_data = df[["id", "name", "start", "end", "owner", "progress", "状态"]].to_csv(index=False).encode("utf-8-sig")
            st.download_button("导出任务CSV", csv_data, "生产任务清单.csv", "text/csv", use_container_width=True)

    with tab2:
        if df.empty:
            st.info("暂无任务数据，请先录入任务")
        else:
            fig = make_gantt(df)
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"toImageButtonOptions": {"format": "png", "scale": 2, "filename": "甘特图"}},
            )
            st.caption("导出甘特图图片：将鼠标移到图表右上角，点击工具栏中的相机图标即可下载PNG图片")

    with tab3:
        if df_all.empty:
            st.info("暂无任务数据")
        else:
            today = pd.Timestamp(date.today())
            soon = df_all[(df_all["end"] >= today) & (df_all["end"] <= today + pd.Timedelta(days=3)) & (df_all["progress"] < 100)]
            late = df_all[(df_all["end"] < today) & (df_all["progress"] < 100)]
            c1, c2 = st.columns(2)
            c1.metric("临近到期任务（3天内）", len(soon))
            c2.metric("延期任务", len(late))
            st.subheader("延期任务（红色高亮）")
            if late.empty:
                st.success("无延期任务")
            else:
                late_show = late[["name", "owner", "end", "progress"]].copy()
                late_show["end"] = late_show["end"].dt.strftime("%Y-%m-%d")
                late_show.columns = ["任务名称", "负责人", "结束时间", "完成进度(%)"]
                late_show = late_show.style.map(lambda v: "color: #E53935; font-weight: bold;")
                st.dataframe(late_show, use_container_width=True, hide_index=True)
            st.subheader("临近到期任务（黄色提醒）")
            if soon.empty:
                st.success("无临近到期任务")
            else:
                soon_show = soon[["name", "owner", "end", "progress"]].copy()
                soon_show["剩余天数"] = (soon["end"] - today).dt.days
                soon_show["end"] = soon_show["end"].dt.strftime("%Y-%m-%d")
                soon_show.columns = ["任务名称", "负责人", "结束时间", "完成进度(%)", "剩余天数"]
                st.dataframe(soon_show, use_container_width=True, hide_index=True)

    with tab4:
        if df_all.empty:
            st.info("暂无任务数据")
        else:
            counts = df_all["状态"].value_counts().reindex(STATUS_ORDER, fill_value=0)
            c1, c2 = st.columns(2)
            for s in STATUS_ORDER:
                c2.metric(s, int(counts[s]))
            c1.subheader("任务状态占比")
            pie = px.pie(
                names=counts.index,
                values=counts.values,
                color=counts.index,
                color_discrete_map=COLOR_MAP,
                hole=0.4,
            )
            pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend_title_text="任务状态")
            c1.plotly_chart(pie, use_container_width=True)
            st.subheader("负责人任务完成情况")
            g = df_all.groupby("owner").agg(任务总数=("id", "count"), 平均进度=("progress", "mean")).reset_index()
            g["平均进度"] = g["平均进度"].round(1)
            g.columns = ["负责人", "任务总数", "平均进度(%)"]
            st.dataframe(g, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
