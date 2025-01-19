from flask import request, jsonify, render_template, session, redirect, url_for
import os
from redbeat import RedBeatSchedulerEntry
from datetime import datetime, timedelta
from tasks import main_task, app, celery
import redis
#Initialize common variables
upload_folder='uploads'
instance_host = os.getenv('instance_host')
r = redis.StrictRedis(host=instance_host,port=6379, db=0)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        result_countries_list = []
        input_countries_list = request.form.getlist('countryList')
        input_raw_cookies = request.form.getlist('cookiesString')
        input_interval = request.form.get("timeInterval")
        input_time_quantifier = request.form.get("timeQuantifier")
        cleaning_option = request.form.get('cleaningOption') == 'True'
        launcher = request.form.get('launcher')
        for raw_country_list in input_countries_list: 
            country_list = [country.strip() for country in raw_country_list.split(",")]
            result_countries_list.append(country_list)
        jobs_details = {
            "country_list": result_countries_list,
            "cookies_list": input_raw_cookies
        }
        current_time = datetime.now()
        if input_time_quantifier == "Hours":
            interval = timedelta(hours=int(input_interval))
        elif input_time_quantifier == "Minutes":
            interval = timedelta(minutes=int(input_interval))
        else:
            interval = timedelta(seconds=int(input_interval))
        task = main_task.delay(jobs_details, cleaning_option)
        task_id = task.id
        entry = RedBeatSchedulerEntry(
            f'laz-task-{task_id}@{launcher}@{input_interval}-{input_time_quantifier}@{result_countries_list}',
            'tasks.main_task',
            interval,
            kwargs={
                "jobs_details":jobs_details,
                "cleaning_option": cleaning_option
                },
            app=celery
        )
        entry.save()
        task_response = {
            'status_code': 200,
            'task_time': current_time,
            'country_list': result_countries_list,
            'raw_cookies': input_raw_cookies
        }
        return jsonify(task_response)
    else:
        return render_template('index.html')
    
@app.route('/delete', methods=['GET', 'POST'])
def delete_task():
    redbeat_group = 'redbeat::schedule'
    if request.method == 'GET':
        elements = r.zrange(redbeat_group, 0, -1, withscores=True)
        return render_template('current_tasks.html', keys=elements)
    else: 
        task_id = request.form.get('deleteTask')
        try: 
            r.zrem(redbeat_group, task_id)
            response = {
                'status_code': 200,
                'message': 'success'
            }
        except Exception as e:
            response = {
                'status_code': 400,
                'message': e
            }
        return jsonify(response)

@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
    
@app.template_filter('taskstatus')
def task_status(task_id):
    task = celery.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'status': 'pending',
            'message': 'Task is still processing.'
        }
    elif task.state == 'SUCCESS':
        response = {
            'status': 'success',
            'message': task.result
        }
    elif task.state == 'FAILURE':
        response = {
            'status': 'failure',
            'message': str(task.result)
        }
    else:
        response = {
            'status': 'unknown',
            'message': 'Task state is unknown.'
        }
    return response['status'].capitalize().strip()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)