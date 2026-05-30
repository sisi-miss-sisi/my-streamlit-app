import streamlit as st  # 做网页界面
import pandas as pd  # 用来存表格数据
import pytz
import datetime  # 导入日期时间模块，记录日期和时间
import plotly.express as px  # 用来画折线图
from io import BytesIO  # 做PDF时临时存放数据用
from supabase import create_client, Client  # 导入云端数据库Supabase客户端，实现数据云同步
from openai import OpenAI # AI接入
# 生成PDF报告
import tempfile, os, shutil
import plotly.io as pio
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


import plotly.io as pio

# 为 Kaleido 设置显式的无头浏览器参数，解决在Streamlit Cloud上卡住/报错的关键
# 参考自 https://discuss.streamlit.io/t/unable-to-run-plotly-kaleido-on-streamlit-cloud-to-generate-image-exports-from-graphs/23425/11
pio.kaleido.scope.chromium_args = (
    "--headless",           # 无界面模式
    "--no-sandbox",         # 禁用沙盒，许多云端环境必需
    "--single-process",     # 单进程模式，适配容器环境
    "--disable-gpu"         # 禁用GPU，适用于无图形界面的服务器
)


# 修改时间获取
china_tz = pytz.timezone('Asia/Shanghai')
now_china = datetime.datetime.now(china_tz)

# 链接云端数据库
# 尝试从Streamlit密钥中读取数据库地址和密钥
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("⚠️ 未检测到数据库配置，请呼唤张茜博：在 Secrets 中设置 SUPABASE_URL 和 SUPABASE_KEY")
    st.stop()

# 页面美化
st.set_page_config(page_title='老爸健康管家', layout='wide', initial_sidebar_state='collapsed')
st.markdown("""
    <style>
    /* 调整 “按钮组件” 的样式 */
    /* height:框高度；font-size:框内字体大小；width:框宽度；broder-radius:框圆角程度 */
    .stButton>button {
        height: 3.5em;
        font-size: 18px !important;
        width: 100%;
        border-radius: 10px;
        }
    /* 调整 “数字输入框” 和 “下拉选择框” 的样式 */
    /* font-size:框内字体大小 */
    .stNumberInput input, .stSelectbox select {
        font-size: 1.2rem !important;
        }


        /*手机端优化*/
    @media only screen and (max-width: 600px) {
        .stButton>button {
            height: 2.8em;
            font-size: 14px !important;
        }
        .stNumberInput input, .stSelectbox select, .stDateInput, .stTimeInput {
            font-size: 14px !important;
        }
        h1 {
            font-size: 1.5rem !important;
        }
        h2, h3 {
            font-size: 1.2rem !important;
        }
        .stTabs [data-baseweb='tab-list'] button {
            font-size: 12px !important;
            padding: 8px 4px;
        }

    }
    </style>
    """, unsafe_allow_html=True)

# 页面布局
# 侧边筛选栏

st.sidebar.header("时间筛选")
range_option = st.sidebar.radio(
    "选择时间段",
    ["最近7天", "最近30天", "最近60天", "自定义"],
    index=1
)
today = now_china.date()
# 自定义筛选
if range_option == "自定义":
    start_date = st.sidebar.date_input("起始日期", value=today - datetime.timedelta(days=60))
    end_date = st.sidebar.date_input("结束日期", value=today)
    if start_date > end_date:
        st.sidebar.error("❌ 起始日期不能晚于结束日期")
        st.stop()

# 最近几天筛选
else:
    days = int(range_option.replace("最近", "").replace("天", ""))
    start_date = today - datetime.timedelta(days=days)
    end_date = today
    st.sidebar.write(f"当前显示：{start_date} 至 {end_date} 的记录")

st.title("👨‍ 老爸健康数据管理系统")  # st.title()大标题
st.write("数据已加密存储于云端，手机与电脑实时同步")  # st.caption 小字提示
st.info("💡 点击左上角“ >> ”筛选日期范围")

# 导航功能区：新建三个标签页
tab1, tab2, tab3, tab4 = st.tabs(["📝 填写记录", "🗂️ 数据管理", "📉 趋势分析", "🖨️ 报告打印"])

