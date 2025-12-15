import streamlit as st
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from fpdf import FPDF
import tempfile
import os
import shutil
import gc
import numpy as np

# === 1. 基础配置 ===
st.set_page_config(page_title="均匀排版生成器", layout="wide")

# 中文字体设置
plt.rcParams['axes.unicode_minus'] = False
possible_fonts = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial Unicode MS', 'PingFang SC', 'Heiti TC']
found_font = None
for font in possible_fonts:
    try:
        plt.rcParams['font.sans-serif'] = [font]
        fig_test = plt.figure(); plt.text(0.5,0.5,'测'); plt.close(fig_test)
        found_font = font; break
    except: continue

# === 2. 配色方案 ===
COLOR_THEMES = {
    "商务蓝 (Professional Blue)": ["#2C3E50", "#34495E", "#4A6FA5", "#6D8EAD", "#94B0C7"],
    "清新绿 (Nature Green)": ["#27AE60", "#2ECC71", "#58D68D", "#82E0AA", "#ABEBC6"],
    "活力橙 (Vibrant Orange)": ["#D35400", "#E67E22", "#F39C12", "#F5B041", "#F8C471"],
    "莫兰迪 (Morandi)": ["#778899", "#8FBC8F", "#BC8F8F", "#B0C4DE", "#D8BFD8"],
    "经典多色 (Classic Set2)": sns.color_palette("Set2").as_hex(),
    "科技紫 (Tech Purple)": ["#6C3483", "#8E44AD", "#A569BD", "#BB8FCE", "#D2B4DE"]
}

# === 3. 核心绘图函数 (算法升级) ===

def create_compound_image(row, name_col, data_cols, temp_dir, index, style_params):
    """
    生成正方形图表，间距完全均匀
    """
    comp_name = str(row[name_col])
    gap_ratio = style_params['gap_ratio']  # 0.1 ~ 0.8
    color_palette = style_params['colors']
    show_labels = style_params['show_labels']
    
    # === 算法核心：如何实现间距完全相等 ===
    # 设 柱间距 = 侧边留白 = gap
    # 柱宽 bar_width = 1 - gap
    # 这样，无论 x 轴间距是多少(1.0)，柱子之间的空隙永远是 gap
    # 而我们在 set_xlim 时，额外留出 gap 的距离，就能实现侧边留白等于柱间距
    
    bar_width = 1.0 - gap_ratio
    side_margin = gap_ratio # 侧边留白等于空隙
    
    # 数据准备
    plot_data = []
    table_row_vals = []
    for col in data_cols:
        val = pd.to_numeric(row[col], errors='coerce')
        val = 0 if pd.isna(val) else val
        plot_data.append(val)
        val_fmt = f"{val:.4f}" if 0 < abs(val) < 0.1 else (f"{val:.2f}" if val % 1 != 0 else f"{val:.0f}")
        table_row_vals.append(val_fmt)
    
    bar_colors = [color_palette[i % len(color_palette)] for i in range(len(data_cols))]

    # === 绘图 ===
    # figsize=(6, 6) 保证原始画布是正方形
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 6), gridspec_kw={'height_ratios': [3, 1]})
    
    x_pos = np.arange(len(data_cols))
    
    # 画柱子
    bars = ax1.bar(x_pos, plot_data, width=bar_width, color=bar_colors, edgecolor='none', alpha=0.9, zorder=3)
    
    # --- 关键修改：手动设置 X 轴范围 ---
    # 左边界 = 第一个柱子中心(0) - 半个柱宽 - 侧边留白
    x_min = 0 - (bar_width / 2) - side_margin
    # 右边界 = 最后一个柱子中心(N-1) + 半个柱宽 + 侧边留白
    x_max = (len(data_cols) - 1) + (bar_width / 2) + side_margin
    ax1.set_xlim(x_min, x_max)
    
    # 细节修饰
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_color('#DDDDDD')
    ax1.spines['bottom'].set_color('#666666')
    ax1.grid(axis='y', linestyle='--', alpha=0.4, color='gray', zorder=0)
    
    ax1.set_title(comp_name, fontsize=14, fontweight='bold', pad=15, color='#333333')
    ax1.set_xticks(x_pos)
    
    x_labels = [str(c) for c in data_cols]
    if len(data_cols) > 3 or any(len(l) > 6 for l in x_labels):
        ax1.set_xticklabels(x_labels, rotation=30, ha='right', fontsize=9)
    else:
        ax1.set_xticklabels(x_labels, fontsize=10)
        
    if show_labels:
        ax1.bar_label(bars, fmt='%.2f', padding=3, fontsize=8, color='#555555')

    # 表格部分
    ax2.axis('off')
    table_data = [data_cols, table_row_vals]
    the_table = ax2.table(
        cellText=table_data, 
        rowLabels=['样品', '峰面积比'], 
        loc='center', 
        cellLoc='center',
        bbox=[0, 0, 1, 1]
    )
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(12)
    for (r, c), cell in the_table.get_celld().items():
        if r == 0: cell.set_facecolor('#F4F6F7') 
        cell.set_edgecolor('#DDDDDD')
    
    plt.tight_layout()
    
    img_path = os.path.join(temp_dir, f"chart_{index}.png")
    plt.savefig(img_path, dpi=100, bbox_inches='tight')
    plt.close('all')
    return img_path

