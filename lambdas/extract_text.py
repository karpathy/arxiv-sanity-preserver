import boto3
import os
import logging
from botocore.exceptions import ClientError
from multiprocessing import Process, Pipe

#leverage freezing
TEXTRACT = None
SNS_ARN = os.environ['SNS_ARN']
ROLE_ARN = os.environ['ROLE_ARN']
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']

def extract_record_data(event):
    # extract info from put record
    for record in event['Records']:
        if record['eventName'] == "ObjectCreated:Put":
            yield record['s3']['bucket']['name'], record['s3']['object']['key']


def start_job(bucket, obj):
    # asynchronously start parsing
    response = TEXTRACT.start_document_text_detection(
        DocumentLocation={
            'S3Object': {
                'Bucket': bucket,
                'Name': obj
            }},
        NotificationChannel={
            'SNSTopicArn': SNS_ARN,
            'RoleArn': ROLE_ARN
        },
        OutputConfig={
            'S3Bucket': OUTPUT_BUCKET,
            'S3Prefix': 'raw_textract'
        }
    )
    jobid = response['JobId']
    return jobid


def main(event, context):
    # load textract
    global TEXTRACT
    if TEXTRACT is None:
        TEXTRACT = boto3.client('textract')
    # logging
    logging.root.setLevel(logging.INFO) 

    # extract pdfs
    try:
        for bucket, obj in extract_record_data(event):
            jobid = start_job(bucket, obj)
            logging.info('Job %s started.' % jobid)
    except Exception as ex:
        logging.error(ex)