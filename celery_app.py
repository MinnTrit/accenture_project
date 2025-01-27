
from flask import request, jsonify, render_template
import os
from redbeat import RedBeatSchedulerEntry
from datetime import datetime, timedelta
from tasks import main_task, app, celery
import json
import redis
import pytz
#Initialize common variables
upload_folder = app.config['UPLOAD_FOLDER']
credentials_folder = app.config['CREDENTIAL_FOLDER']
instance_host = os.getenv('instance_host')
r = redis.StrictRedis(host=instance_host,port=6379, db=0)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        result_countries_list = []
        reports_type = request.form.get('reportsType')
        print(reports_type)
        google_credential_name = request.form.get('credentials')
        google_credential_path = os.path.join(credentials_folder, google_credential_name)
        input_countries_list = request.form.getlist('countryList')
        input_raw_cookies = request.form.getlist('cookiesString')
        input_interval = request.form.get("timeInterval")
        input_time_quantifier = request.form.get("timeQuantifier")
        cleaning_option = request.form.get('cleaningOption') == 'True'
        product_spreadsheet = request.form.get('productSpreadsheet').strip()
        product_tab = request.form.get('productWorksheet').strip()
        voucher_spreadsheet = request.form.get('voucherSpreadsheet').strip()
        voucher_tab = request.form.get('voucherWorksheet').strip()
        launcher = request.form.get('launcher')
        for raw_country_list in input_countries_list: 
            country_list = [country.strip() for country in raw_country_list.split(",")]
            result_countries_list.append(country_list)
        jobs_details = {
            "country_list": result_countries_list,
            "cookies_list": input_raw_cookies
        }
        task = main_task.delay(
            google_credential_path=google_credential_path,
            jobs_details=jobs_details, 
            cleaning_option=cleaning_option,
            product_spreadsheet=product_spreadsheet,
            voucher_spreadsheet=voucher_spreadsheet,
            product_tab=product_tab,
            voucher_tab=voucher_tab,
            reports_type=reports_type
            )
        task_id = task.id
        current_time = datetime.now()
        if (input_time_quantifier != 'None') and (input_interval != 'None'):
            if input_time_quantifier == "Hours":
                interval = timedelta(hours=int(input_interval))
            elif input_time_quantifier == "Minutes":
                interval = timedelta(minutes=int(input_interval))
            else:
                interval = timedelta(seconds=int(input_interval))
            entry = RedBeatSchedulerEntry(
                f'laz-task-{task_id}@{launcher}@{input_interval}-{input_time_quantifier}@{result_countries_list}',
                'tasks.main_task',
                interval,
                kwargs={
                    "google_credential_path": google_credential_path,
                    "jobs_details":jobs_details,
                    "cleaning_option": cleaning_option,
                    "product_spreadsheet": product_spreadsheet,
                    "voucher_spreadsheet": voucher_spreadsheet,
                    "product_tab": product_tab,
                    "voucher_tab": voucher_tab,
                    'reports_type': reports_type
                },
                app=celery
            )
            entry.save()
        else:
            r.set(f'custom-{task_id}',json.dumps({
            "launcher": launcher, 
            "reportsType": reports_type,
            "countriesList": result_countries_list
            }))
        task_response = {
            'status_code': 200,
            'task_id': task_id, 
            'task_time': current_time,
            'country_list': result_countries_list,
            'raw_cookies': input_raw_cookies
        }
        return jsonify(task_response)
    else:
        list_items = os.listdir(credentials_folder)
        return render_template('index.html', items=list_items)
    
@app.route('/delete', methods=['GET', 'POST'])
def delete_task():
    redbeat_group = 'redbeat::schedule'
    redis_metadata = 'celery-task-meta'
    if request.method == 'GET':
        scheduled_tasks = r.zrange(redbeat_group, 0, -1, withscores=True)
        accenture_keys = r.keys(f'{redis_metadata}*')
        normal_tasks = [json.loads(r.get(accenture_key).decode('utf-8')) for accenture_key in accenture_keys]
        for task in normal_tasks: 
            task_id = task['task_id']
            custom_metadata = r.get(f'custom-{task_id}')
            if custom_metadata:  
                task.update(json.loads(custom_metadata.decode('utf-8')))
        normal_tasks.sort(key=lambda task: datetime.fromisoformat(task['date_done']), reverse=True)
        return render_template('current_tasks.html', scheduled_tasks=scheduled_tasks, normal_tasks=normal_tasks)
    else: 
        task_id = request.form.get('deleteTask')
        if 'redbeat' in task_id:
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
        else:
            try:
                r.delete(f'celery-task-meta-{task_id}')
                r.delete(f'custom-{task_id}')
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
    
@app.route('/credentials', methods=['GET','POST'])
def upload_credentials():
    if request.method == 'POST':
        uploaded_file = request.files['uploadedGoogleAuth']
        launcher = request.form.get('credentialUploader')
        file_name = f'{launcher}_{uploaded_file.filename}'
        file_path = os.path.join(app.config['CREDENTIAL_FOLDER'], file_name)
        if uploaded_file.filename.endswith('.json'):
            try:
                uploaded_file.save(file_path)
                response_content = {
                    'credentials_path': file_path, 
                    'status_code': 200
                }
            except Exception as e:
                response_content = {
                    'error_message': e,
                    'status_code': 400
                }
        else:
            response_content = {
                'error_message': 'Google Auth Credential must in json format',
                'status_code': 400
            }
        return jsonify(response_content)
    else:
        list_items = os.listdir('/home/ubuntu/credentials')
        owners = [item.split('_')[0] for item in list_items]
        credentials = [item.split('_')[1] for item in list_items]
        return render_template('credentials.html', owners=owners, credentials=credentials)
    
@app.route('/delete_credentials', methods=['POST'])
def delete_credentials():
    credential_name = request.form.get('deleteCredentials')
    file_path = os.path.join(credentials_folder, credential_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        task_response = {
            'deleted_credential': file_path, 
            'status_code': 200
        }
    else:
        task_response = {
            'deleted_credential': file_path, 
            'status_code': 400
        }
    return jsonify(task_response)

@app.template_filter('togmt7')
def convert_to_gmt7(time_string):
    utc_time = datetime.fromisoformat(time_string)
    gmt7 = pytz.timezone('Asia/Ho_Chi_Minh')  # GMT+7
    utc_time = utc_time.replace(tzinfo=pytz.utc) 
    gmt7_time = utc_time.astimezone(gmt7)
    return gmt7_time.strftime('%Y-%m-%d %H:%M:%S')

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