# 第一部分：数据录入
with tab1:  # 把内容放在第一个标签页里面
    option = st.radio("请选择测量项目：", ("血糖记录", "血压记录"), horizontal=True)
    # st.radio("提示文字", (选项1，选项2), horizontal=True)
    # horizontal=True:选项横着放；horizontal=False:选项竖着放

    with st.form("input_form", clear_on_submit=False):  # st.form("表单名", clear_on_submit=True):创建表单，提交后自动清空内容
        if option == "血糖记录":  # 选择了记录血糖之后出来的表单
            d = st.date_input("日期", now_china.date())
            t = st.time_input("具体时间", now_china.time())
            options = [
                "早餐前（空腹）",
                "早餐后2小时",
                "午餐前",
                "午餐后2小时",
                "晚餐前",
                "晚餐后2小时",
            ]
            p = st.radio(
                "测量时段",
                options,
                index=0,  # 默认选中第一项
                horizontal=False,  # 垂直排列，每行一个选项
                key="period_radio"
            )

            v = st.number_input("血糖数值(mmol/L)", value=10.0, step=0.1)


            n = st.text_input("备注", "状态良好")

            if st.form_submit_button("🚀 点击保存"):  # 点击保存按钮后
                if v>30 or v<=0 :
                    st.error("血糖数值疑似录入有误，请修改后重新保存~")
                else:
                    try:
                        data = {"日期": str(d), "具体时间": str(t)[:5], "测量时段": p, "血糖数值(mmol/L)": v, "备注": n}
                        supabase.table("glucose").insert(data).execute()  # 把打包好的数据，存入云端数据库的 “glucose（血糖）表” 里
                        st.toast("✅ 血糖数据已存入云库！")
                        # 保存成功后重新运行页面，清空表单
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存失败，请呼叫张茜博：{e}")

        else:
            d = st.date_input("日期", now_china.date())
            t = st.time_input("具体时间", now_china.time())

            sys = st.number_input("高压（收缩压）mmHg", value=160)
            dia = st.number_input("低压（舒张压）mmHg", value=95)
            a = st.selectbox("测量手臂", ['左臂', '右臂'])
            hr = st.number_input("心率", value=80)


            note = st.text_input("备注", "状态良好")

            if st.form_submit_button("🚀 点击保存"):
                if sys>300 or sys<=0 :
                    st.error("高压数值疑似录入有误，请修改后重新保存~")
                elif dia>300 or dia<=0:
                    st.error("低压数值疑似录入有误，请修改后重新保存~")
                elif hr>300 or hr<=0:
                    st.error("心率数值疑似录入有误，请修改后重新保存~")
                else:
                    try:
                        data = {"日期": str(d), "具体时间": str(t)[0:5], "高压（收缩压）mmHg": sys, "低压（舒张压）mmHg": dia, "测量手臂": a,
                                "心率": hr, "备注": note}
                        supabase.table("bp").insert(data).execute()
                        st.toast("✅ 血压数据已存入云库！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存失败，请呼叫张茜博：{e}")

