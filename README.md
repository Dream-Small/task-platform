# 重型装备车间生产任务进度数字化跟踪平台

基于 Streamlit + SQLite + Plotly 开发的生产任务进度跟踪系统。

## 功能

- **任务管理**：任务的新增、修改、删除
- **进度甘特图**：可视化展示任务时间线与进度状态
- **预警清单**：延期任务（红色）与临近到期任务（黄色）自动提醒
- **统计分析**：任务状态占比、负责人任务完成情况

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 技术栈

- [Streamlit](https://streamlit.io/) - Web 界面
- SQLite - 数据存储
- Pandas / Plotly - 数据处理与可视化
