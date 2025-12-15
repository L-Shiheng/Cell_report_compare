import streamlit as st
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
import seaborn as sns
from fpdf import FPDF
import tempfile
import os
import shutil
import gc
import numpy as np

# === 1. 基础配置 ===
st.set_page_config(page_title="成分对比报告 (终极版)", layout="wide")

# === 2. 字体加载逻辑 (核弹级修复) ===
def load_font(uploaded_font_file=None):
    font_path = None
    font_prop = None
    
    # 策略 A: 侧边栏上传
    if uploaded_font_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as tmp:
            tmp.write(uploaded_font_file.getvalue())
            font_path = tmp.name
        st.sidebar.success("✅ 已加载上传的字体文件！")

    # 策略 B: 本地查找
    elif font_path is None:
        possible_files = ['SimHei.ttf', 'simhei.ttf', 'NotoSansSC-Regular.ttf', 'msyh.ttf', 'MSYH.TTF']
        current_files = os.listdir('.')
        for f in possible_files:
            if f in current_files:
                font_path = os.path.abspath(f)
                break
    
    if font_path and os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        font_prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
        plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
        plt.rcParams['axes.unicode_minus'] = False
        return font_prop, font_path
    
    return None, None

# === 侧边栏：字体上传 ===
st.sidebar.header("🛠️ 字体工具")
uploaded_font = st.sidebar.file_uploader("若中文显示异常，请上传 SimHei.ttf", type=["ttf", "otf"])
custom_font_prop, loaded_font_path = load_font(uploaded_font)

# === 3. 配色方案 ===
COLOR_THEMES = {
    "商务蓝 (Professional Blue)": ["#2C3E50", "#34495E", "#4A6FA5", "#6D8EAD", "#94B0C7"],
    "清新绿 (Nature Green)": ["#27AE60", "#2ECC71", "#58D68D", "#82E0AA", "#ABEBC6"],
    "活力橙 (Vibrant Orange)": ["#D35400", "#E67E22", "#F39C12", "#F5B041", "#F8C471"],
    "莫兰迪 (Morandi)": ["#778899", "#8FBC8F", "#BC8F8F", "#B0C4DE", "#D8BFD8"],
    "经典柔和 (Set2)": sns.color_palette("Set2").as_hex(),
    "强对比 (Paired)": sns.color_palette("Paired").as_hex(),
    "标准十色 (Tab10)": sns.color_palette("tab10").as_hex(),
    "多色渐变 (Spectral)": sns.color_palette("Spectral", n_colors=10).as_hex(),
}

# === 4. 核心绘图函数 (柱状图版) ===

def create_comparison_image(row, name_col, data_cols, temp_dir, index, style_params):
    """
    生成单个化合物的【柱状图+表格】，正方形布局
    """
    comp_name = str(row[name_col])
    colors = style_params['colors']
    bar_width = style_params['bar_width']
    show_labels = style_params['show_labels']
    font_prop = style_params.get('font_prop')
    
    # 准备绘图数据
    plot_data = []
    table_vals = []
    for col in data_cols:
        val = pd.to_numeric(row[col], errors='coerce')
        val = 0 if pd.isna(val) else val
        plot_data.append(val)
        
        # 表格数值格式化
        if val == 0: s = "0"
        elif val % 1 == 0: s = f"{int(val):,}"
        elif abs(val) > 1000: s = f"{val:,.0f}"
        elif abs(val) < 0.01: s = f"{val:.4f}"
        else: s = f"{val:.2f}"
        table_vals.append(s)
        
    # 颜色循环
    bar_colors = [colors[i % len(colors)] for i in range(len(data_cols))]

    # === 创建画布 (高度比例 3:1.6，给表格留空间) ===
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 6), gridspec_kw={'height_ratios': [3, 1.6]})
    
    # 1. 柱状图
    x_pos = np.arange(len(data_cols))
    bars = ax1.bar(x_pos, plot_data, width=bar_width, color=bar_colors, edgecolor='none', alpha=0.9, zorder=3)
    
    # 样式修饰
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_color('#DDDDDD') 
    ax1.spines['bottom'].set_color('#666666')
    ax1.grid(axis='y', linestyle='--', alpha=0.4, color='gray', zorder=0)
    
    # 标题 (强制指定字体)
    title_font = font_prop if font_prop else None
    ax1.set_title(comp_name, fontsize=14, fontweight='bold', pad=12, color='#333333', fontproperties=title_font)
    
    # === 修改点 1 & 2: 添加中文坐标轴标签 ===
    # 注意：这里使用 fontproperties 确保如果有自定义字体，标签也能显示中文
    ax1.set_xlabel("种类", fontsize=10, labelpad=8, color='#555555', fontproperties=title_font)
    ax1.set_ylabel("峰面积比", fontsize=10, labelpad=8, color='#555555', fontproperties=title_font)
    
    # X轴标签处理
    ax1.set_xticks(x_pos)
    x_labels = [str(c) for c in data_cols]
    # 如果标签太长或太多，自动旋转
    if len(data_cols) > 4 or any(len(l) > 5 for l in x_labels):
        ax1.set_xticklabels(x_labels, rotation=30, ha='right', fontsize=9, fontproperties=title_font)
    else:
        ax1.set_xticklabels(x_labels, fontsize=10, fontproperties=title_font)
        
    # 数值标签
    if show_labels:
        ax1.bar_label(bars, fmt=lambda x: f"{x:,.0f}" if x>1000 else f"{x:.2f}", padding=3, fontsize=8, color='#555555')

    # 2. 数据表格
    ax2.axis('off')
    
    # 构建表格数据
    table_data = [data_cols, table_vals]
    
    # === 修改点 3: 表格行标签改为中文 ===
    the_table = ax2.table(
        cellText=table_data, 
        rowLabels=['种类', '峰面积比'], # <--- 这里改成了中文
        loc='center', 
        cellLoc='center',
        bbox=[0, 0, 1, 1]
    )
    
    # === 字体暴力加大 & 行高拉伸 ===
    num_cols = len(data_cols)
    font_size = 12 if num_cols < 4 else (10 if num_cols < 6 else 8)
    
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(font_size)
    the_table.scale(1, 1.5) # 拉高行高
    
    # 美化表格
    for (r, c), cell in the_table.get_celld().items():
        if r == 0: # 第一行 (表头/样品名)
            cell.set_facecolor('#F4F6F7')
            cell.set_text_props(weight='bold')
        cell.set_edgecolor('#DDDDDD')
    
    plt.tight_layout()
    
    img_path = os.path.join(temp_dir, f"bar_{index}.png")
    plt.savefig(img_path, dpi=100, bbox_inches='tight')
    plt.close('all')
    return img_path

