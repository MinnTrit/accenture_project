from processing import Processor
from processing import Processor
from datalake import Minio_client
from pusher import Pusher
from worker import make_celery
from flask import Flask
import os

app = Flask(__name__)
broker_url = os.getenv('broker_url')
app.config['CELERY_BROKER_URL'] = broker_url
app.config['CELERY_RESULT_BACKEND'] = broker_url
app.config['REDBEAT_REDIS_URL'] = broker_url
app.config['CELERY_TASK_SERIALIZER'] = 'json'
upload_folder = 'uploads'
app.config['UPLOAD_FOLDER'] = upload_folder
app.secret_key = 'supersecretkey'
celery = make_celery(app)
@celery.task(queue='accenture')
def main_task(jobs_details):
    #Initialize the datalake client
    datalake_client = Minio_client('datalake')

    #Initialize the google api client
    google_client = Pusher(
        credential_path="/home/ubuntu/googleauth.json",
        voucher_spreadsheet="Testing",
        product_spreadsheet="Testing",
        voucher_worksheet="Voucher Analysis",
        product_worksheet="Product Analysis",
        clear_option=True    
    )

    #Initialize the processor
    processor = Processor(
        jobs_details=jobs_details,
        datalake_client=datalake_client,
        google_client=google_client
    )

    processor.get_all_data()