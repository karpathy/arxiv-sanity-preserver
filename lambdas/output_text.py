import boto3
import time
from datetime import datetime
import logging
from botocore.exceptions import ClientError
from multiprocessing import Process, Pipe

#leverage freezing
S3CLIENT = None
TEXTRACT = None


def receive_results(jobid):
    # get results by pinging the job over time - migrate this to a separate lambda and use SNS ASAP
    response = TEXTRACT.get_document_text_detection(JobId=jobid)
    while response['JobStatus'] == 'IN_PROGRESS':
        logging.info('Job %s in progress...' % jobid)
        time.sleep(5)
        response = TEXTRACT.get_document_text_detection(JobId=jobid)
    logging.info('Job %s finished at %s.' % (jobid, datetime.now().strftime("%H:%M:%S")))
    while nextToken := response['NextToken']:
        yield response
        response = TEXTRACT.get_document_text_detection(JobId=jobid, NextToken=nextToken)
    return response


def main(event, context):
    # load bucket
    global S3CLIENT
    if S3CLIENT is None:
        S3CLIENT = boto3.client('s3')
    # load textract
    global TEXTRACT
    if TEXTRACT is None:
        TEXTRACT = boto3.client('textract')
    # logging
    logging.root.setLevel(logging.INFO) 

    # extract pdfs
    try:
        print(event)
    except Exception as ex:
        logging.error(ex)