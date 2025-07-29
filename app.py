from flask import Flask, render_template, request
import pandas as pd
import json
from course_utils import build_dept_info, try_schedule

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    # 預設課程列表
    selected = [
        "離散數學", "資料結構", "數位邏輯設計", "計算機概論",
        "物件導向程式設計", "計算機網路", "專業英文",
        "Android應用程式開發", "網頁程式設計", "體育"
    ]

    timetable_html = ''

    if request.method == 'POST':
        priority_dept = request.form.get('priority_dept', '資工系')
        selected_courses = request.form.getlist('selected')

        # 讀取班級網址 JSON
        with open("class_urls_1.json", "r", encoding="utf-8") as f:
            class_urls = json.load(f)

        # 產生部門資訊
        dept_info = build_dept_info(class_urls, priority_dept=priority_dept)

        # 初始化空排程表
        cols    = ['一','二','三','四','五']
        periods = list(range(1,12)) + ["NoTime"]
        schedule = pd.DataFrame('', index=periods, columns=cols)
        occupied = {}

        # 執行排課
        for name in selected_courses:
            try_schedule(name, dept_info, schedule, occupied, verbose=False)

        # 轉成彩色格子 HTML
        blocks = []
        blocks.append("<div class='timetable'>")
        # 標題列
        blocks.append("<div></div>" + ''.join(f"<div class='head'>{d}</div>" for d in cols))
        for i, row in schedule.iterrows():
            blocks.append(f"<div class='time'>{i}</div>")
            for d in cols:
                val = row[d]
                if not val:
                    blocks.append("<div></div>")
                else:
                    # 根據課程名稱套用 class
                    cls = 'course-def'
                    if '體育' in val:
                        cls = 'course-pe'
                    elif '英文' in val:
                        cls = 'course-eng'
                    elif 'AI' in val or '智慧' in val:
                        cls = 'course-ai'
                    elif 'ESG' in val:
                        cls = 'course-esg'
                    elif '工作' in val:
                        cls = 'course-work'
                    elif '國語' in val:
                        cls = 'course-ch'
                    elif '法' in val:
                        cls = 'course-law'
                    blocks.append(f"<div class='{cls}'>{val}</div>")
        blocks.append("</div>")
        timetable_html = ''.join(blocks)

    # 傳遞給模板
    return render_template('index.html', selected=selected, timetable=timetable_html)

if __name__ == '__main__':
    app.run(debug=True)