# 第二部分：数据管理与导出
with tab2:
    st.write(f"当前显示从{start_date} 至 {end_date} 的数据")

    # 获取血糖数据
    res_g = supabase.table("glucose").select('*').gte("日期", str(start_date)).lte("日期", str(end_date)).order("日期",
                                                                                                            desc=True).order(
        "具体时间", desc=True).execute()  # desc=True:降序/desc=False:升序
    df_g = pd.DataFrame(res_g.data)
    if not df_g.empty:
        df_g['具体时间'] = df_g['具体时间'].astype(str).str[:5]

    # 获取血压数值
    res_b = supabase.table("bp").select('*').gte("日期", str(start_date)).lte("日期", str(end_date)).order("日期",
                                                                                                       desc=True).order(
        "具体时间", desc=True).execute()  # desc=True:降序/desc=False:升序
    df_b = pd.DataFrame(res_b.data)
    if not df_b.empty:
        df_b['具体时间'] = df_b['具体时间'].astype(str).str[:5]

    # 页面里新建两个页面
    tab21, tab22 = st.tabs(["🩸血糖记录", "💓血压记录"])

    # 血糖记录
    with tab21:

        if not df_g.empty:
            # Excel导出功能
            output_g = BytesIO()
            with pd.ExcelWriter(output_g, engine='xlsxwriter') as writer:
                df_g.to_excel(writer, index=False, sheet_name='血糖记录')
            st.download_button("📥 下载血糖 Excel", output_g.getvalue(), "血糖记录.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.dataframe(df_g, use_container_width=True, hide_index=True, height=400)

            # 删除功能
            del_g = st.selectbox("选择要删除的记录序号", ["请选择"] + df_g['序号'].tolist(), key="del_g")

            if st.button("🗑️ 删除选中的血糖记录") and del_g != "请选择":
                supabase.table("glucose").delete().eq("序号", del_g).execute()
                st.rerun()



        else:
            st.write("暂无血糖记录")

    # 血压记录
    with tab22:

        if not df_b.empty:
            # Excel导出功能
            output_b = BytesIO()
            with pd.ExcelWriter(output_b, engine='xlsxwriter') as writer:
                df_b.to_excel(writer, index=False, sheet_name='血压记录')
            st.download_button("📥 下载血压 Excel", output_b.getvalue(), "血压记录.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.dataframe(df_b, use_container_width=True, hide_index=True)

            # 删除功能
            del_b = st.selectbox("选择要删除的记录序号", ["请选择"] + df_b['序号'].tolist(), key='del_b')
            if st.button("🗑️ 删除选中的血压记录") and del_b != "请选择":
                supabase.table("bp").delete().eq("序号", del_b).execute()
                st.rerun()

        else:
            st.write("暂无血压记录")

# 第三部分：数据可视化（平均值计算）与打印
with tab3:
    st.write(f"当前显示从{start_date} 至 {end_date} 的数据")

    tab31, tab32 = st.tabs(['血糖可视化', '血压可视化'])

    with tab31:
        if not df_g.empty:

            # 降采样或排序处理
            df_g_plot = df_g.sort_values("日期")
            df_g_plot["日期时间"] = df_g_plot["日期"] + " " + df_g_plot["具体时间"]
            df_g_plot["日期时间"] = pd.to_datetime(df_g_plot["日期时间"])
            df_g_plot = df_g_plot.sort_values("日期时间")
            # 绘图
            fig_g_plot = px.line(df_g_plot, x="日期时间", y="血糖数值(mmol/L)", hover_data=["测量时段"], markers=True,
                                 title="血糖长期趋势图")
            # 优化横坐标
            fig_g_plot.update_layout(xaxis=dict(tickangle=-45, tickformat='%y-%m-%d %H:%M'))
            # 显示图表
            st.plotly_chart(fig_g_plot, use_container_width=True)
            st.info("💡 提示：将鼠标悬停在图表右上角，点击‘相机’图标可下载高清打印图片")

            # 按时段分组平均值
            st.write("各时段平均血糖")
            order = ["早餐前（空腹）", "早餐后2小时", "午餐前", "午餐后2小时", "晚餐前", "晚餐后2小时"]
            df_g['测量时段'] = pd.Categorical(df_g['测量时段'], categories=order, ordered=True)
            period_avg = df_g.groupby('测量时段')['血糖数值(mmol/L)'].mean().reset_index()
            st.dataframe(period_avg, use_container_width=True)

            # 计算平均值
            avg_glucose = df_g['血糖数值(mmol/L)'].mean()
            # 使用 st.metric 突出显示
            st.metric("📊 平均血糖", f"{avg_glucose:.2f} mmol")

        else:
            st.write("暂时还没有录入血糖数据哦~")

    with tab32:
        if not df_b.empty:

            # 降采样或排序处理
            df_b_plot = df_b.sort_values("日期")
            df_b_plot['日期时间'] = df_b_plot["日期"] + " " + df_b_plot['具体时间']
            df_b_plot['日期时间'] = pd.to_datetime(df_b_plot['日期时间'])
            df_b_plot = df_b_plot.sort_values('日期时间')

            # 绘图
            fig_b_plot = px.line(df_b_plot, x="日期时间", y=['高压（收缩压）mmHg', '低压（舒张压）mmHg'], markers=True, title='血压长期趋势图')
            fig_b_plot.update_layout(xaxis=dict(tickangle=-45, tickformat='%Y-%m-%d %H:%M'))
            st.plotly_chart(fig_b_plot, use_container_width=True)
            st.info("💡 提示：将鼠标悬停在图表右上角，点击‘相机’图标可下载高清打印图片")

            # 计算平均值
            # 高压
            avg_bp1 = df_b["高压（收缩压）mmHg"].mean()
            # 使用st.metric 突出显示
            st.metric("📊 高压平均值", f"{avg_bp1:.2f} mmHg")
            # 低压
            avg_bp2 = df_b["低压（舒张压）mmHg"].mean()
            st.metric("📊 低压平均值", f"{avg_bp2:.2f} mmHg")

        else:
            st.write("暂时还没有录入血压数据哦~")


# 第四部分：报告打印
with tab4:
    st.write(f"报告显示从{start_date} 至 {end_date} 的数据")

    # 直接使用本地 OPPO 字体（无需网络，手机 PDF 正常显示）
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import os

    font_file = "OPPOSans-M.ttf"
    if not os.path.exists(font_file):
        st.error("未找到字体文件 OPPOSans-M.ttf，请确保它在程序目录下。")
        st.stop()
    pdfmetrics.registerFont(TTFont('ChineseFont', font_file))
    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName='ChineseFont')
    heading_style = ParagraphStyle('Heading2', parent=styles['Heading2'], fontName='ChineseFont')
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontName='ChineseFont', fontSize=18, alignment=1)

    tab41, tab42 = st.tabs(['血糖报告', '血压报告'])


    # 血糖报告打印
    with tab41:
        if df_g.empty:
            st.warning("当前时间段无血糖数据，无法生成报告")
        else:
            if st.button("📄 生成血糖报告 PDF", key="glucose_pdf_btn", use_container_width=True):
                with st.spinner("正在生成血糖报告，请稍后......"):

                    # 1.血糖趋势图准备
                    df_g_plot = df_g.sort_values("日期")
                    df_g_plot["日期时间"] = df_g_plot["日期"] + " " + df_g_plot["具体时间"]
                    df_g_plot["日期时间"] = pd.to_datetime(df_g_plot["日期时间"])
                    df_g_plot = df_g_plot.sort_values("日期时间")
                    fig_g = px.line(df_g_plot, x="日期时间", y="血糖数值(mmol/L)", hover_data=["测量时段"], markers=True,
                                    title="血糖长期趋势图")
                    fig_g.update_layout(
                        xaxis_title="日期时间",
                        yaxis_title="血糖 (mmol/L)",
                        font=dict(family="Noto Sans CJK SC"),  # 关键：图表也使用同一中文字体
                        plot_bgcolor='white',
                        xaxis=dict(tickangle=-45),
                        width=1000,
                        height=500
                    )
                    # 2.平均值准备
                    # 各时段平均值
                    order = ["早餐前（空腹）", "早餐后2小时", "午餐前", "午餐后2小时", "晚餐前", "晚餐后2小时"]
                    df_g['测量时段'] = pd.Categorical(df_g['测量时段'], categories=order, ordered=True)
                    period_avg = df_g.groupby('测量时段')['血糖数值(mmol/L)'].mean().reset_index()
                    # 总体平均值
                    overall_avg = df_g['血糖数值(mmol/L)'].mean()

                    # 3.AI总结准备
                    ai_text = ""
                    if st.secrets.get("DEEPSEEK_API_KEY"):
                        try:
                            client = OpenAI(
                                api_key=st.secrets["DEEPSEEK_API_KEY"],
                                base_url=st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
                            )
                            df_g_sorted = df_g.sort_values(['日期', '具体时间'])
                            records = []
                            for _, row in df_g_sorted.iterrows():
                                # 备注如果为空或是默认的"状态良好"，可以省略
                                note_part = f"，备注：{row['备注']}" if row['备注'] and row['备注'] != "状态良好" else ""
                                records.append(
                                    f"{row['日期']} {row['具体时间']} [{row['测量时段']}] : {row['血糖数值(mmol/L)']} mmol/L{note_part}"
                                )
                            data_str = "\n".join(records)

                            overall_avg = df_g['血糖数值(mmol/L)'].mean()
                            user_prompt = f"""
                                   时间段：{start_date} 至 {end_date}
                                   用户血糖记录（按时间顺序，共{len(df_g)}条）：
                                   {data_str}

                                   总体平均血糖：{overall_avg:.1f} mmol/L

                                   请根据以上完整的血糖记录，用一段话（不超过200字）向医生描述用户近期的血糖变化趋势。只需要客观陈述数值的高低、波动大小、餐前餐后的变化，备注中不同饮食所反映的血糖趋势变化等。不要与任何标准对比（不要帮用户和医生对数值“高低”下定义，可以对比得出高低变化趋势），也不要给出“正常/不正常”或“好/不好”的评价。
                                   """
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": "你是一位医疗数据报告助手，只负责客观描述数据趋势，不提供医疗建议。"},
                                    {"role": "user", "content": user_prompt}
                                ],
                                temperature=0.5,
                                max_tokens=400
                            )
                            ai_text = response.choices[0].message.content.strip()
                        except Exception as e:
                            st.warning(f"AI 总结生成失败：{e}")

                    # 生成PDF
                    temp_dir = tempfile.mkdtemp()
                    img_path = os.path.join(temp_dir, "glucose_trend.png")
                    fig_g.write_image(img_path, width=800, height=400, scale=2)

                    pdf_path = os.path.join(temp_dir, "glucose_report.pdf")
                    doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
                    story = []

                    # 使用已经定义好的 title_style（中文字体）
                    story.append(Paragraph(f"血糖健康报告（{start_date} 至 {end_date}）", title_style))
                    story.append(Spacer(1, 10 * mm))

                    # 插入趋势图（使用 heading_style）
                    story.append(Paragraph("血糖长期趋势图", heading_style))
                    story.append(Image(img_path, width=160 * mm, height=80 * mm, kind='proportional'))
                    story.append(Spacer(1, 8 * mm))

                    # 各时段平均血糖表（使用 heading_style 作为标题）
                    story.append(Paragraph("各时段平均血糖 (mmol/L)", heading_style))
                    data = [["测量时段", "平均血糖"]]
                    for _, row in period_avg.iterrows():
                        data.append([row['测量时段'], f"{row['血糖数值(mmol/L)']:.1f}"])
                    t = Table(data, colWidths=[80 * mm, 40 * mm])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),  # 表格内文字使用中文字体
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 8 * mm))

                    # 总体平均血糖
                    story.append(Paragraph("总体平均血糖", heading_style))
                    story.append(Paragraph(f"{overall_avg:.1f} mmol/L", normal_style))
                    story.append(Spacer(1, 8 * mm))

                    # AI 总结
                    if ai_text:
                        story.append(Paragraph("AI总结（仅供参考）", heading_style))
                        story.append(Paragraph(ai_text, normal_style))
                    else:
                        story.append(Paragraph("⚠️ 未生成 AI 总结（未配置 API 或调用失败）", normal_style))

                    doc.build(story)

                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label="📥 点击下载血糖报告 PDF",
                        data=pdf_bytes,
                        file_name=f"血糖报告_{start_date}_至_{end_date}.pdf",
                        mime="application/pdf"
                    )
                    shutil.rmtree(temp_dir, ignore_errors=True)
    # 血压报告打印
    with tab42:
        if df_b.empty:
            st.warning("当前时间段无血压数据，无法生成报告")
        else:
            if st.button("📄 生成血压报告 PDF", key="bp_pdf_btn", use_container_width=True):
                with st.spinner("正在生成血压报告，请稍后......"):

                    # 1.血压趋势图准备
                    df_b_plot = df_b.sort_values("日期")
                    df_b_plot['日期时间'] = df_b_plot["日期"] + " " + df_b_plot['具体时间']
                    df_b_plot['日期时间'] = pd.to_datetime(df_b_plot['日期时间'])
                    df_b_plot = df_b_plot.sort_values('日期时间')
                    fig_b = px.line(df_b_plot, x="日期时间", y=['高压（收缩压）mmHg', '低压（舒张压）mmHg'],
                                    markers=True, title='血压长期趋势图')
                    fig_b.update_layout(
                        xaxis_title="日期时间",
                        yaxis_title="血压 (mmHg)",
                        font=dict(family="Noto Sans CJK SC"),
                        plot_bgcolor='white',
                        xaxis=dict(tickangle=-45),
                        width=1000,
                        height=500
                    )
                    # 2.平均值准备
                    avg_sys = df_b["高压（收缩压）mmHg"].mean()
                    avg_dia = df_b["低压（舒张压）mmHg"].mean()

                    # 3.AI总结准备
                    ai_text = ""
                    if st.secrets.get("DEEPSEEK_API_KEY"):
                        try:
                            client = OpenAI(
                                api_key=st.secrets["DEEPSEEK_API_KEY"],
                                base_url=st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
                            )
                            df_b_sorted = df_b.sort_values(['日期', '具体时间'])
                            records = []
                            for _, row in df_b_sorted.iterrows():
                                note_part = f"，备注：{row['备注']}" if row['备注'] and row['备注'] != "状态良好" else ""
                                records.append(
                                    f"{row['日期']} {row['具体时间']} - 高压 {row['高压（收缩压）mmHg']} mmHg, 低压 {row['低压（舒张压）mmHg']} mmHg, 心率 {row['心率']} bpm{note_part}"
                                )
                            data_str = "\n".join(records)

                            avg_sys = df_b["高压（收缩压）mmHg"].mean()
                            avg_dia = df_b["低压（舒张压）mmHg"].mean()
                            user_prompt = f"""
                                   时间段：{start_date} 至 {end_date}
                                   用户血压记录（按时间顺序，共{len(df_b)}条）：
                                   {data_str}

                                   平均高压：{avg_sys:.1f} mmHg，平均低压：{avg_dia:.1f} mmHg

                                   请根据以上完整的血压数据，用一段话（不超过200字）向医生描述用户近期的血压变化趋势。只需要客观陈述数值的高低、波动大小、高低压的变化情况，不要与任何标准对比（不要帮用户和医生对数值“高低”下定义，可以对比得出高低变化趋势），也不要给出“正常/不正常”或“好/不好”的评价。如果备注中有相关信息，可以提及。
                                   """
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": "你是一位医疗数据报告助手，只负责客观描述数据趋势，不提供医疗建议。"},
                                    {"role": "user", "content": user_prompt}
                                ],
                                temperature=0.5,
                                max_tokens=400
                            )
                            ai_text = response.choices[0].message.content.strip()
                        except Exception as e:
                            st.warning(f"AI 总结生成失败：{e}")

                    # 生成PDF
                    temp_dir = tempfile.mkdtemp()
                    img_path = os.path.join(temp_dir, "bp_trend.png")
                    fig_b.write_image(img_path, width=800, height=400, scale=2)

                    pdf_path = os.path.join(temp_dir, "bp_report.pdf")
                    doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
                    story = []

                    # 直接使用 tab4 开头定义的 title_style（已包含中文字体）
                    story.append(Paragraph(f"血压健康报告（{start_date} 至 {end_date}）", title_style))
                    story.append(Spacer(1, 10 * mm))

                    # 插入趋势图（使用 heading_style）
                    story.append(Paragraph("血压长期趋势图", heading_style))
                    story.append(Image(img_path, width=160 * mm, height=80 * mm, kind='proportional'))
                    story.append(Spacer(1, 8 * mm))

                    # 血压平均值表（标题使用 heading_style，表格内容指定中文字体）
                    story.append(Paragraph("血压平均值 (mmHg)", heading_style))
                    bp_data = [["项目", "平均值"], ["高压（收缩压）", f"{avg_sys:.1f}"], ["低压（舒张压）", f"{avg_dia:.1f}"]]
                    bp_table = Table(bp_data, colWidths=[80 * mm, 40 * mm])
                    bp_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),  # 表格内文字使用中文字体
                    ]))
                    story.append(bp_table)
                    story.append(Spacer(1, 8 * mm))

                    # AI 总结（使用 normal_style 和 heading_style）
                    if ai_text:
                        story.append(Paragraph("AI总结（仅供参考）", heading_style))
                        story.append(Paragraph(ai_text, normal_style))
                    else:
                        story.append(Paragraph("⚠️ 未生成 AI 总结（未配置 API 或调用失败）", normal_style))

                    doc.build(story)

                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label="📥 点击下载血压报告 PDF",
                        data=pdf_bytes,
                        file_name=f"血压报告_{start_date}_至_{end_date}.pdf",
                        mime="application/pdf"
                    )
                    shutil.rmtree(temp_dir, ignore_errors=True)