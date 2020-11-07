import boto3
import logging
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeDeserializer

#leverage freezing
TABLE = None
S3CLIENT = None
DESERIALIZER = None

def upload_file(file_name, s3, bucket):
    # upload file to S3 bucket
    
    object_name = file_name
    try:
        response = s3.upload_life(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True


def process_records(event):
    # extract entry metadata
    for record in event['Records']:
        yield {
            key: DESERIALIZER.deserialize(val) for key, val in record['dynamodb']['NewImage'].items()
        }

def main(event, context):
    # load table
    global TABLE, S3CLIENT, DESERIALIZER
    if TABLE is None:
        TABLE = boto3.resource('dynamodb').Table('asp2-fetch-results')
    # load bucket
    if S3CLIENT is None:
        S3CLIENT = boto3.client('s3')
    # load serializer
    if DESERIALIZER is None:
        DESERIALIZER = TypeDeserializer()
    # logging
    logging.root.setLevel(logging.NOTSET) 

    # process records
    try:
        for link in process_records(event):
            logging.info(link)
    except Exception as e:
        logging.error(e)