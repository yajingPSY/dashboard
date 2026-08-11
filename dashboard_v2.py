# dashboard.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import colorsys
import numpy as np
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import warnings
from datetime import datetime, timedelta
import os
import chardet
import re

warnings.filterwarnings('ignore')

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="物料消耗看板",
    page_icon="📊",
    layout="wide"
)

# ==================== 数据文件路径配置 ====================
# 在这里配置数据文件路径
DATA_CONFIG = {
    'sales_path': "./DATA/7月商品销售汇总表.csv",  
    'bom_path': "./DATA/单杯物料消耗明细.csv",  
    'order_path':"./DATA/7月报货单明细.csv", 
}

# ==================== 字体配置 ====================
def setup_chinese_font():
    available_fonts = [f.name for f in fm.fontManager.ttflist]

    font_priority = [
        'Microsoft YaHei', 'Microsoft YaHei UI', 'SimHei',
        'PingFang SC', 'Heiti SC', 'STHeiti',
        'WenQuanYi Micro Hei', 'Noto Sans CJK SC',
        'Arial Unicode MS', 'DejaVu Sans'
    ]

    selected_font = None
    for font in font_priority:
        if font in available_fonts:
            selected_font = font
            break

    if selected_font is None:
        selected_font = 'DejaVu Sans'

    plt.rcParams['font.sans-serif'] = [selected_font]
    plt.rcParams['font.family'] = 'sans-serif'

    return selected_font

# ==================== 看板视觉风格（来自品牌配色方案） ====================
# 品牌色板：青蓝绿 Teal 商务系
BRAND_COLORS = {
    'primary':      '#2D7A8A',   # 主青蓝绿（强调色）
    'dark':         '#111727',   # 深藏蓝（标题/文字/深色面）
    'mint':         '#B7DBD1',   # 浅薄荷绿（浅色辅助）
    'slate':        '#739EA7',   # 蓝灰（过渡/次级系列）
    'gray_blue':    '#6B7380',   # 灰蓝（次级文字/边框）
    'light_bg':     '#E0E5F1',   # 浅蓝白（页面背景）
    'card_bg':      '#D5DCE8',   # 卡片背景（比页面深一度，同色系）
    'ink':          '#393C45',   # 深灰（正文）
    'gold':         '#E4BD5B',   # 金色（警示/高亮，来自模板）
}

# 语义色（异常状态，固定，不参与系列色循环）
STATUS_COLORS = {
    'normal':   '#2D7A8A',   # 正常 → 青绿
    'over':     '#E4BD5B',   # 过度订货 → 金色警示
    'under':    '#B03A2E',   # 订货不足 → 深红（模板粉棕加深）
    'up':       '#2D7A8A',   # 涨 → 青绿
    'down':     '#B03A2E',   # 跌 → 深红
}

# 分类系列色（固定顺序，不循环；超过则并入"其他"）
SERIES_COLORS = ['#2D7A8A', '#111727', '#739EA7', '#E4BD5B', '#6B7380', '#B03A2E']

def inject_css():
    """注入全局 CSS：侧边栏、KPI 卡片、分区标题、图表卡片"""
    st.markdown(f"""
    <style>
        /* ---- 侧边栏：深藏蓝 ---- */
        [data-testid="stSidebar"] {{
            background-color: {BRAND_COLORS['dark']};
        }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stRadio label {{
            color: {BRAND_COLORS['light_bg']};
        }}
        [data-testid="stSidebar"] hr {{
            border-color: rgba(224, 229, 241, 0.2);
        }}

        /* ---- 侧边栏导航（模板风格：整宽导航块） ---- */
        /* "选择页面"标签 */
        [data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stWidgetLabel"] p {{
            font-size: 16px;
            font-weight: 600;
            color: {BRAND_COLORS['mint']};
            margin-bottom: 8px;
        }}
        /* 选项块 */
        [data-testid="stSidebar"] [data-testid="stRadio"] label:not([data-testid="stWidgetLabel"]) {{
            display: flex;
            align-items: center;
            width: 100%;
            padding: 11px 14px;
            margin: 4px 0;
            border-radius: 8px;
            font-size: 17px;
            font-weight: 500;
            cursor: pointer;
            transition: background-color 0.3s;
        }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label:not([data-testid="stWidgetLabel"]):hover {{
            background-color: #2D6C78;
        }}
        /* 选中项：青绿底 + 左侧薄荷色条（对应模板 active 高亮） */
        [data-testid="stSidebar"] [data-testid="stRadio"] label:not([data-testid="stWidgetLabel"]):has(input:checked) {{
            background-color: {BRAND_COLORS['primary']};
            border-left: 4px solid {BRAND_COLORS['mint']};
            color: #FFFFFF;
        }}
        /* 隐藏默认 radio 圆点 */
        [data-testid="stSidebar"] [data-testid="stRadio"] input {{
            display: none;
        }}

        /* ---- 侧边栏刷新按钮：置底 + 放大 ---- */
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            display: flex;
            flex-direction: column;
            min-height: 100%;
        }}
        [data-testid="stSidebar"] [data-testid="stButton"] {{
            margin-top: auto;
        }}
        [data-testid="stSidebar"] .stButton button {{
            background-color: {BRAND_COLORS['primary']};
            color: #FFFFFF;
            border: none;
            font-size: 16px;
            padding: 10px 12px;
        }}
        [data-testid="stSidebar"] .stButton button:hover {{
            background-color: #2D6C78;
            color: #FFFFFF;
        }}

        /* ---- 页面背景与文字 ---- */
        [data-testid="stAppViewContainer"] {{
            background-color: {BRAND_COLORS['light_bg']};
        }}
        [data-testid="stHeader"] {{
            background-color: transparent;
        }}

        /* ---- 分区标题：青色左边线 ---- */
        .main h2, .main h3 {{
            color: {BRAND_COLORS['dark']};
            border-left: 4px solid {BRAND_COLORS['primary']};
            padding-left: 10px;
            margin-top: 24px;
        }}

        /* ---- KPI 指标卡：浅灰蓝底圆角 + 青色顶条 ---- */
        [data-testid="stMetric"] {{
            background-color: {BRAND_COLORS['card_bg']};
            border-radius: 10px;
            padding: 14px 16px;
            border-top: 3px solid {BRAND_COLORS['primary']};
            box-shadow: 0 1px 4px rgba(17, 23, 39, 0.08);
        }}

        /* ---- 图表容器卡（st.container(border=True)）：浅灰蓝底 ---- */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {BRAND_COLORS['card_bg']};
            border-radius: 10px;
            border: 1px solid rgba(17, 23, 39, 0.08);
        }}
        [data-testid="stMetricLabel"] p {{
            color: {BRAND_COLORS['gray_blue']};
        }}
        [data-testid="stMetricValue"] {{
            color: {BRAND_COLORS['dark']};
        }}
        [data-testid="stMetricDelta"] {{
            font-weight: 600;
        }}

        /* ---- 主按钮 ---- */
        .stButton > button {{
            background-color: {BRAND_COLORS['primary']};
            color: #FFFFFF;
            border: none;
        }}
        .stButton > button:hover {{
            background-color: #2D6C78;
            color: #FFFFFF;
            border: none;
        }}

        /* ---- 筛选器：背景与 KPI 卡片同色 ---- */
        [data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child {{
            background-color: {BRAND_COLORS['card_bg']};
        }}
        [data-testid="stDateInput"] [data-baseweb="input"] {{
            background-color: {BRAND_COLORS['card_bg']};
        }}

        /* ---- 数据表格表头 ---- */
        [data-testid="stDataFrame"] thead th {{
            background-color: {BRAND_COLORS['mint']};
            color: {BRAND_COLORS['dark']};
        }}

        /* ---- 下载按钮 ---- */
        .stDownloadButton button {{
            background-color: {BRAND_COLORS['dark']};
            color: #FFFFFF;
            border: none;
        }}
        .stDownloadButton button:hover {{
            background-color: #1a2540;
            color: #FFFFFF;
        }}
    </style>
    """, unsafe_allow_html=True)

def setup_chart_style():
    """matplotlib 图表统一样式：无顶/右边框、浅灰网格、品牌墨色"""
    plt.rcParams['axes.edgecolor'] = '#6B7380'
    plt.rcParams['axes.labelcolor'] = '#393C45'
    plt.rcParams['xtick.color'] = '#6B7380'
    plt.rcParams['ytick.color'] = '#6B7380'
    plt.rcParams['axes.titlecolor'] = '#111727'
    plt.rcParams['grid.color'] = '#D8DEE8'
    plt.rcParams['grid.linewidth'] = 0.8
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.spines.right'] = False
    plt.rcParams['figure.facecolor'] = '#F2F5FA'  # 图表背景浅蓝白，融入卡片
    plt.rcParams['axes.facecolor'] = '#F2F5FA'

def style_axes(ax):
    """去除顶部和右侧边框，浅色网格线"""
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.set_axisbelow(True)

