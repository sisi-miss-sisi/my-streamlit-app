import streamlit as st # 做网页界面
import pandas as pd # 用来存表格数据
import pytz
import datetime # 导入日期时间模块，记录日期和时间
import plotly.express as px # 用来画折线图
from io import BytesIO # 做PDF时临时存放数据用
from supabase import create_client, Client # 导入云端数据库Supabase客户端，实现数据云同步


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
st.set_page_config(page_title='老爸健康管家', layout='wide')
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
        </style>
    """, unsafe_allow_html=True)


# 页面布局
# 侧边筛选栏
st.sidebar.header("🗓️ 数据范围筛选")
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


st.title("👨‍ 老爸健康数据管理系统") # st.title()大标题
st.caption("数据已加密存储于云端，手机与电脑实时同步") # st.caption 小字提示

# 导航功能区：新建三个标签页
tab1, tab2, tab3 = st.tabs(["📝 填写记录", "📂 数据管理与导出", "📈 趋势分析"])


# 第一部分：数据录入
with tab1: # 把内容放在第一个标签页里面
    option = st.radio("请选择测量项目：", ("血糖记录", "血压记录"), horizontal=True)
    # st.radio("提示文字", (选项1，选项2), horizontal=True)
    # horizontal=True:选项横着放；horizontal=False:选项竖着放

    with st.form("input_form", clear_on_submit=True): # st.form("表单名", clear_on_submit=True):创建表单，提交后自动清空内容
        if option == "血糖记录": # 选择了记录血糖之后出来的表单
            d = st.date_input("日期", now_china.date())
            t = st.time_input("具体时间", now_china.time())
            p = st.selectbox("测量时段", ["早餐前（空腹）", "早餐后2小时", "午餐前", "午餐后2小时", "晚餐前", "晚餐后2小时"])
            v = st.number_input("血糖数值(mmol/L)", min_value = 0.0, max_value = 30.0, value = 10.0, step = 0.1)
            n = st.text_input("备注","状态良好")

            if st.form_submit_button("🚀 点击保存"): # 点击保存按钮后
                data = {"日期": str(d), "具体时间": str(t)[:5], "测量时段":p, "血糖数值(mmol/L)":v, "备注":n}
                supabase.table("glucose").insert(data).execute() # 把打包好的数据，存入云端数据库的 “glucose（血糖）表” 里
                st.success("✅ 血糖数据已存入云库！")

        else:
            d = st.date_input("日期", now_china.date())
            t = st.time_input("具体时间", now_china.time())
            sys = st.number_input("高压（收缩压）mmHg", value=160)
            dia = st.number_input("低压（舒张压）mmHg", value=95)
            a = st.selectbox("测量手臂",['左臂','右臂'])
            hr = st.number_input("心率", value=80)
            note = st.text_input("备注", "状态良好")

            if st.form_submit_button("🚀 点击保存"):
                data = {"日期": str(d), "具体时间": str(t)[0:5], "高压（收缩压）mmHg":sys,"低压（舒张压）mmHg":dia,"测量手臂":a,"心率":hr,"备注":note}
                supabase.table("bp").insert(data).execute()
                st.success("✅ 血压数据已存入云库！")


# 第二部分：数据管理与导出
with tab2:
    st.header("数据管理中心")

    # 获取血糖数据
    res_g = supabase.table("glucose").select('*').gte("日期", str(start_date)).lte("日期", str(end_date)).order("日期", desc=True).execute() # desc=True:降序/desc=False:升序
    df_g = pd.DataFrame(res_g.data)

    # 获取血压数值
    res_b = supabase.table("bp").select('*').gte("日期", str(start_date)).lte("日期", str(end_date)).order("日期", desc=True).order("具体时间",desc=True).execute() # desc=True:降序/desc=False:升序
    df_b = pd.DataFrame(res_b.data)


    # 页面里新建两个页面
    tab4, tab5 = st.tabs(["血糖记录", "血压记录"])

    # 血糖记录
    with tab4:
        st.subheader("🩸 血糖记录编辑")
        if not df_g.empty:
            # Excel导出功能
            output_g = BytesIO()
            with pd.ExcelWriter(output_g, engine='xlsxwriter') as writer:
                df_g.to_excel(writer, index=False, sheet_name='血糖记录')
            st.download_button("📥 下载血糖 Excel", output_g.getvalue(), "血糖记录.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # 删除功能
            del_g = st.selectbox("选择要删除的记录序号", ["请选择"] + df_g['序号'].tolist(), key="del_g")

            if st.button("🗑️ 删除选中的血糖记录") and del_g != "请选择":
                supabase.table("glucose").delete().eq("序号", del_g).execute()
                st.rerun()
            st.dataframe(df_g, use_container_width=True, hide_index=True)



        else:
            st.write("暂无血糖记录")


    #血压记录
    with tab5:
        st.subheader("💓 血压记录编辑")
        if not df_b.empty:
            # Excel导出功能
            output_b = BytesIO()
            with pd.ExcelWriter(output_b,engine='xlsxwriter') as writer:
                df_b.to_excel(writer, index=False, sheet_name='血压记录')
            st.download_button("📥 下载血压 Excel", output_b.getvalue(), "血压记录.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # 删除功能
            del_b = st.selectbox("选择要删除的记录序号", ["请选择"] + df_b['序号'].tolist(), key='del_b')
            if st.button("🗑️ 删除选中的血压记录") and del_b != "请选择":
                supabase.table("bp").delete().eq("序号", del_b).execute()
                st.rerun()
            st.dataframe(df_b, use_container_width=True, hide_index=True)

        else:
            st.write("暂无血压记录")

# 第三部分：数据可视化（平均值计算）与打印
with tab3:
    st.header("趋势分析与平均值")
    st.write(f"当前显示从{start_date} 至 {end_date} 的数据")

    tab6, tab7 = st.tabs(['血糖可视化', '血压可视化'])

    with tab6:
        if not df_g.empty:
            # 计算平均值
            avg_glucose = df_g['血糖数值(mmol/L)'].mean()
            # 使用 st.metric 突出显示
            st.metric("📊 平均血糖", f"{avg_glucose:.2f} mmol")

            # 按时段分组平均值
            st.subheader("各时段平均血糖")
            period_avg = df_g.groupby('测量时段')['血糖数值(mmol/L)'].mean().reset_index()
            st.dataframe(period_avg, use_container_width=True)

            # 降采样或排序处理
            df_g_plot = df_g.sort_values("日期")
            df_g_plot["日期时间"] = df_g_plot["日期"] + " " + df_g_plot["具体时间"]
            df_g_plot["日期时间"] = pd.to_datetime(df_g_plot["日期时间"])
            df_g_plot = df_g_plot.sort_values("日期时间")
            # 绘图
            fig_g_plot = px.line(df_g_plot, x="日期时间", y="血糖数值(mmol/L)", color="测量时段", markers=True, title="血糖长期趋势图")
            # 优化横坐标
            fig_g_plot.update_layout(xaxis=dict(tickangle=-45, tickformat='%y-%m-%d %H:%M'))
            # 显示图表
            st.plotly_chart(fig_g_plot, use_container_width=True)
            st.info("💡 提示：将鼠标悬停在图表右上角，点击‘相机’图标可下载高清打印图片")
        else:
            st.write("暂时还没有录入血糖数据哦~")



    with tab7:
        if not df_b.empty:
            # 计算平均值
            # 高压
            avg_bp1 = df_b["高压（收缩压）mmHg"].mean()
            # 使用st.metric 突出显示
            st.metric("📊 高压平均值", f"{avg_bp1:.2f} mmHg")
            # 低压
            avg_bp2 = df_b["低压（舒张压）mmHg"].mean()
            st.metric("📊 低压平均值", f"{avg_bp2:.2f} mmHg")


            # 降采样或排序处理
            df_b_plot = df_b.sort_values("日期")
            df_b_plot['日期时间'] = df_b_plot["日期"] +  " " + df_b_plot['具体时间']
            df_b_plot['日期时间'] = pd.to_datetime(df_b_plot['日期时间'])
            df_b_plot = df_b_plot.sort_values('日期时间')

            # 绘图
            fig_b_plot = px.line(df_b_plot, x="日期时间", y=['高压（收缩压）mmHg', '低压（舒张压）mmHg'], markers=True, title='血压长期趋势图')
            fig_b_plot.update_layout(xaxis=dict(tickangle=-45, tickformat='%Y-%m-%d %H:%M'))
            st.plotly_chart(fig_b_plot, use_container_width=True)
            st.info("💡 提示：将鼠标悬停在图表右上角，点击‘相机’图标可下载高清打印图片")





