def generate_grid_pdf(df, name_col, data_cols, cols_per_row, style_params):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Comparison Report', 0, 1, 'C')
    
    temp_dir = tempfile.mkdtemp()
    
    # === A4 排版计算 ===
    page_width = 210
    margin = 10
    usable_width = page_width - (2 * margin)
    gap = 5 
    
    # 1. 计算每个图的宽度
    img_width = (usable_width - (cols_per_row - 1) * gap) / cols_per_row
    
    # 2. 强制正方形：高度 = 宽度
    # 这样整个块就是一个完美的正方形
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
            
            img_path = create_compound_image(row, name_col, data_cols, temp_dir, i, style_params)
            
            # 换页检测
            if current_y + img_height > page_break_y:
                pdf.add_page()
                current_x = x_start
                current_y = 15
            
            pdf.image(img_path, x=current_x, y=current_y, w=img_width, h=img_height)
            
            # 移动坐标
            if (i + 1) % cols_per_row == 0:
                current_x = x_start
                current_y += img_height + gap # 加上间隙
            else:
                current_x += img_width + gap
            
            progress_bar.progress((i + 1) / total_items)
            if i % 20 == 0: gc.collect()

        out_path = os.path.join(temp_dir, "Final_Report.pdf")
        pdf.output(out_path)
        with open(out_path, "rb") as f:
            pdf_bytes = f.read()
        return pdf_bytes

    finally:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        plt.close('all')

# === 4. Streamlit 界面 ===
st.title("🔲 均匀正方形排版生成器")

st.sidebar.header("🎨 样式控制")

# 1. 颜色
selected_theme_name = st.sidebar.selectbox("1. 配色方案", list(COLOR_THEMES.keys()), index=0)
selected_colors = COLOR_THEMES[selected_theme_name]

st.sidebar.markdown("---")
# 2. 统一间距控制 (核心修改)
st.sidebar.info("💡 **一键调距**：此滑块同时控制「侧边留白」和「柱间距」，保持画面均匀。")
gap_ratio = st.sidebar.slider("2. 空隙率 (Gap Ratio)", 0.1, 0.8, 0.4, 0.05)
st.sidebar.caption(f"当前状态：柱宽 {1-gap_ratio:.1f} | 间距 {gap_ratio:.1f} | 两侧留白 {gap_ratio:.1f}")

show_labels = st.sidebar.checkbox("3. 显示数值", value=True)

style_params = {
    'colors': selected_colors,
    'gap_ratio': gap_ratio,
    'show_labels': show_labels
}

# 主界面
if found_font:
    st.caption(f"✅ 中文支持: {found_font}")
else:
    st.warning("⚠️ 未检测到中文字体")

uploaded_file = st.file_uploader("上传 Excel 文件", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    cols = df.columns.tolist()
    
    st.write("### 数据设置")
    c1, c2 = st.columns([1, 2])
    
    default_name = 0
    for idx, c in enumerate(cols):
        if str(c).lower() in ['name', 'compound', '化合物', '名称']: default_name = idx; break
            
    with c1: name_col = st.selectbox("化合物名称列", cols, index=default_name)
    with c2: 
        default_data = [c for c in cols if c != name_col]
        data_cols = st.multiselect("数据列 (样品)", cols, default=default_data)

    if data_cols:
        st.write("---")
        st.write("### 排版预览")
        
        layout_col1, layout_col2 = st.columns([1, 4])
        with layout_col1:
            cols_per_row = st.radio("一行显示几个?", [2, 3, 4], index=0)
            st.info(f"模式: 一行{cols_per_row}个 (自动正方形)")

        with layout_col2:
            st.write(f"#### 👁️ 真实排版预览 (前 {cols_per_row} 个)")
            
            if st.button("点击预览 (查看间距与正方形效果)"):
                temp_preview_dir = tempfile.mkdtemp()
                try:
                    subset = df.dropna(subset=[name_col]).head(cols_per_row)
                    if len(subset) > 0:
                        preview_cols = st.columns(cols_per_row)
                        for i, (idx, row) in enumerate(subset.iterrows()):
                            p_path = create_compound_image(row, name_col, data_cols, temp_preview_dir, i, style_params)
                            with preview_cols[i]:
                                st.image(p_path, caption=f"化合物 {i+1}", use_column_width=True)
                        st.success("✅ 预览成功！这显示了在 PDF 中的真实正方形比例。")
                finally:
                    shutil.rmtree(temp_preview_dir)

        st.write("---")
        if st.button("🚀 生成 PDF"):
            with st.spinner("正在生成正方形排版报告..."):
                pdf_bytes = generate_grid_pdf(df, name_col, data_cols, cols_per_row, style_params)
                if pdf_bytes:
                    st.success("PDF 生成成功！")
                    st.download_button(
                        label="📥 下载 PDF 报告",
                        data=pdf_bytes,
                        file_name=f"Square_Report_{cols_per_row}x.pdf",
                        mime="application/pdf"
                    )
