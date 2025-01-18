from minio import Minio
import os

datalake_host = os.getenv('datalake_host')
datalake_access_key = os.getenv('datalake_access_key')
datalake_secret_key = os.getenv('datalake_secret_key')

class Minio_client:
    def __init__(self, buckets):
        self.client = self.initialize()
        self.buckets = buckets

    def initialize(self):
        client = Minio(
        datalake_host,
        access_key=datalake_access_key,
        secret_key=datalake_secret_key,
        secure=False
        )
        return client
    
    def to_datalake(self,file_path): 
        file_name = os.path.basename(file_path)
        dir_name = os.path.basename(os.path.dirname(file_path))
        object_name = f"{dir_name}/{file_name}"
        if self.client.bucket_exists(self.buckets):
            self.client.fput_object(self.buckets, object_name, file_path)
        else: 
            print(f'Bucket {self.buckets} was not existed, start creating it')
            self.client.make_bucket(self.buckets)
            print(f'Bukets {self.buckets} was created')
            self.client.fput_object(self.buckets, object_name, file_path)
        print(f'{object_name} imported to buckets {self.buckets}')
    
