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
app.config['CREDENTIAL_FOLDER'] = '/home/ubuntu/credentials'
app.config['UPLOAD_FOLDER'] = upload_folder
app.secret_key = 'supersecretkey'
celery = make_celery(app)

@celery.task(queue='accenture',max_retries=5, acks_late=True)
def main_task(
    jobs_details:dict, 
    google_credential_path: str,
    product_spreadsheet: str,
    voucher_spreadsheet: str, 
    product_tab: str,
    voucher_tab: str,
    cleaning_option: bool
    ):
    #Initialize the datalake client
    datalake_client = Minio_client('datalake')

    #Initialize the google api client
    google_client = Pusher(
        credential_path=google_credential_path,
        voucher_spreadsheet=voucher_spreadsheet,
        product_spreadsheet=product_spreadsheet,
        voucher_worksheet=voucher_tab,
        product_worksheet=product_tab,
        clear_option=cleaning_option
    )

    if (google_client.product_worksheet is not None) & (google_client.voucher_worksheet is not None):
        #Initialize the processor
        processor = Processor(
            jobs_details=jobs_details,
            datalake_client=datalake_client,
            google_client=google_client
        )

        processor.get_all_data()
    else:
        print('Failed initializing the Google Client')
