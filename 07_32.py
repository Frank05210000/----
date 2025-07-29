import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
import urllib3
from tabulate import tabulate
import json

# 關閉 SSL 警告
urllib3.disable_warnings()

# 映射表
DAY_MAP = {'日':None,'一':'1','二':'2','三':'3','四':'4','五':'5','六':None}
PERIOD_MAP = {str(i): str(i) for i in range(1, 10)}
PERIOD_MAP.update({'10':'a', '11':'b'})  # 若有更多，可再加 {'12':'c'}

# 反轉 day_map 用於 DataFrame 欄位
DAY_NUM_TO_COL = {v:k for k,v in DAY_MAP.items() if v}

def sort_key(code):
    """把時間碼（如 '1a'、'23'）轉成可比大小的整數。"""
    d, p = int(code[0]), code[1]
    idx = int(p) if p.isdigit() else (10 if p=='a' else 11)
    return d * 100 + idx

# 新增：必選修符號對照
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
    input:「班級頁面」或「科系頁面」URL。
    return: (label, course_map)
    course_map: {
      '課程名稱': {
         '課號': .., '教師': .., 'time_codes': [..],
         'symbol': '▲', 'req': '必修', 'detail': '校訂專業必修'
      }
    }
    """
    resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, verify=False)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    # 取標題最後的「-- XXX」或「　XXX」
    header = soup.find("h2").get_text()
    label = header.split("--")[-1].strip()

    # 把 HTML 投給 pandas 讀取表格
    try:
        df = pd.read_html(StringIO(resp.text), header=[0,1])[0]
    except ValueError:
        return label, {}

    # 保留第二層 header
    df.columns = df.columns.get_level_values(1)
    # 過濾無課號、小計
    df = df[df['課號'].notna() & (df['課號']!='小計')].reset_index(drop=True)

    # 解析時間碼與符號
    course_map = {}
    for _, row in df.iterrows():
        name    = row['課程名稱']
        symbol  = str(row['修']).strip()  # ○、△、☆、●、▲、★
        info    = SYMBOL_MAP.get(symbol, {'req': None, 'detail': None})
        codes   = []
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
            'symbol':     symbol,
            'req':        info['req'],     # '必修' or '選修'
            'detail':     info['detail'],  # e.g. '校訂專業必修'
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

    # 1. 先處理 priority_dept（若有指定）
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
    elif course_name in ["電子學(一)","電子學(二)","電路學(一)","電路學(二)","線性代數","機率","數位邏輯設計","微積分","離散數學"]:
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

        if not info['time_codes']:
            if verbose:
                print(f"ℹ️ 『{name}』在『{label}』沒有固定上課時間")
            prev = schedule.at["NoTime", "一"]
            new = f"{name}({label})"
            schedule.at["NoTime", "一"] = (prev + "；" + new) if prev else new
            occupied[name] = name
            return True
        
        # filter rules 
        if not course_filter(label, name, info):
            if verbose:
                print(f"🚫 『{name}』在『{label}』不符合過濾規則，跳過")
            continue

        # 衝堂檢查
        conflict = next((c for c in info['time_codes'] if c in occupied), None)
        if conflict:
            if verbose:
                print(f"⚠️『{name}』與『{occupied[conflict]}』衝堂於 {conflict}，跳過 {label}")
            continue

        # 無衝堂就排
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
    with open("class_urls_2.json", "r", encoding="utf-8") as f:
        class_urls = json.load(f)

    dept_info = build_dept_info(class_urls, priority_dept="資工系")

    # initialize schedule
    cols     = ['一','二','三','四','五']
    periods  = list(range(1,12)) + ["NoTime"]
    schedule = pd.DataFrame('', index=periods, columns=cols)
    occupied = {}

    # 選課 piority
    selected = [
        "微積分",
        "作業系統",
        "實務專題(二)",
        "機率",
        "iOS 應用程式開發",
        "自然語言處理與文件探勘",
        "駭客攻防概論",
        "生成式人工智慧導論"
    ]

# 5. 排課
for name in selected:
    try_schedule(name, dept_info, schedule, occupied, verbose=True)

print("\n===== 最終排課表 =====")
clean = schedule.replace('', '-')  # 空值換成 '-'
print(tabulate(clean, headers="keys", showindex=True, tablefmt="grid"))



