import requests
import pandas as pd
from io import StringIO
import urllib3
from tabulate import tabulate
import json

# 關閉 SSL 警告
urllib3.disable_warnings()

# 映射表
DAY_MAP = {'日':None,'一':'1','二':'2','三':'3','四':'4','五':'5','六':None}
PERIOD_MAP = {str(i): str(i) for i in range(1, 10)}
PERIOD_MAP.update({'10':'a', '11':'b'})

# 反轉 day_map 用於 pd.DataFrame 欄位
DAY_NUM_TO_COL = {v:k for k,v in DAY_MAP.items() if v}

def sort_key(code):
    """將上課時間（例： '1a'、'23'）轉成可比大小的整數。
    例： '1a' -> 101, '23' -> 203
    """
    d, p = int(code[0]), code[1]
    idx = int(p) if p.isdigit() else (10 if p=='a' else 11)
    return d * 100 + idx

# 必選修符號對照表
SYMBOL_MAP = {
    '○': {'req': '必修', 'detail': '部訂共同必修'},
    '△': {'req': '必修', 'detail': '校訂共同必修'},
    '☆': {'req': '選修', 'detail': '共同選修'},
    '●': {'req': '必修', 'detail': '部訂專業必修'},
    '▲': {'req': '必修', 'detail': '校訂專業必修'},
    '★': {'req': '選修', 'detail': '專業選修'},
}

def fetch_course_map(url):
    """
    input: 班級或系所頁面 URL
    return: (label, course_map)
      label: 從 DataFrame MultiIndex 第一層取得（如「光電一」「資工四」…）
      course_map: {
        '課程名稱': {
           '課號': ..., '教師': ..., 
           'symbol': '▲', 'req': '必修', 'detail': '校訂專業必修',
           'time_codes': [...]
        }
      }
    """
    # 取得頁面
    resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, verify=False)
    resp.encoding = "utf-8"
    html = resp.text

    # 用 pandas 讀出兩層 header
    try:
        df_raw = pd.read_html(StringIO(html), header=[0,1])[0]
    except ValueError:
        return None, {}

    # 從 MultiIndex 的第一層抓出 label
    label = df_raw.columns.get_level_values(0)[0].strip()

    # 第二層 header
    df = df_raw.copy()
    df.columns = df_raw.columns.get_level_values(1)
    df = df[df['課號'].notna() & (df['課號']!='小計')].reset_index(drop=True)

    # 分析課程info
    course_map = {}
    for _, row in df.iterrows():
        name   = row['課程名稱']
        sn     = str(row['修']).strip()  # ○△☆●▲★
        info   = SYMBOL_MAP.get(sn, {'req':None,'detail':None})

        # 處理時間碼
        codes = []
        for day, dnum in DAY_MAP.items():
            raw = row.get(day, "")
            if pd.notna(raw):
                for p in str(raw).split():
                    t = PERIOD_MAP.get(p)
                    if dnum and t:
                        codes.append(f"{dnum}{t}")
        codes = sorted(codes, key=sort_key)

        course_map[name] = {
            '課號':       row['課號'],
            '教師':       row['教師'],
            'symbol':     sn,
            'req':        info['req'],
            'detail':     info['detail'],
            'time_codes': codes
        }

    return label, course_map

def build_dept_info(class_urls, priority_dept=None):
    """    
    Arguments:
      class_urls: dict
        {
          "資工系": { "資工一": url1, "資工二": url2, … },
          "電機系": { … },
          …
        }
      priority_dept: str or None，例如 "資工系"。若不則為 None，
        先讀該科系，再讀其他科系。

    Returns:
      dept_info: list of (class_label, course_map)
    """
    dept_info = []

    # 1. 先處理 priority_dept
    if priority_dept and priority_dept in class_urls:
        for class_label, url in class_urls[priority_dept].items():
            print(f"正在讀取（優先）：{class_label}（{url}）")
            _, cmap = fetch_course_map(url)
            dept_info.append((class_label, cmap))

    # 2. 處理其他科系
    for dept, cls_dict in class_urls.items():
        if dept == priority_dept:
            continue
        for class_label, url in cls_dict.items():
            print(f"正在讀取：{class_label}（{url}）")
            _, cmap = fetch_course_map(url)
            dept_info.append((class_label, cmap))

    return dept_info

def course_filter(dept_name, course_name, course_info):
    if "資工" in dept_name:
        return True
    elif course_name in ["電子學(一)",
                         "電子學(二)",
                         "電路學(一)",
                         "電路學(二)",
                         "線性代數",
                         "機率",
                         "數位邏輯設計",
                         "微積分",
                         "離散數學",
                         "物理",
                         "專業英文",
                         "體育"]:
        return True
    else:
        return False


def try_schedule(name, dept_info, schedule, occupied, verbose=False):
    """
    name: 課程名稱
    dept_info: list of (label, course_map)
    """
    for label, cmap in dept_info:
        info = cmap.get(name)
        if not info:
            continue
        
        # filter rules 
        if not course_filter(label, name, info):
            if verbose:
                print(f"🚫 『{name}』在『{label}』不符合過濾規則，跳過")
            continue
        
        if not info['time_codes']:
            if verbose:
                print(f"ℹ️ 『{name}』在『{label}』沒有固定上課時間")
            prev = schedule.at["NoTime", "一"]
            new = f"{name}({label})"
            schedule.at["NoTime", "一"] = (prev + "；" + new) if prev else new
            occupied[name] = name
            return True

        # 衝堂檢查
        conflict = next((c for c in info['time_codes'] if c in occupied), None)
        if conflict:
            if verbose:
                print(f"⚠️『{name}』與『{occupied[conflict]}』衝堂於 {conflict}，跳過 {label}")
            continue

        # 無衝堂則排課
        for code in info['time_codes']:
            d, p = code[0], code[1]
            idx = int(p) if p.isdigit() else (10 if p=='a' else 11)
            col = DAY_NUM_TO_COL[d]
            schedule.at[idx, col] = f"{name}({label})"
            occupied[code] = name
        if verbose:
            print(f"✅ 已在『{label}』排入：{name}")
        return True

    if verbose:
        print(f"❌ 無法排入：{name}")
    return False

if __name__ == "__main__":
    with open("class_urls_1.json", "r", encoding="utf-8") as f:
        class_urls = json.load(f)

    dept_info = build_dept_info(class_urls, priority_dept="資工系")

    # initialize schedule
    cols     = ['一','二','三','四','五']
    periods  = list(range(1,12)) + ["NoTime"]
    schedule = pd.DataFrame('', index=periods, columns=cols)
    occupied = {}

    # 選課 piority
    selected = [
        "離散數學",
        "資料結構",
        "數位邏輯設計",
        "計算機概論",
        "物件導向程式設計",
        "計算機網路",
        "專業英文",
        "Android應用程式開發",
        "網頁程式設計",
        "體育"
    ]

    # 排課
    for name in selected:
        try_schedule(name, dept_info, schedule, occupied, verbose=True)

    print("\n===== 最終排課表 =====")
    clean = schedule.replace('', '-')  # 空值換成 '-'
    print(tabulate(clean, headers="keys", showindex=True, tablefmt="grid"))