# ==================== 编码检测和CSV读取函数 ====================
def detect_encoding(file_path):
    """检测文件编码"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
            result = chardet.detect(raw_data)
            return result['encoding']
    except:
        return None

def read_csv_with_encoding(file_path):
    """增强版CSV读取函数，专门处理中文编码问题"""
    import re
    
    # 定义中文检测函数
    def has_chinese(text):
        return bool(re.search(r'[\u4e00-\u9fff]', str(text)))
    
    # 1. 首先尝试用chardet检测
    detected = detect_encoding(file_path)
    encodings = [detected] if detected else []
    
    # 2. 添加常见中文编码（按优先级排序）
    encodings.extend(['utf-8-sig', 'gb18030', 'gbk', 'gb2312', 'utf-8'])
    encodings.extend(['latin1', 'cp1252', 'iso-8859-1'])
    
    # 去重
    encodings = list(dict.fromkeys(encodings))
    
    # 3. 尝试各种分隔符
    separators = [',', ';', '\t', '|', '，', '、']
    
    for encoding in encodings:
        if encoding is None:
            continue
        for sep in separators:
            try:
                df = pd.read_csv(
                    file_path, 
                    encoding=encoding, 
                    sep=sep,
                    engine='python',
                    on_bad_lines='warn'
                )
                
                # 检查是否成功读取
                if df.empty or len(df.columns) < 2:
                    continue
                
                # 清理列名
                df.columns = df.columns.str.strip()
                df.columns = df.columns.str.replace('\ufeff', '', regex=False)
                
                # 检查列名是否包含中文（说明编码正确）
                chinese_cols = sum(1 for col in df.columns if has_chinese(col))
                if chinese_cols >= len(df.columns) * 0.5:  # 至少一半列名是中文
                    print(f"成功读取，编码: {encoding}, 分隔符: {sep}")
                    return df
                    
            except Exception as e:
                continue
    
    # 4. 最后尝试：用二进制方式读取并手动解码
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            # 尝试用不同编码解码
            for encoding in ['gb18030', 'utf-8', 'gbk']:
                try:
                    text = content.decode(encoding)
                    # 将文本转为DataFrame
                    import io
                    df = pd.read_csv(io.StringIO(text), engine='python')
                    df.columns = df.columns.str.strip()
                    if has_chinese(df.columns[0]):
                        return df
                except:
                    continue
    except:
        pass
    
    raise Exception(f"无法读取CSV文件。请检查文件是否为有效的CSV格式，编码应为UTF-8或GBK。")

# ==================== 数据处理函数 ====================
@st.cache_data
def load_and_process_data(sales_path, bom_path, order_path):
    """加载并处理数据"""
    # 读取销售数据 - 使用改进的读取函数
    data = read_csv_with_encoding(sales_path)

    # 检查数据是否为空
    if data.empty:
        raise Exception("CSV文件为空或无法正确读取")

    # 去除列名中的空格
    data.columns = data.columns.str.strip()

    # 检查必要的列是否存在
    required_columns = ['商品/套餐名称', '商品销量', '门店编码', '商品id', '机构名称', '做法']
    missing_columns = [col for col in required_columns if col not in data.columns]
    if missing_columns:
        st.warning(f"缺少以下列: {missing_columns}")
        st.info(f"当前列名: {data.columns.tolist()}")
        raise Exception(f"CSV文件缺少必要的列: {missing_columns}")

    # 数据清洗
    data = data.dropna(subset=['商品/套餐名称'])
    data = data[data['商品销量'] > 0]

    # 替换特殊字符
    data['商品/套餐名称'] = data['商品/套餐名称'].astype(str).str.replace('`', '', regex=False)
    data['门店编码'] = data['门店编码'].astype(str).str.replace('`', '', regex=False)
    data['商品id'] = data['商品id'].astype(str).str.replace('`', '', regex=False)

    # 拆分机构
    def split_org_name_ignore_region(name):
        parts = str(name).split('-')
        if len(parts) >= 3:
            return pd.Series({
                '事业部': parts[0],
                '大区': parts[1],
                '督导': parts[-1]
            })
        else:
            return pd.Series({
                '事业部': parts[0] if len(parts) > 0 else '未知',
                '大区': parts[1] if len(parts) > 1 else '未知',
                '督导': parts[-1] if len(parts) > 0 else '未知'
            })

    data[['事业部', '大区', '督导']] = data['机构名称'].apply(split_org_name_ignore_region)

    # 拆分做法
    KEYWORDS = {
        '咖啡豆_茶底_口味': ['IIAC金奖咖啡豆', '茉莉绿妍', '正山小种', '红苹果风味', '汤力风味', '意式拼配', '耶加雪菲豆'],
        '杯型': ['m', 'L', 'l', 'M'],
        '温度': ['冰', '热', '温', '常温'],
        '糖度': ['糖']
    }

    def smart_split_zuofa_v2(zuofa):
        if pd.isna(zuofa) or str(zuofa).strip() == '' or str(zuofa).strip() == '-':
            return pd.Series(['未知', '未知', '未知', '未知', '未知'])

        parts = [p.strip() for p in str(zuofa).split(',')]

        result = {
            '咖啡豆_茶底_口味': '未知',
            '杯型': '未知',
            '温度': '未知',
            '糖度': '未知',
            '其他': '未知'
        }

        for part in parts:
            if part == '-':
                continue

            classified = False
            for key, kw_list in KEYWORDS.items():
                if any(kw in part for kw in kw_list):
                    if key == '杯型' and '糖' in part:
                        continue
                    result[key] = part
                    classified = True
                    break

            if not classified:
                if result['其他'] == '未知':
                    result['其他'] = part
                else:
                    result['其他'] += ',' + part

        if result['杯型'] == '未知':
            import re
            for part in parts:
                if re.search(r'\d+ml', part):
                    result['杯型'] = part
                    break

        return pd.Series([result['咖啡豆_茶底_口味'], result['杯型'], result['温度'], result['糖度'], result['其他']])

    data[['咖啡豆_茶底_口味', '杯型', '温度', '糖度', '其他']] = data['做法'].apply(smart_split_zuofa_v2)

    # 标准化商品名称
    REMOVE_PATTERNS = re.compile(
        r'【交个朋友】|【拼团】|\(拼\)|【甄选爆品】|【爆品】|（拼）|【马蹄爆爆珠】|【经典美味】|【美式经典】|'
        r'\(甄选爆品\)|\(爆品价\)|-默认|（爆品价）|'
        r'（可热饮）|\(可热饮\)|'
        r'\(升级版\)|\(经典款\)|（IIAC金奖咖啡豆）|'
        r'（可选热饮）|\(可选热饮\)|\(到店自取5.8\)|'
        r'小咖咖啡|【已下架】|可自取丨特惠|【首杯特价】|（特惠）|\(首创\)|·首创|（480ml）'
    )

    def standardize_product_name(name):
        if pd.isna(name):
            return name
        name = str(name).strip()
        name = REMOVE_PATTERNS.sub('', name)
        name = re.sub(r'[（(]1L[）)]', '(1L装)', name)
        name = re.sub(r'（1L装）', '(1L装)', name)
        name = re.sub(r'【一升桶】', '(1L装)', name)
        name = re.sub(r'（1升装）', '(1L装)', name)
        name = ' '.join(name.split())
        return name

    data['商品名称'] = data['商品/套餐名称'].apply(standardize_product_name)

    # 名称映射
    name_mapping = {
        '橙C茉莉果茶': '橙C茉莉茶',
        '橙c茉莉茶': '橙C茉莉茶',
        '橙c美式': '橙C气泡美式',
        '橙C气泡美式': '橙C气泡美式',
        '大桶美式1L装': '一大大大桶美式(1L装)',
        '美式一大桶': '一大大大桶美式(1L装)',
        '美式一大桶(1L装)': '一大大大桶美式(1L装)',
        '一大大大桶金奖美式(1L装)': '一大大大桶美式(1L装)',
        '大桶椰子水': '一大大大桶超清爽椰子水(1L装)',
        '1L桶清爽椰子水': '一大大大桶超清爽椰子水(1L装)',
        '一大大大桶超级电解生椰水(1L装)': '一大大大桶超清爽椰子水(1L装)',
        '一大大大桶椰青冰萃美式(1L装)': '一大大大桶椰青美式(1L装)',
        '热美式咖啡': '美式',
        '美式咖啡': '美式',
        '金奖美式': '美式',
        '【七夕CP】美式＋拿铁': '【双拼】美式＋拿铁',
        '拿铁咖啡': '拿铁',
        '万山红·红茶拿铁': '红茶拿铁',
        '经典拿铁': '拿铁',
        '椰青冰萃美式': '椰青美式',
        '黄油风味美式（全冰去水）': '全冰小黄油风味美式',
        '【快乐芭芭】芭乐白糯米酸奶+送芭乐凉感眼罩':'芭乐白糯米酸奶',
        '一大大大桶橙C冰美式(1L装)': '一大大大桶橙C气泡美式(1L装)',
        '一大大大桶橙C美式(1L装)': '一大大大桶橙C气泡美式(1L装)',
        '一大大桶橙c气泡冰美式(1L装)': '一大大大桶橙C气泡美式(1L装)',
        '奇异果葡萄气泡茶':'奇异果葡萄气泡'
    }
    data['商品名称'] = data['商品名称'].replace(name_mapping)

    # 糖葫芦系列特殊处理
    TOPPING_IDS = [1240991367226466305, 1249352432464445440]

    def add_topping_label(name, product_id):
        if pd.isna(name) or pd.isna(product_id):
            return name
        if str(product_id) in [str(pid) for pid in TOPPING_IDS]:
            if '含Topping' not in str(name):
                return f"{name}(含Topping)"
        return name

    data['商品名称'] = data.apply(
        lambda row: add_topping_label(row['商品名称'], row['商品id']),
        axis=1
    )

    # 小金鱼气泡水特殊处理
    def add_flavor_to_name(row):
        name = row['商品名称']
        flavor = row['咖啡豆_茶底_口味']
        if pd.isna(name) or pd.isna(flavor):
            return name
        name = str(name)
        flavor = str(flavor)
        flavor_suffix_map = {
            '红苹果风味': '(红苹果风味)',
            '汤力风味': '(汤力风味)',
        }
        if flavor in flavor_suffix_map:
            suffix = flavor_suffix_map[flavor]
            if suffix not in name:
                return f"{name}{suffix}"
        return name

    data['商品名称'] = data.apply(add_flavor_to_name, axis=1)

    # 做法名称处理
    data['温度'] = data['温度'].str.replace('（不可少冰）', '', regex=False)

    special_products = [
        '一大大大桶美式(1L装)',
        '一大大大桶超清爽椰子水(1L装)',
        '美式',
        '橙C气泡美式',
        '全冰小黄油风味美式',
        '一大大大桶椰青美式(1L装)',
        '奇异果葡萄气泡'
    ]
    mask = data['商品名称'].isin(special_products)
    data.loc[mask, '温度'] = '标准冰'
    data.loc[mask, '糖度'] = '不另外加糖'

    special_products2 = ['橙C茉莉茶', '葡萄气泡美式']
    mask = data['商品名称'].isin(special_products2)
    data.loc[mask, '温度'] = '标准冰'
    data.loc[mask, '糖度'] = '标准糖'

    mask = (data['商品名称'].isin(['芭乐白糯米酸奶','一大大大桶橙C气泡美式(1L装)','奇异果茉莉冰茶'])) & (data['做法'].isna() | (data['做法'] == ''))
    data.loc[mask, '温度'] = '标准冰'
    data.loc[mask, '糖度'] = '标准糖'

    mask = (data['商品名称'].isin(['奇异果茉莉冰茶'])) & (data['糖度'].isna() | (data['糖度'] == '未知'))
    data.loc[mask, '糖度'] = '不另外加糖'

    # 聚合数据
    data_cleaned = data.groupby(['日期', '大区', '督导', '门店编码', '门店名称', '商品名称', '温度', '糖度']).agg(
        商品售卖量=('商品销量', 'sum'),
    ).reset_index()

    # 读取BOM表
    data_bom = pd.read_excel(bom_path)

    # 合并销售数据和BOM表
    merged = data_cleaned.merge(
        data_bom,
        on=['商品名称', '温度', '糖度'],
        how='left',
        indicator='BOM匹配状态'
    )
    merged['物料消耗净料量'] = merged['商品售卖量'] * merged['净料量']
    
     # 检查商品名称及做法是否匹配
    unmatched_bom = merged[merged['BOM匹配状态'] == 'left_only'].copy()
    unmatched_bom.to_csv(r"C:\商品销售数据\过程文件（维护用）\商品名称及做法未匹配数据.csv", encoding='utf-8-sig', index=False)
    print("\n数据已保存到: 商品名称及做法未匹配数据.csv，需进一步核查")
    
    # 添加门店类型信息
    data_type = pd.read_excel("./DATA/门店类型信息.xlsx")
    data_type['门店编码'] = data_type['门店编码'].astype(str)
    data_type = data_type.drop_duplicates(subset=['门店编码', '门店名称'])

    # 合并门店类型信息到merged
    merged = merged.merge(
        data_type[['门店编码', '门店名称', '门店类型']], 
        on=['门店编码', '门店名称'],
        how='left',
        indicator='门店匹配状态'
    )
    # 检查门店类型是否匹配
    unmatched_store = merged[merged['门店匹配状态'] == 'left_only'].copy()
    if len(unmatched_store) > 0:
        print(f"门店类型未匹配数据：{len(unmatched_store)} 条")
        print("以下门店的类型信息未匹配，需维护门店类型信息表：")
        print(unmatched_store['门店名称'].unique())
    else:
        print("所有门店类型信息匹配成功")


    # 物料消耗聚合
    daily_material_consumption = merged.groupby([
        '日期',
        '大区',
        '督导',
        '门店类型',
        '门店编码',
        '门店名称',
        '品项编码',
        '品项名称',
        '品项规格',
        '消耗单位',
    ]).agg({
        '物料消耗净料量': 'sum'
    }).reset_index()
    
    # 转换日期类型
    daily_material_consumption['日期'] = pd.to_datetime(daily_material_consumption['日期'])

    #读取报货表
    data_order= pd.read_excel(order_path) 
    data_order = data_order.query("订单状态 not in ['已取消', '已驳回']")
    target_categories = ['果汁果酱', '乳制品', '茶叶', '咖啡制品','其他原料','糖浆','装饰食材','粉剂','其他','小料','原料折扣']
    data_order = data_order[data_order['品项类别'].isin(target_categories)]
    
    # 订货包替换
    pack_materials = [
        {'品项编码': 'WP3322', '品项名称': '璞悦·白糯米（方便米饭）300g', '规格': '300g*40盒/箱', '订货单位': '盒', '包内数量': 7},
        {'品项编码': 'WP3321', '品项名称': '红心芭乐果浆1kg', '规格': '1kg*12袋/箱', '订货单位': '袋', '包内数量': 2},
    ]
    order_codes = ['TJ00133']
    def expand_pack(row):
        if row.get('品项编码') in order_codes:
            # 获取订单的基本信息
            order_info = row.to_dict()
            pack_quantity = row.get('报货数量', 0)  # 包的订货数量
            
            # 展开为多个物料行
            expanded_rows = []
            for material in pack_materials:
                new_row = order_info.copy()
                # 更新物料信息
                new_row['品项编码'] = material['品项编码']
                new_row['品项名称'] = material['品项名称']
                new_row['规格'] = material['规格']
                new_row['订货单位'] = material['订货单位']
                new_row['报货数量'] = material['包内数量']* pack_quantity
                 # 添加标记字段方便追溯
                new_row['原订货包编码'] = row.get('品项编码')
                new_row['原订货包名称'] = row.get('品项名称')
                expanded_rows.append(new_row)
            
            return expanded_rows
        else:
            # 非订货包，直接返回原行
            row_dict = row.to_dict()
            row_dict['原订货包编码'] = ''
            row_dict['原订货包名称'] = ''
            return [row_dict]
            
    all_rows = []
    for _, row in data_order.iterrows():
        rows = expand_pack(row)
        all_rows.extend(rows)
    
    result_df = pd.DataFrame(all_rows)
    
    # 移除原始的订货包行（即品项编码在order_codes中的行）
    result_df = result_df[~result_df['品项编码'].isin(order_codes)]
    
    result_df = result_df.dropna(subset=['规格']) 
    
    #拆规格
    def split_spec(spec_str):
        # 将 * 替换为 /，统一分隔符，避免混合写法
        clean_str = str(spec_str).replace('*', '/')
        parts = clean_str.split('/')
        
        # 确保即使少了分割符也能补全列 (防止报错)
        while len(parts) < 3:
            parts.append('')
        return parts
    
    # 应用拆分函数并生成新列
    split_results = result_df['规格'].apply(split_spec)
    result_df['单规格'] = split_results.apply(lambda x: x[0])   # 例如：1L
    result_df['包装数量'] = split_results.apply(lambda x: x[1]) # 例如：12盒
    result_df['箱规'] = split_results.apply(lambda x: x[2])     # 例如：箱
    
    # 进一步拆分单规格及包装数量
    def split_qty_unit(qty_str):
        # 匹配数字和中文/英文单位
        match = re.match(r'([\d.]+)(\D*)', str(qty_str))
        if match:
            return match.group(1), match.group(2)
        return qty_str, ''
    
    result_df['数量_g_ml'] = result_df['单规格'].apply(lambda x: split_qty_unit(x)[0])
    result_df['数量_g_ml'] = pd.to_numeric(result_df['数量_g_ml'], errors='coerce').fillna(0)
    result_df['单位_g_ml'] = result_df['单规格'].apply(lambda x: split_qty_unit(x)[1])
    result_df['数量_盒_袋'] = result_df['包装数量'].apply(lambda x: split_qty_unit(x)[0])
    result_df['数量_盒_袋'] = pd.to_numeric(result_df['数量_盒_袋'], errors='coerce').fillna(1)
    result_df['单位_盒_袋'] = result_df['包装数量'].apply(lambda x: split_qty_unit(x)[1])

    # 统一转换为g/ml
    result_df['份数'] = np.where(
        result_df['订货单位'] == '箱', 
        result_df['报货数量'] * result_df['数量_盒_袋'], 
        result_df['报货数量']
    )
    result_df['订货量_临时'] = result_df['份数'] * result_df['数量_g_ml']
    
    def convert_to_minor_unit(row):
        qty = row['订货量_临时']
        unit = str(row['单位_g_ml']).strip().lower() # 转小写并去除首尾空格，防误判

        if unit in ['l', 'kg']:
            return qty * 1000
        else:
            return qty
    result_df['统一订货量'] = result_df.apply(convert_to_minor_unit, axis=1)
    
    #订货单位转换
    def get_final_unit(unit):
        unit = str(unit).strip().lower()
        if unit == 'l': return 'ml'
        if unit == 'kg': return 'g'
        if unit == ' ': return '只'  #糖葫芦山楂比较特殊
        return unit # 原本是 ml 或 g 则不变
    
    result_df['最终订货单位'] = result_df['单位_g_ml'].apply(get_final_unit)
    
    result_df['订货日期'] = result_df['创建时间'].astype(str).str.split(' ').str[0]
    result_df.rename(columns={
        '统一订货量': '订货量',
        '最终订货单位': '单位'
    }, inplace=True)
    
    #物料替换
    
    # 编码替换字典 (旧编码: 新编码)
    code_map = {
        'WP3323': 'WP0300', 
        'WP3075': 'WP0383', 
        'WP3227': 'WP0004', 
        'WP3108T': 'WP3108'
    }
    
    # 名称替换字典 (旧名称: 新名称)
    name_map = {
        '埃塞俄比亚古吉日晒250g': '耶加雪菲咖啡豆',
        '华桑厚椰乳1L': '厚椰乳',
        '味全常温奶1L': '纯牛奶',
        '小咖定制咸芝士牛乳含乳饮料1kg（特价款）': '小咖定制咸芝士牛乳含乳饮料1kg'
    }

    result_df['品项编码'] = result_df['品项编码'].replace(code_map)
    result_df['品项名称'] = result_df['品项名称'].replace(name_map)

    material_order = result_df.groupby([
    '订货日期', 
    '门店名称', 
    '品项编码', 
    '品项名称', 
    '单规格',
    '单位', 
    ]).agg({
        '订货量': 'sum'
    }).reset_index()
     
    # 执行聚合
    order_agg = material_order.groupby(
        ['门店名称', '品项编码', '品项名称', '单规格', '单位'],
    ).agg(
        总订货量=('订货量', 'sum')
    ).reset_index()

    # 计算消耗聚合（全量） ----------
    consumption_agg = daily_material_consumption.groupby(
        ['大区', '督导', '门店编码', '门店名称', '门店类型', '品项编码', '品项名称', '消耗单位']
    ).agg(
        总消耗量=('物料消耗净料量', 'sum')
    ).reset_index()

    # 添加上消耗天数（用于计算日均）
    consumption_days = daily_material_consumption.groupby(
        ['门店名称', '品项编码']
    )['日期'].nunique().reset_index().rename(columns={'日期': '消耗天数'})

    consumption_agg = consumption_agg.merge(consumption_days, on=['门店名称', '品项编码'], how='left')

    # 关联订货表和消耗表（全量关联）

    merged_oc = order_agg.merge(
        consumption_agg,
        on=['门店名称', '品项编码','品项名称'],
        how='outer'
    )

    # 填充缺失值
    merged_oc['总订货量'] = merged_oc['总订货量'].fillna(0)
    merged_oc['总消耗量'] = merged_oc['总消耗量'].fillna(0)
    merged_oc['消耗天数'] = merged_oc['消耗天数'].fillna(0)
    merged_oc['单位'] = merged_oc['单位'].fillna(merged_oc['消耗单位'])

    mask_only_order = (merged_oc['总消耗量'] == 0) & (merged_oc['总订货量'] > 0)
    missing_stores = merged_oc.loc[mask_only_order, '门店名称'].unique()
    store_subset = consumption_agg[consumption_agg['门店名称'].isin(missing_stores)]
    store_mapping = store_subset[['门店名称', '大区', '督导', '门店类型', '门店编码']].drop_duplicates('门店名称')

    # 用映射补全缺失记录
    for field in ['大区', '督导', '门店类型', '门店编码']:
        # 构建门店→属性的映射字典
        map_dict = store_mapping.set_index('门店名称')[field].to_dict()
        # 只对缺失的记录进行补全
        merged_oc.loc[mask_only_order, field] = merged_oc.loc[mask_only_order, '门店名称'].map(map_dict)
    
    # 剩余缺失值用空字符串填充
    for field in ['大区', '督导', '门店类型', '门店编码']:
        merged_oc[field] = merged_oc[field].fillna('未知')

    # ---------- 计算异常指标 ----------
    def calculate_anomaly_metrics(row):
        订货量 = row['总订货量']
        消耗量 = row['总消耗量']

        if 订货量 == 0 and 消耗量 > 0:
            消耗占比 = float('inf')
            异常类型 = '订货不足'  
            差异绝对量 = 消耗量
        elif 订货量 > 0 and 消耗量 == 0:
            消耗占比 = 0.0
            异常类型 = '过度订货' 
            差异绝对量 = 订货量
        elif 订货量 == 0 and 消耗量 == 0:
            消耗占比 = 1.0
            异常类型 = '正常'
            差异绝对量 = 0
        else:
            消耗占比 = 消耗量 / 订货量
            差异绝对量 = abs(订货量 - 消耗量)
            if 消耗占比 < 0.5:
                异常类型 = '过度订货'
            elif 消耗占比 <= 1.5: 
                异常类型 = '正常'
            else:
                异常类型 = '订货不足'

        return pd.Series({
            '消耗量/订货量': 消耗占比,
            '异常类型': 异常类型,
            '差异量绝对值': 差异绝对量
        })

    anomaly_metrics = merged_oc.apply(calculate_anomaly_metrics, axis=1)
    merged_oc = pd.concat([merged_oc, anomaly_metrics], axis=1)

    # # ---------- 计算门店级别指标 ----------
    # def calculate_store_metric(group):
    #     """计算门店级别指标，只返回异常门店"""
    #     异常物料 = group[group['异常类型'] != '正常']
    #     if len(异常物料) == 0:
    #         return None  # 正常门店不参与排名

    #     异常物料数 = len(异常物料)

    #     # 平均消耗占比（只算非无穷）
    #     finite = 异常物料[~np.isinf(异常物料['消耗占比'])]
    #     if len(finite) > 0:
    #         平均消耗占比 = finite['消耗占比'].mean()
    #     else:
    #         平均消耗占比 = 999  # 全是无穷大

    #     # 判断主要异常倾向
    #     over_count = len(异常物料[异常物料['异常类型'] == '过度订货'])
    #     under_count = len(异常物料[异常物料['异常类型'] == '订货不足'])
    #     主要异常类型 = '过度订货' if over_count >= under_count else '订货不足'

    #     # 最大差异物料
    #     top_item = 异常物料.sort_values('差异绝对量', ascending=False).iloc[0]

    #     return pd.Series({
    #         '异常物料数': 异常物料数,
    #         '平均消耗占比': round(平均消耗占比, 2) if 平均消耗占比 != 999 else 999,
    #         '主要异常类型': 主要异常类型,
    #         '最大差异物料': f'{top_item["品项名称"]} (差异{top_item["差异绝对量"]:,.0f})',
    #     })

    # # 按门店聚合（只保留异常门店，正常门店被自动过滤）
    # store_anomaly = merged_oc.groupby(
    #     ['大区', '督导', '门店编码', '门店名称', '门店类型']
    # ).apply(calculate_store_metric).reset_index()

    # # 分离过度订货和订货不足门店，各自排序
    # over_order_stores = store_anomaly[store_anomaly['主要异常类型'] == '过度订货'].copy()
    # under_order_stores = store_anomaly[store_anomaly['主要异常类型'] == '订货不足'].copy()

    # # 过度订货：按平均消耗占比升序（越低越严重排前面）
    # over_order_stores = over_order_stores.sort_values('平均消耗占比', ascending=True)

    # # 订货不足：按平均消耗占比降序（越高越严重排前面）
    # under_order_stores = under_order_stores.sort_values('平均消耗占比', ascending=False)

    # ---------- 计算品项总消耗量（用于下拉排序） ----------
    item_total_consumption = daily_material_consumption.groupby('品项名称')['物料消耗净料量'].sum().reset_index()
    item_total_consumption = item_total_consumption.rename(columns={'物料消耗净料量': '品项总消耗量'})
    item_total_consumption = item_total_consumption.sort_values('品项总消耗量', ascending=False)

    return daily_material_consumption, merged, data_cleaned, material_order, result_df, merged_oc, item_total_consumption
 

# ==================== 绘图函数 ====================
def build_trend_data(data, start_date, end_date):
    """构建按大区分线的消耗趋势数据（闭区间 [start_date, end_date]，单位换算为 L/kg）
    - start_date/end_date: datetime.date / pd.Timestamp / str 均可
    - 单日模式由调用方传入 (T-6, T)；区间模式传入 (S, E)——函数本身不感知模式
    - 返回: DataFrame（index=日期，columns=各大区），值为消耗量/1000；区间无数据返回空 DataFrame
    """
    # 统一转 Timestamp（st.date_input 返回 datetime.date，pandas 2.x 不能与 datetime64 直接比较）
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    window = data[(data['日期'] >= start_date) & (data['日期'] <= end_date)]
    if window.empty:
        return pd.DataFrame()

    # 按大区分列求和，换算单位（g→kg、ml→L），大区列固定排序；
    # 保留两位小数（悬浮提示即显示该精度）
    trend = window.pivot_table(
        index='日期', columns='大区', values='物料消耗净料量', aggfunc='sum'
    ).sort_index()
    trend = trend[sorted(trend.columns)] / 1000.0
    return trend.round(2)

def create_trend_chart(trend_df, region1, region2, title):
    """按大区分线的消耗趋势折线图（与 TOP7 图同尺寸 figsize=(13, 8.5)）
    - 颜色映射与 TOP7 堆叠条一致：region1 '#2D7A8A'、region2 '#5A919E'，其余大区 SERIES_COLORS 轮换
    - x 轴用 mdates 显式设置刻度（否则出现浮点日期刻度）
    - 每个数据点都标注数值（补偿 hover 丢失）
    """
    setup_chinese_font()
    setup_chart_style()

    fig, ax = plt.subplots(figsize=(13, 8.5))

    if trend_df.empty:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=14)
        ax.set_title(title, fontsize=16, weight='normal', pad=12)
        style_axes(ax)
        return fig

    # 与 TOP7 堆叠条同色映射：同一大区在两图中颜色一致
    top7_color_map = {region1: '#2D7A8A', region2: '#5A919E'}
    for i, region in enumerate(trend_df.columns):
        color = top7_color_map.get(region, SERIES_COLORS[i % len(SERIES_COLORS)])
        ax.plot(trend_df.index, trend_df[region], label=region,
                color=color, linewidth=2, marker='o', markersize=5)

    # x 轴刻度：≤14 天每日一格，否则按跨度约 12 格
    span_days = (trend_df.index[-1] - trend_df.index[0]).days + 1
    interval = 1 if span_days <= 14 else max(1, round(span_days / 12))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

    # 全点标注：每个数据点都标注数值
    for region, series in trend_df.items():
        s = series.dropna()
        if s.empty:
            continue
        for x, v in zip(s.index, s.values):
            ax.annotate(f'{v:.2f}', xy=(x, v), xytext=(4, 4),
                        textcoords='offset points', fontsize=9,
                        color=BRAND_COLORS['ink'], va='bottom', ha='left')

    ax.set_ylabel('消耗量 (L/kg)', fontsize=11, weight='normal')
    ax.legend(fontsize=11, loc='lower right', framealpha=0.95,
              edgecolor=BRAND_COLORS['gray_blue'], shadow=False)
    ax.grid(alpha=0.3, linestyle='--', linewidth=0.8)
    style_axes(ax)
    ax.margins(x=0.06, y=0.1)
    ax.set_title(title, fontsize=16, weight='normal', pad=12)

    plt.tight_layout()
    return fig

def create_top7_chart(data, start_date, end_date, region1, region2):
    """创建TOP7物料消耗图表
    - start_date == end_date: 单日模式 → 与现状一致（含日环比/周同比两行小字）
    - start_date <  end_date: 区间模式 → 区间聚合排序，仅显示区间总量，无环比/同比
    - 返回 matplotlib Figure 或 None（区间内无数据）
    """
    setup_chinese_font()
    setup_chart_style()

    # 统一转 Timestamp（st.date_input 返回 datetime.date，pandas 2.x 不能与 datetime64 直接比较）
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)
    is_single = (start_date == end_date)

    if is_single:
        window_data = data[data['日期'] == start_date]
    else:
        window_data = data[(data['日期'] >= start_date) & (data['日期'] <= end_date)]

    if window_data.empty:
        return None

    # 按大区和品项统计（单日=当日数据；区间=区间聚合总量）
    day_pivot = window_data.groupby(['大区', '品项名称'])['物料消耗净料量'].sum().reset_index()
    pivot_data = day_pivot.pivot(index='品项名称', columns='大区', values='物料消耗净料量').fillna(0)

    if region1 not in pivot_data.columns:
        pivot_data[region1] = 0
    if region2 not in pivot_data.columns:
        pivot_data[region2] = 0

    pivot_data['总计'] = pivot_data.sum(axis=1)
    top7_data = pivot_data.sort_values('总计', ascending=True).tail(7)
    top7_data = top7_data.drop('总计', axis=1)

    # 单位换算
    unit_mapping = window_data.groupby('品项名称')['消耗单位'].first().to_dict()

    def convert_unit(value, unit):
        if unit == 'ml':
            return value / 1000, 'L'
        elif unit == 'g':
            return value / 1000, 'kg'
        else:
            return value, unit

    top7_data_display = top7_data.copy()
    top7_data_display['显示单位'] = top7_data_display.index.map(lambda x: unit_mapping.get(x, ''))

    for region in [region1, region2]:
        top7_data_display[f'{region}_换算值'] = top7_data_display.apply(
            lambda row: convert_unit(row[region], row['显示单位'])[0], axis=1
        )

    top7_data_display['总计_换算值'] = top7_data_display[f'{region1}_换算值'] + top7_data_display[f'{region2}_换算值']
    top7_data_display['总计_换算单位'] = top7_data_display.apply(
        lambda row: convert_unit(row[region1], row['显示单位'])[1], axis=1
    )
    top7_data_display = top7_data_display.sort_values('总计_换算值', ascending=True)

    # 计算环比同比（仅单日模式；区间模式跳过，只显示总量）
    metrics = {}
    if is_single:
        def calculate_metrics(item_name):
            item_data = data[data['品项名称'] == item_name]
            if item_data.empty:
                return None, None

            today_val = item_data[item_data['日期'] == start_date]['物料消耗净料量'].sum()
            yesterday = start_date - pd.Timedelta(days=1)
            yesterday_val = item_data[item_data['日期'] == yesterday]['物料消耗净料量'].sum()
            last_week = start_date - pd.Timedelta(days=7)
            last_week_val = item_data[item_data['日期'] == last_week]['物料消耗净料量'].sum()

            day_ratio = ((today_val - yesterday_val) / yesterday_val * 100) if yesterday_val > 0 else (100 if today_val > 0 else 0)
            week_ratio = ((today_val - last_week_val) / last_week_val * 100) if last_week_val > 0 else (100 if today_val > 0 else 0)

            return day_ratio, week_ratio

        for item in top7_data_display.index:
            day_ratio, week_ratio = calculate_metrics(item)
            metrics[item] = {'日环比': day_ratio, '周同比': week_ratio}

    # 创建图表（并排布局，width='stretch' 撑满后与趋势图等高）
    fig, ax = plt.subplots(figsize=(13, 8.5))

    categories = top7_data_display.index.tolist()
    y = np.arange(len(categories))

    values1 = top7_data_display[f'{region1}_换算值'].values
    values2 = top7_data_display[f'{region2}_换算值'].values
    total_values = top7_data_display['总计_换算值'].values

    # 相近色堆叠：青蓝绿 + 中蓝绿（同族色系，浅色段配深色文字）
    TOP7_COLOR_1 = '#2D7A8A'   # 大区1（深）
    TOP7_COLOR_2 = '#5A919E'   # 大区2（浅）
    ax.barh(y, values1, label=f'{region1}', color=TOP7_COLOR_1, alpha=0.9, height=0.6)
    ax.barh(y, values2, left=values1, label=f'{region2}', color=TOP7_COLOR_2, alpha=0.9, height=0.6)

    max_val = max(total_values) if len(total_values) > 0 else 1

    for i, (idx, row) in enumerate(top7_data_display.iterrows()):
        r1_val = row[f'{region1}_换算值']
        r2_val = row[f'{region2}_换算值']
        total = row['总计_换算值']
        unit = row['总计_换算单位']

        if total > 0:
            if r1_val > total * 0.08 and r1_val > 0:
                ax.text(r1_val/2, i, f'{round(r1_val)}',
                       ha='center', va='center', fontsize=10, color='white', weight='normal')

            if r2_val > total * 0.08 and r2_val > 0:
                ax.text(r1_val + r2_val/2, i, f'{round(r2_val)}',
                       ha='center', va='center', fontsize=10, color=BRAND_COLORS['dark'], weight='normal')

            day_ratio = metrics.get(idx, {}).get('日环比', 0)
            week_ratio = metrics.get(idx, {}).get('周同比', 0)

            text_x = total + max_val * 0.01

            ax.text(text_x, i, f'{total:.2f}{unit}',
                   ha='left', va='center', fontsize=12, color=BRAND_COLORS['ink'], weight='normal')

            if is_single and day_ratio is not None and abs(day_ratio) < 999:
                day_color = STATUS_COLORS['up'] if day_ratio >= 0 else STATUS_COLORS['down']
                day_arrow = '↑' if day_ratio >= 0 else '↓'
                ax.text(text_x + max_val * 0.13, i - 0.11, f'日环比 {day_arrow}{abs(day_ratio):.2f}%',
                       ha='left', va='center', fontsize=9.5, color=day_color, weight='normal')

            if is_single and week_ratio is not None and abs(week_ratio) < 999:
                week_color = STATUS_COLORS['up'] if week_ratio >= 0 else STATUS_COLORS['down']
                week_arrow = '↑' if week_ratio >= 0 else '↓'
                ax.text(text_x + max_val * 0.13, i + 0.11, f'周同比 {week_arrow}{abs(week_ratio):.2f}%',
                       ha='left', va='center', fontsize=9.5, color=week_color, weight='normal')

    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=11, weight='normal')
    ax.set_xlabel('消耗量 (L/kg)', fontsize=11, weight='normal')
    ax.set_ylabel('品项名称', fontsize=11, weight='normal')
    if is_single:
        ax.set_title(f'{start_date.strftime("%Y-%m-%d")} TOP7 物料消耗情况',
                    fontsize=16, weight='normal', pad=12)
    else:
        ax.set_title(f'{start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")} TOP7 物料消耗情况',
                    fontsize=16, weight='normal', pad=12)

    ax.legend(fontsize=11, loc='upper right', framealpha=0.95,
              edgecolor=BRAND_COLORS['gray_blue'], shadow=False)
    ax.grid(axis='x', alpha=0.3, linestyle='--', linewidth=0.8)
    style_axes(ax)
    ax.set_xlim(0, max_val * (1.75 if is_single else 1.2))

    plt.tight_layout()
    return fig

def create_anomaly_pie(merged_oc, anom_type):
    """全国异常品项差异量分布（单张饼图，供 TAB 切换：订货不足/过度订货）
    - 切片 = 各品项差异量绝对值占比，取 TOP7，其余合并"其他"
    - 颜色渐变：差异量最大的 TOP1 颜色最深，依次变浅（HSL 亮度递增）；"其他"用灰
    - 图例单位按品项实际单位：ml→L、g→kg，其他/混合→L/KG
    """
    setup_chinese_font()
    setup_chart_style()

    title = '订货不足品项差异量分布' if anom_type == '订货不足' else '过度订货品项差异量分布'
    color = STATUS_COLORS['under'] if anom_type == '订货不足' else STATUS_COLORS['over']

    fig, ax = plt.subplots(figsize=(8, 4.3))

    data = merged_oc[merged_oc['异常类型'] == anom_type]
    if data.empty:
        ax.text(0.5, 0.5, '无数据', ha='center', va='center', fontsize=14)
        ax.set_title(f'全国{title}', fontsize=10, pad=10)
        return fig

    # 品项差异量聚合（g/ml 原单位），取 TOP7，其余合并"其他"
    item_diff = data.groupby('品项名称')['差异量绝对值'].sum().sort_values(ascending=False)
    top7 = item_diff.head(7)
    other_sum = item_diff.iloc[7:].sum()

    labels = list(top7.index)
    sizes = list(top7.values)
    if other_sum > 0:
        labels.append('其他')
        sizes.append(other_sum)

    # 品项→单位映射（用于图例单位换算）
    unit_map = merged_oc.groupby('品项名称')['单位'].first().to_dict()

    def fmt_diff(value, item):
        """按品项实际单位换算：ml→L、g→kg、其他→L/KG"""
        u = unit_map.get(item, '')
        if u == 'ml':
            return f'{value / 1000:,.2f} L'
        elif u == 'g':
            return f'{value / 1000:,.2f} kg'
        return f'{value / 1000:,.2f} L/kg'

    # 颜色渐变：TOP1（差异量最大）原始色最深，按排名 HSL 亮度递增变浅；"其他"用灰
    base = mcolors.to_rgb(color)
    h, l, s = colorsys.rgb_to_hls(*base)
    colors = [mcolors.to_hex(colorsys.hls_to_rgb(h, min(l + i * 0.055, 0.94), s))
              for i in range(len(sizes))]
    if other_sum > 0:
        colors[-1] = '#B0B7C4'
    explode = [0.05] + [0] * (len(sizes) - 1)

    wedges, texts, autotexts = ax.pie(
        sizes, labels=None, autopct='%1.1f%%',
        colors=colors, startangle=90,
        explode=explode,
        textprops={'fontsize': 11}
    )
    for autotext in autotexts:
        autotext.set_fontsize(10)

    # 图例：品项名 + 差异量（按品项单位换算）
    legend_labels = [f'{l} ({fmt_diff(s, l)})' for l, s in zip(labels, sizes)]
    ax.legend(wedges, legend_labels, loc='lower center', bbox_to_anchor=(0.5, -0.22),
              fontsize=9, ncol=2, frameon=False)
    ax.set_title(f'全国{title}', fontsize=10, pad=10)

    plt.tight_layout()
    return fig

def create_store_type_stack(merged_oc, item_name='全部'):
    """直营 vs 加盟 异常类型堆叠图（按品项筛选）
    - 粒度：门店×品项（merged_oc 行），按异常类型计数（正常/过度订货/订货不足）
    - 选具体品项时每家门店仅一行，统计的即是门店数 → 标注"门店数: N 家"；
      选"全部"时是门店×品项记录数 → 标注"记录数: N 条"
    - 空类型也画 0 柱保证两柱恒在；图例移到图上方，避免遮挡柱体
    """
    setup_chinese_font()
    setup_chart_style()

    if item_name != '全部':
        data = merged_oc[merged_oc['品项名称'] == item_name]
    else:
        data = merged_oc
    # 单位标注：单品项下计数即门店数
    count_unit = '家' if item_name != '全部' else '条'
    count_word = '门店数' if item_name != '全部' else '记录数'
    title_suffix = f'品项: {item_name}' if item_name != '全部' else '全国'

    fig, ax = plt.subplots(figsize=(8, 6.7))

    x_labels = ['直营', '加盟']
    bar_width = 0.45
    stack_totals = []

    for idx, stype in enumerate(x_labels):
        type_data = data[data['门店类型'] == stype]

        normal = len(type_data[type_data['异常类型'] == '正常'])
        over = len(type_data[type_data['异常类型'] == '过度订货'])
        under = len(type_data[type_data['异常类型'] == '订货不足'])
        total = normal + over + under
        stack_totals.append(total)

        # 堆叠柱状图：底部为正常，中间为过度订货，顶部为订货不足
        bottom_normal = 0
        ax.bar(idx, normal, bar_width, bottom=bottom_normal,
               label='正常' if idx == 0 else '', color=STATUS_COLORS['normal'], alpha=0.85)
        bottom_over = normal
        ax.bar(idx, over, bar_width, bottom=bottom_over,
               label='过度订货' if idx == 0 else '', color=STATUS_COLORS['over'], alpha=0.85)
        bottom_under = normal + over
        ax.bar(idx, under, bar_width, bottom=bottom_under,
               label='订货不足' if idx == 0 else '', color=STATUS_COLORS['under'], alpha=0.85)

        # 柱顶标注：单品项 → 门店数（家）；全部 → 门店×品项记录数（条）
        if total > 0:
            annotation = f'{count_word}: {total} {count_unit}'
            if over + under > 0:
                annotation += f'\n异常: {over+under} {count_unit}'
            ax.text(idx, total + max(total * 0.02, 2), annotation,
                    ha='center', va='bottom', fontsize=10, color=BRAND_COLORS['dark'])

    ax.set_xticks([0, 1])
    ax.set_xticklabels(x_labels, fontsize=12)
    ax.set_ylabel(f'{count_word}', fontsize=12)
    # 图例纵向（ncol=1）放绘图区右上角空白区，不遮挡堆叠条与标题
    ax.legend(fontsize=10, loc='upper right', ncol=1, frameon=False)
    ax.set_title(f'直营 vs 加盟 异常门店分布（{title_suffix}）', fontsize=15, pad=15)
    max_total = max(stack_totals) if stack_totals else 0
    # y 轴顶部留白：容纳柱顶两行标注 + 右上角图例
    ax.set_ylim(0, max_total * 1.72 if max_total > 0 else 1)

    plt.tight_layout()
    return fig

def create_store_rank_chart(merged_oc, region, item_name, chart_type, top_n=15):
    """创建门店排名的TOP15水平条形图
    - chart_type: '订货不足' → 按 (消耗量-订货量) 降序
                  '过度订货' → 按 (订货量-消耗量) 降序
    - item_name: '全部' 或具体品项名称
    """
    setup_chinese_font()
    setup_chart_style()

    # 筛选大区
    data = merged_oc[merged_oc['大区'] == region].copy()

    if data.empty:
        return None

    # 筛选品项
    if item_name != '全部':
        data = data[data['品项名称'] == item_name]

    # 按异常类型筛选
    data = data[data['异常类型'] == chart_type].copy()

    if data.empty:
        return None

    # 计算差值（÷1000 换算 g/ml → L/kg）
    if chart_type == '订货不足':
        data['差值'] = (data['总消耗量'] - data['总订货量']) / 1000
        color = STATUS_COLORS['under']
        title_prefix = '订货不足'
    else:
        data['差值'] = (data['总订货量'] - data['总消耗量']) / 1000
        color = STATUS_COLORS['over']
        title_prefix = '过度订货'

    # 按门店聚合差值
    store_diff = data.groupby(['门店名称', '门店类型'])['差值'].sum().reset_index()

    # 降序取TOP15
    store_diff = store_diff.sort_values('差值', ascending=False).head(top_n)

    if store_diff.empty:
        return None

    store_diff = store_diff.iloc[::-1]

    fig, ax = plt.subplots(figsize=(14, max(5, len(store_diff) * 0.5)))

    y_pos = np.arange(len(store_diff))
    values = store_diff['差值'].values
    store_names = store_diff['门店名称'].values
    store_types = store_diff['门店类型'].values

    # 统一颜色
    bars = ax.barh(y_pos, values, color=color, alpha=0.85, height=0.6)

    max_val = values.max() if len(values) > 0 else 1

    # 添加标签
    for i, (name, stype, v) in enumerate(zip(store_names, store_types, values)):
        # 在条末端显示：门店名称 | 门店类型 (差值 L/kg 两位小数)
        label = f'{name} | {stype} ({v:,.2f})'
        ax.text(v + max_val * 0.01, i, label, va='center', fontsize=11)

    # y轴显示排名
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f'#{len(store_diff) - i}' for i in range(len(store_diff))], fontsize=12)

    ax.set_xlabel('差异量 (L/kg)', fontsize=13)
    title_item = f' | 品项: {item_name}' if item_name != '全部' else ''
    ax.set_title(f'{region}{title_item} - {title_prefix}门店 TOP{min(top_n, len(store_diff))}',
                 fontsize=18, pad=15)

    ax.grid(axis='x', alpha=0.3, linestyle='--', linewidth=0.8)
    style_axes(ax)
    ax.set_xlim(0, max_val * 1.3)

    plt.tight_layout()
    return fig

# ==================== 主应用 ====================
def main():
    st.title("  门店物料消耗看板")

    # 注入品牌视觉风格（侧边栏/KPI卡片/分区标题/图表卡片）
    inject_css()

    # ==================== 数据加载状态 ====================
    # 检查数据文件是否存在
    sales_path = DATA_CONFIG['sales_path']
    bom_path = DATA_CONFIG['bom_path']
    order_path = DATA_CONFIG['order_path']

    if not os.path.exists(sales_path):
        st.error(f"❌ 销售数据文件不存在: {sales_path}")
        st.info("请将销售数据文件放置在正确的位置，或在 DATA_CONFIG 中更新文件路径")
        return

    if not os.path.exists(bom_path):
        st.error(f"❌ BOM表文件不存在: {bom_path}")
        st.info("请将BOM表文件放置在正确的位置，或在 DATA_CONFIG 中更新文件路径")
        return

    if not os.path.exists(order_path):
        st.error(f"❌ 订货数据文件不存在: {order_path}")
        st.info("请将订货数据文件放置在正确的位置，或在 DATA_CONFIG 中更新文件路径")
        return

    # 侧边栏 - 数据信息

    st.markdown("""
        <style>
            /* 固定侧边栏宽度 */
            section[data-testid="stSidebar"] {
                width: 200px !important; 
                min-width: 200px !important;
                max-width: 200px !important;
            }
            
            /* 调整主内容区域的左边距，避免被侧边栏遮挡 */
            section[data-testid="stSidebar"] ~ div {
                margin-left:20px !important;
            }
            
        </style>
    """, unsafe_allow_html=True)

    
    with st.sidebar:
        # 功能切换
        page = st.radio(
            "选择页面",
            options=[
                "物料消耗分析",
                "订货异常分析"
            ],
            index=0,
            key="page_nav"
        )
        
        st.markdown("---")
        if st.button("🔄 刷新数据", width='stretch', key="refresh_btn"):
            st.cache_data.clear()
            st.rerun()

    try:
        # 加载数据
        with st.spinner("正在加载和处理数据..."):
            daily_material_consumption, merged, data_cleaned, material_order, result_df, merged_oc, item_total_consumption = load_and_process_data(sales_path, bom_path,order_path)
            # region_list = sorted([r for r in merged_oc['大区'].unique() if r != '未知'])
            # item_options = ['全部'] + item_total_consumption['品项名称'].tolist()

        # 显示数据日期范围
        min_date = daily_material_consumption['日期'].min().to_pydatetime().date()
        max_date = daily_material_consumption['日期'].max().to_pydatetime().date()

        # ==================== 页面1: 物料消耗分析 ====================
        if page == "物料消耗分析":

            # 数据日期范围：小号青色文字（与标题左边线同色）
            st.markdown(
                f'<p style="font-size:0.95rem;color:{BRAND_COLORS["primary"]};'
                f'border-left:4px solid {BRAND_COLORS["primary"]};'
                f'padding-left:10px;margin:8px 0 4px 0;">'
                f'数据日期范围: {min_date} 至 {max_date}</p>',
                unsafe_allow_html=True
            )
            st.markdown("---")
            
            # 获取两个大区用于图表
            region_list = daily_material_consumption['大区'].unique()
            if len(region_list) >= 2:
                region1, region2 = region_list[0], region_list[1]
            else:
                region1, region2 = region_list[0], '其他'

            # ---------- 并排：消耗趋势 + TOP7 物料消耗（支持日期区间） ----------
            # 开始=结束为单日模式：趋势图回看近7日 + TOP7 含日环比/周同比
            # 开始≠结束为区间模式：两图均按区间展示，TOP7 仅显示区间总量
            chart_c1, chart_c2 = st.columns(2)
            with chart_c1:
                chart_start_date = st.date_input(
                    "📅 开始日期",
                    value=max_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="chart_start_date",
                    help="开始=结束为单日模式：趋势图展示该日期前7天，TOP7展示该日数据（含日环比/周同比）；"
                         "开始≠结束为区间模式：两图均按区间展示，TOP7仅显示区间总量"
                )
            with chart_c2:
                chart_end_date = st.date_input(
                    "📅 结束日期",
                    value=max_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="chart_end_date",
                    help="开始=结束为单日模式：趋势图展示该日期前7天，TOP7展示该日数据（含日环比/周同比）；"
                         "开始≠结束为区间模式：两图均按区间展示，TOP7仅显示区间总量"
                )

            if chart_start_date > chart_end_date:
                st.warning("⚠️ 图表开始日期不能晚于结束日期，已自动调整")
                chart_start_date, chart_end_date = chart_end_date, chart_start_date

            is_single = (chart_start_date == chart_end_date)
            trend_start = chart_start_date - timedelta(days=6) if is_single else chart_start_date

            if is_single:
                mode_text = "单日模式 · 趋势图近7日 + TOP7含日环比/周同比"
            else:
                mode_text = f"区间模式 · {chart_start_date} ~ {chart_end_date}"
            st.caption(mode_text)

            left_col, right_col = st.columns(2)

            with left_col:
                if is_single:
                    trend_title = "消耗趋势（近7日）"
                else:
                    trend_title = f"消耗趋势（{chart_start_date} ~ {chart_end_date}）"
                st.markdown(f"**{trend_title}**")
                with st.container(border=True):
                    trend_df = build_trend_data(daily_material_consumption, trend_start, chart_end_date)
                    if not trend_df.empty:
                        fig_trend = create_trend_chart(trend_df, region1, region2, trend_title)
                        st.pyplot(fig_trend, width='stretch')
                        plt.close(fig_trend)
                    else:
                        st.info("当前筛选下暂无趋势数据")

            with right_col:
                if is_single:
                    top7_title = "TOP7 物料消耗"
                else:
                    top7_title = f"TOP7 物料消耗（{chart_start_date} ~ {chart_end_date}）"
                st.markdown(f"**{top7_title}**")
                with st.container(border=True):
                    fig = create_top7_chart(daily_material_consumption, chart_start_date, chart_end_date, region1, region2)
                    if fig:
                        st.pyplot(fig, width='stretch')
                        plt.close(fig)
                    else:
                        if is_single:
                            warn_range = chart_start_date.strftime('%Y-%m-%d')
                        else:
                            warn_range = f"{chart_start_date} ~ {chart_end_date}"
                        st.warning(f"⚠️ {warn_range} 没有数据")
            
            # ---------- 分隔线 ----------
            st.markdown("---")
            
            # ---------- 明细表筛选器（多维度） ----------
            st.markdown("##  数据筛选与明细")
            
            # 创建筛选器布局
            col1, col2 = st.columns(2)
            
            with col1:
                start_date = st.date_input(
                    "📅 开始日期",
                    value=min_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="start_date"
                )
            
            with col2:
                end_date = st.date_input(
                    "📅 结束日期",
                    value=max_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="end_date"
                )
            
            # 第二行筛选器
            col3, col4, col5, col6, col7 = st.columns(5)
            
            with col3:
                regions = ['全部'] + sorted(daily_material_consumption['大区'].unique().tolist())
                selected_region = st.selectbox(
                    "大区",
                    regions,
                    key="region_filter"
                )
            
            with col4:
                mendian_type = ['全部'] + sorted(daily_material_consumption['门店类型'].unique().tolist())
                selected_mendian_type = st.selectbox(
                    "门店类型",
                    mendian_type,
                    key="mendian_type_filter"
                )
            with col5:
                supervisors = ['全部'] + sorted(daily_material_consumption['督导'].unique().tolist())
                selected_supervisor = st.selectbox(
                    "督导",
                    supervisors,
                    key="supervisor_filter"
                )
            
            with col6:
                mendian = ['全部'] + sorted(daily_material_consumption['门店名称'].unique().tolist())
                selected_mendian = st.selectbox(
                    "门店名称",
                    mendian,
                    key="mendian_filter"
                )
            
            with col7:
                items = ['全部'] + sorted(daily_material_consumption['品项名称'].unique().tolist())
                selected_item = st.selectbox(
                    "品项名称",
                    items,
                    key="item_filter"
                )
            
            # ---------- 数据筛选 ----------
            # 确保日期范围正确
            if start_date > end_date:
                st.warning("⚠️ 开始日期不能晚于结束日期，已自动调整")
                start_date, end_date = end_date, start_date
            
            start_date_ts = pd.Timestamp(start_date)
            end_date_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            
            filtered_data = daily_material_consumption[
                (daily_material_consumption['日期'] >= start_date_ts) &
                (daily_material_consumption['日期'] <= end_date_ts)
            ]
            
            if selected_region != '全部':
                filtered_data = filtered_data[filtered_data['大区'] == selected_region]
            
            if selected_mendian_type != '全部':
                filtered_data = filtered_data[filtered_data['门店类型'] == selected_mendian_type]
            
            if selected_supervisor != '全部':
                filtered_data = filtered_data[filtered_data['督导'] == selected_supervisor]
            
            if selected_mendian != '全部':
                filtered_data = filtered_data[filtered_data['门店名称'] == selected_mendian]
            
            if selected_item != '全部':
                filtered_data = filtered_data[filtered_data['品项名称'] == selected_item]

            # ---------- 汇总统计 ----------
            st.markdown("##  汇总")

            col1, col2, col3, col4 = st.columns(4)

            total_consumption = filtered_data['物料消耗净料量'].sum()
            total_stores = filtered_data['门店编码'].nunique()
            total_items = filtered_data['品项名称'].nunique()
            total_days = filtered_data['日期'].nunique()

            with col1:
                st.metric("总消耗量", f"{total_consumption:,.2f}")
            with col2:
                st.metric("门店数", total_stores)
            with col3:
                st.metric("品项数", total_items)
            with col4:
                st.metric("涉及天数", total_days)

            # ---------- 数据明细表 ----------
            st.markdown("###  门店物料消耗明细")
            
            # 选择显示的列
            display_columns = ['日期', '大区', '门店类型', '督导', '门店编码', '门店名称', '品项编码', '品项名称', '品项规格', '消耗单位', '物料消耗净料量']
            
            display_data = filtered_data[display_columns].copy()
            
            # 日期格式化
            display_data['日期'] = display_data['日期'].dt.strftime('%Y-%m-%d')
            
            # 显示数据行数
            st.info(f"共 {len(display_data)} 条记录")

            # 显示数据
            st.dataframe(
                display_data,
                use_container_width=True,
                height=400,
                column_config={
                    "物料消耗净料量": st.column_config.NumberColumn(
                        "物料消耗净料量",
                        format="%.2f"
                    )
                }
            )
            
            # ---------- 下载按钮 ----------
            col1, col2 = st.columns(2)
            
            with col1:
                # 下载筛选后的数据
                csv = display_data.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下载筛选数据 (CSV)",
                    data=csv,
                    file_name=f"物料消耗明细_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # 下载完整数据（按日期分组）
                all_data = daily_material_consumption.copy()
                all_data['日期'] = all_data['日期'].dt.strftime('%Y-%m-%d')
                all_csv = all_data[display_columns].to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下载全部数据 (CSV)",
                    data=all_csv,
                    file_name=f"全部物料消耗明细.csv",
                    mime="text/csv"
                )
        
        # ==================== 页面2: 订货异常分析 ====================
        else:
            st.markdown(
                f'<p style="font-size:0.95rem;color:{BRAND_COLORS["primary"]};'
                f'border-left:4px solid {BRAND_COLORS["primary"]};'
                f'padding-left:10px;margin:8px 0 4px 0;">'
                f'数据说明：7月份销售数据 & 7月份订货数据',
                unsafe_allow_html=True)
            
            st.markdown(
                f'<p style="font-size:0.95rem;color:{BRAND_COLORS["primary"]};'
                f'border-left:4px solid {BRAND_COLORS["primary"]};'
                f'padding-left:10px;margin:8px 0 4px 0;">'
                f'口径说明：消耗量/订货量 < 0.5 : 订货不足； 消耗量/订货量 > 1.5 : 过度订货； 仅有订货数据无销售数据的门店标记为未开业，不参与订货异常分析',
                unsafe_allow_html=True)
            
            st.markdown("---")
            
            
            # 品项下拉选项（按总消耗量降序）
            item_options = item_total_consumption['品项名称'].tolist()

            # 门店编码未知 = 未开业门店（只有订货数据、无销售数据），不参与异常分析：
            # 饼图/堆叠图/TOP排行排除；明细表保留记录，异常类型标记为"未开业"
            merged_oc_view = merged_oc.copy()
            unknown_mask = merged_oc_view['门店编码'].astype(str).str.strip() == '未知'
            merged_oc_view['异常类型'] = np.where(unknown_mask, '未开业', merged_oc_view['异常类型'])
            merged_oc_analysis = merged_oc_view[merged_oc_view['异常类型'] != '未开业']

            # ---------- 异常分布图表（左：差异量饼图 TAB 切换；右：直营vs加盟堆叠） ----------
            col_dist, col_stack = st.columns(2) 

            with col_dist:
                # 差异量分布：TAB 切换（订货不足在前，过度订货在后）
                tab_under, tab_over = st.tabs([" 订货不足", " 过度订货"])
                with tab_under:
                    fig_under = create_anomaly_pie(merged_oc_analysis, '订货不足')
                    if fig_under:
                        st.pyplot(fig_under, width='stretch')
                        plt.close(fig_under)
                with tab_over:
                    fig_over = create_anomaly_pie(merged_oc_analysis, '过度订货')
                    if fig_over:
                        st.pyplot(fig_over, width='stretch')
                        plt.close(fig_over)

            with col_stack:
                # 直营 vs 加盟 异常类型堆叠（品项筛选；单品项下每家门店一行，统计的即门店数）
                sel_stack_item = st.selectbox(
                    "选择品项查看直营/加盟分布",
                    item_options,
                    key="stack_item"
                )
                fig_stack = create_store_type_stack(merged_oc_analysis, sel_stack_item)
                if fig_stack:
                    st.pyplot(fig_stack, use_container_width=True)
                    plt.close(fig_stack)
            
            # ---------- 异常门店TOP排行 ----------
            st.markdown("---")
            st.markdown("##  异常门店TOP排行")
            
            # 获取大区列表
            region_list = sorted([r for r in merged_oc_analysis['大区'].unique() if r != '未知'])
            
            # 订货不足Tab在前，过度订货在后
            tab1, tab2 = st.tabs([" 订货不足门店TOP", " 过度订货门店TOP"])
            
            with tab1:
                st.markdown("**按 (消耗量-订货量) 降序排列**")
                col_left, col_right = st.columns([1, 2])
                with col_left:
                    sel_region_under = st.selectbox("选择大区", region_list, key="under_region")
                with col_right:
                    sel_item_under = st.selectbox("选择品项", item_options, key="under_item")
                
                fig_under = create_store_rank_chart(
                    merged_oc_analysis, sel_region_under, sel_item_under, '订货不足', top_n=15
                )
                if fig_under:
                    st.pyplot(fig_under)
                    plt.close(fig_under)
                else:
                    st.info(f"✅ {sel_region_under} 暂无订货不足门店")
            
            with tab2:
                st.markdown("**按 (订货量-消耗量) 降序排列**")
                col_left, col_right = st.columns([1, 2])
                with col_left:
                    sel_region_over = st.selectbox("选择大区", region_list, key="over_region")
                with col_right:
                    sel_item_over = st.selectbox("选择物料品项", item_options, key="over_item")
                
                fig_over = create_store_rank_chart(
                    merged_oc_analysis, sel_region_over, sel_item_over, '过度订货', top_n=15
                )
                if fig_over:
                    st.pyplot(fig_over)
                    plt.close(fig_over)
                else:
                    st.info(f"✅ {sel_region_over} 暂无过度订货门店")
            
            # ---------- 异常明细筛选器 ----------
            st.markdown("---")
            st.markdown("##  异常明细")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                regions = ['全部'] + region_list
                sel_region = st.selectbox("大区", regions, key="detail_region")
            
            with col2:
                if sel_region != '全部':
                    sup_list = ['全部'] + sorted(merged_oc_view[merged_oc_view['大区'] == sel_region]['督导'].unique())
                else:
                    sup_list = ['全部'] + sorted(merged_oc_view['督导'].unique())
                sel_supervisor = st.selectbox("督导", sup_list, key="detail_supervisor")
            
            with col3:
                store_types_filter = ['全部', '直营', '加盟']
                sel_type = st.selectbox("门店类型", store_types_filter, key="detail_type")
            
            with col4:
                anom_types = ['全部', '过度订货', '正常', '订货不足', '未开业']
                sel_anom_type = st.selectbox("异常类型", anom_types, key="detail_anom_type")
            
            col1, col2 = st.columns(2)
            
            with col1:
                stores = ['全部'] + sorted(merged_oc_view['门店名称'].unique())
                sel_store = st.selectbox("门店名称", stores, key="detail_store")
            
            with col2:
                # 品项按总消耗量降序
                detail_item_options = ['全部'] + item_total_consumption['品项名称'].tolist()
                sel_item = st.selectbox("品项名称", detail_item_options, key="detail_item")
            
            # 应用筛选（明细保留"未开业"标记记录）
            filtered = merged_oc_view.copy()
            
            if sel_region != '全部':
                filtered = filtered[filtered['大区'] == sel_region]
            if sel_supervisor != '全部':
                filtered = filtered[filtered['督导'] == sel_supervisor]
            if sel_type != '全部':
                filtered = filtered[filtered['门店类型'] == sel_type]
            if sel_anom_type != '全部':
                filtered = filtered[filtered['异常类型'] == sel_anom_type]
            if sel_store != '全部':
                filtered = filtered[filtered['门店名称'] == sel_store]
            if sel_item != '全部':
                filtered = filtered[filtered['品项名称'] == sel_item]
            
            # 显示明细表
            display_cols = ['大区', '督导', '门店编码', '门店名称', '门店类型',
                            '品项编码', '品项名称','单位',
                            '总订货量', '总消耗量', '消耗量/订货量', '异常类型', '差异量绝对值']
            
            display_data = filtered[display_cols].copy()
            display_data['消耗量/订货量'] = display_data['消耗量/订货量'].apply(
                lambda x: '∞' if np.isinf(x) else round(x, 2)
            )
            
            st.dataframe(
                display_data,
                use_container_width=True,
                height=500,
                column_config={
                    '总订货量': st.column_config.NumberColumn(format="%.0f"),
                    '总消耗量': st.column_config.NumberColumn(format="%.0f"),
                    '差异量绝对值': st.column_config.NumberColumn(format="%.0f"),
                }
            )
            
            csv = display_data.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 下载筛选数据 (CSV)",
                data=csv,
                file_name=f"订货消耗异常明细.csv",
                mime="text/csv",
                width='content'
            )
            
    except Exception as e:
        st.error(f"❌ 数据加载失败: {str(e)}")
        st.info("请检查数据文件路径和格式是否正确")
        st.stop()
       

if __name__ == "__main__":
    main()
