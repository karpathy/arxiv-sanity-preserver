import boto3
import os
import logging
from botocore.exceptions import ClientError

S3CLIENT = None
FILE_BUCKET = os.environ['FILE_BUCKET']
TEXT_BUCKET = os.environ['TEXT_BUCKET']

def main(event, context):

    global S3CLIENT
    # load bucket
    if S3CLIENT is None:
        S3CLIENT = boto3.resource('s3')
    # logging
    logging.root.setLevel(logging.INFO) 

    # process records
    try:
        f_bucket = S3CLIENT.Bucket(FILE_BUCKET)
        t_bucket = S3CLIENT.Bucket(TEXT_BUCKET)
        f_bucket.objects.delete()
        t_bucket.objects.delete()

        
    except ClientError as cerr:
        logging.error(cerr)
    except Exception as ex:
        logging.error(ex)