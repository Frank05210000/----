import requests
import pandas as pd
from io import StringIO
import urllib3

# 關閉 SSL 警告
urllib3.disable_warnings()

# 映射表
DAY_MAP = {'日':None,'一':'1','二':'2','三':'3','四':'4','五':'5','六':None}
PERIOD_MAP = {str(i): str(i) for i in range(1, 10)}
PERIOD_MAP.update({'10':'a', '11':'b'})
DAY_NUM_TO_COL = {v:k for k,v in DAY_MAP.items() if v}

SYMBOL_MAP = {
    '○': {'req': '必修', 'detail': '部訂共同必修'},
    '△': {'req': '必修', 'detail': '校訂共同必修'},
    '☆': {'req': '選修', 'detail': '共同選修'},
    '●': {'req': '必修', 'detail': '部訂專業必修'},
    '▲': {'req': '必修', 'detail': '校訂專業必修'},
    '★': {'req': '選修', 'detail': '專業選修'},
}

def sort_key(code):
    d, p = int(code[0]), code[1]
    idx = int(p) if p.isdigit() else (10 if p=='a' else 11)
    return d * 100 + idx

def fetch_course_map(url):
    resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, verify=False)
    resp.encoding = "utf-8"
    html = resp.text
    try:
        df_raw = pd.read_html(StringIO(html), header=[0,1])[0]
    except ValueError:
        return None, {}
    label = df_raw.columns.get_level_values(0)[0].strip()
    df = df_raw.copy()
    df.columns = df_raw.columns.get_level_values(1)
    df = df[df['課號'].notna() & (df['課號']!='小計')].reset_index(drop=True)
    course_map = {}
    for _, row in df.iterrows():
        name = row['課程名稱']
        sn = str(row['修']).strip()
        info = SYMBOL_MAP.get(sn, {'req':None,'detail':None})
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
            '課號': row['課號'],
            '教師': row['教師'],
            'symbol': sn,
            'req': info['req'],
            'detail': info['detail'],
            'time_codes': codes
        }
    return label, course_map

def build_dept_info(class_urls, priority_dept=None):
    dept_info = []
    if priority_dept and priority_dept in class_urls:
        for class_label, url in class_urls[priority_dept].items():
            print(f"正在讀取（優先）：{class_label}（{url}）")
            _, cmap = fetch_course_map(url)
            dept_info.append((class_label, cmap))
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
    elif course_name in [
        "電子學(一)", "電子學(二)", "電路學(一)", "電路學(二)",
        "線性代數", "機率", "數位邏輯設計", "微積分", "離散數學",
        "物理", "專業英文", "體育"]:
        return True
    return False

def try_schedule(name, dept_info, schedule, occupied, verbose=False):
    for label, cmap in dept_info:
        info = cmap.get(name)
        if not info:
            continue
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
        conflict = next((c for c in info['time_codes'] if c in occupied), None)
        if conflict:
            if verbose:
                print(f"⚠️『{name}』與『{occupied[conflict]}』衝堂於 {conflict}，跳過 {label}")
            continue
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
