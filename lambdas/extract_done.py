import boto3
import time
from datetime import datetime
import logging
import json
from botocore.exceptions import ClientError

def process_message(event):
    for record in event['Records']:
        if record["EventSource"] == "aws:sns":
            message = json.loads(record["Sns"]["Message"])
            logging.info('Job %s ended with status %s' % (message["JobId"], message["Status"]))
            


def main(event, context):
    # logging
    logging.root.setLevel(logging.INFO) 

    # extract pdfs
    try:
        process_message(event)
    except Exception as ex:
        logging.error(ex)