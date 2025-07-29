import json
import pandas as pd
from tabulate import tabulate
from course_utils import get_or_build_dept_info, try_schedule

def main():
    """
    主執行函式：讀取設定、透過快取抓取資料、排課並印出結果。
    """
    # 讀取設定檔
    with open("schedule_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    priority_dept = config.get("priority_dept")
    selected_courses = config.get("selected_courses", [])
    class_urls_file = config.get("class_urls_file", "class_urls_1.json")

    # 讀取班級網址
    with open(class_urls_file, "r", encoding="utf-8") as f:
        class_urls = json.load(f)

    # 透過快取機制取得課程資料
    dept_info = get_or_build_dept_info(class_urls, priority_dept=priority_dept)

    # 初始化課表
    cols = ['一', '二', '三', '四', '五']
    periods = list(range(1, 12)) + ["NoTime"]
    schedule = pd.DataFrame('-', index=periods, columns=cols)
    occupied = {}

    # 根據設定檔中的清單進行排課
    print("\n開始排課...")
    for name in selected_courses:
        try_schedule(name, dept_info, schedule, occupied, verbose=True)
    
    print("\n===== 最終排課結果 =====")
    print(tabulate(schedule, headers="keys", showindex=True, tablefmt="grid"))

if __name__ == "__main__":
    main()