def generate_grid_pdf(df, name_col, data_cols, cols_per_row, style_params):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Comparison Analysis Report', 0, 1, 'C')
    
    temp_dir = tempfile.mkdtemp()
    
    # A4 排版参数 (正方形网格)
    page_width = 210
    margin = 10
    usable_width = page_width - (2 * margin)
    gap = 5 
    img_width = (usable_width - (cols_per_row - 1) * gap) / cols_per_row
    img_height = img_width 
    
    x_start, y_start = margin, 25
    current_x, current_y = x_start, y_start
    page_break_y = 280 

    progress_bar = st.progress(0)
    status_text = st.empty()
    
    df = df.dropna(subset=[name_col])
    total_items = len(df)
    
    try:
        for i, (index, row) in enumerate(df.iterrows()):
            status_text.text(f"Processing {i+1}/{total_items}...")
            
            img_path = create_comparison_image(row, name_col, data_cols, temp_dir, i, style_params)
            
            if current_y + img_height > page_break_y:
                pdf.add_page()
                current_x = x_start
                current_y = 15
            
            pdf.image(img_path, x=current_x, y=current_y, w=img_width, h=img_height)
            
            if (i + 1) % cols_per_row == 0:
                current_x = x_start
                current_y += img_height + gap
            else:
                current_x += img_width + gap
            
            progress_bar.progress((i + 1) / total_items)
            if i % 20 == 0: gc.collect()

        out_path = os.path.join(temp_dir, "Comparison_Report.pdf")
        pdf.output(out_path)
        with open(out_path, "rb") as f:
            pdf_bytes = f.read()
        return pdf_bytes

    finally:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        plt.close('all')

# === 5. Streamlit 界面 ===
st.title("📊 成分对比报告 (终极网格版)")

# --- 侧边栏样式设置 ---
st.sidebar.markdown("---")
st.sidebar.header("🎨 样式设置")
selected_theme_name = st.sidebar.selectbox("1. 配色方案", list(COLOR_THEMES.keys()), index=6) # 默认 Tab10
selected_colors = COLOR_THEMES[selected_theme_name]

bar_width = st.sidebar.slider("2. 柱子宽度", 0.2, 0.9, 0.6, 0.1)
show_labels = st.sidebar.checkbox("3. 显示数值标签", value=True)

style_params = {
    'colors': selected_colors,
    'bar_width': bar_width,
    'show_labels': show_labels,
    'font_prop': custom_font_prop
}

# --- 文件上传区 ---
uploaded_file = st.file_uploader("上传 Excel 文件 (不同种类结果)", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    cols = df.columns.tolist()
    
    st.write("### 字段设置")
    c1, c2 = st.columns([1, 2])
    
    # 智能选择
    default_name = 0
    for idx, c in enumerate(cols):
        if str(c).lower() in ['name', 'compound', '化合物', '名称']: default_name = idx; break
            
    with c1: name_col = st.selectbox("化合物名称列", cols, index=default_name)
    with c2: 
        default_data = [c for c in cols if c != name_col]
        data_cols = st.multiselect("数据列 (样品)", cols, default=default_data)

    if data_cols:
        st.write("---")
        layout_col1, layout_col2 = st.columns([1, 4])
        
        with layout_col1:
            st.write("#### 排版设置")
            cols_per_row = st.radio("一行几个?", [1, 2, 3, 4], index=1)
        
        with layout_col2:
            st.write(f"#### 👁️ 效果预览 (前 {cols_per_row} 个)")
            if st.button("点击预览"):
                temp_preview_dir = tempfile.mkdtemp()
                try:
                    subset = df.dropna(subset=[name_col]).head(cols_per_row)
                    if len(subset) > 0:
                        preview_cols = st.columns(cols_per_row)
                        for i, (idx, row) in enumerate(subset.iterrows()):
                            p_path = create_comparison_image(row, name_col, data_cols, temp_preview_dir, i, style_params)
                            with preview_cols[i]:
                                st.image(p_path, caption=str(row[name_col]), use_column_width=True)
                finally:
                    shutil.rmtree(temp_preview_dir)

        st.write("---")
        if st.button("🚀 生成并下载 PDF"):
            with st.spinner("正在生成对比报告..."):
                pdf_bytes = generate_grid_pdf(df, name_col, data_cols, cols_per_row, style_params)
                if pdf_bytes:
                    st.success("PDF 生成成功！")
                    st.download_button(
                        label="📥 下载 PDF 报告",
                        data=pdf_bytes,
                        file_name=f"Comparison_Report_{cols_per_row}x.pdf",
                        mime="application/pdf"
                    )
