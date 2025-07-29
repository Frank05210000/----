from flask import Flask, render_template, request
import pandas as pd
import json
from course_utils import get_or_build_dept_info, try_schedule

app = Flask(__name__)

# 載入預設課程設定
with open("schedule_config.json", "r", encoding="utf-8") as f:
    DEFAULT_CONFIG = json.load(f)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        priority_dept = request.form.get('priority_dept', DEFAULT_CONFIG['priority_dept'])
        selected_courses_str = request.form.get('selected_courses', "")
        selected_courses = [course.strip() for course in selected_courses_str.split('\n') if course.strip()]
        class_urls_file = request.form.get('class_urls_file', DEFAULT_CONFIG['class_urls_file'])
    else:
        priority_dept = DEFAULT_CONFIG['priority_dept']
        selected_courses = DEFAULT_CONFIG['selected_courses']
        class_urls_file = DEFAULT_CONFIG['class_urls_file']

    # 讀取班級網址 JSON
    with open(class_urls_file, "r", encoding="utf-8") as f:
        class_urls = json.load(f)

    # 透過快取機制取得課程資料
    dept_info = get_or_build_dept_info(class_urls, priority_dept=priority_dept)

    # 初始化空排程表
    cols = ['一', '二', '三', '四', '五']
    periods = list(range(1, 12)) + ["NoTime"]
    schedule = pd.DataFrame('', index=periods, columns=cols)
    occupied = {}

    # 執行排課
    for name in selected_courses:
        try_schedule(name, dept_info, schedule, occupied, verbose=False)

    # 將 DataFrame 傳遞給模板
    return render_template(
        'index.html', 
        schedule=schedule, 
        selected_courses="\n".join(selected_courses),
        priority_dept=priority_dept,
        class_urls_file=class_urls_file
    )

if __name__ == '__main__':
    app.run(debug=True)
