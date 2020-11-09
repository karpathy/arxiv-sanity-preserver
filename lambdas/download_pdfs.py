import boto3
import logging
import csv
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeDeserializer

#leverage freezing
TABLE = None
S3CLIENT = None
DESERIALIZER = None

def upload_file(target_names, s3, bucket_details):
    # upload file to S3 bucket
    
    if sub_folder := bucket_details['folder']:
        object_name = sub_folder + "/{}".format(target_names['dest']) 
    else:
        object_name = target_names['dest']
    try:
        response = s3.upload_file(
            target_names['src'], 
            bucket_details['bucket'], 
            object_name
        )
    except ClientError as e:
        logging.error(e)
        return False
    return True


def process_records(event):
    # extract entry metadata
    for record in event['Records']:
        if record['eventName'] == "INSERT":
            yield {
                key: DESERIALIZER.deserialize(val) for key, val in record['dynamodb']['NewImage'].items()
            }
        
def write_entries_to_csv(event, s3):
    # create a csv in an s3 bucket containing the entry data recorded in the event
    now = datetime.now()
    # file name uses time stamp common to all the records in the event
    file_name = now.strftime("%a_%b_%d_%y_%H%M%S.%f.csv")
    local_file_name = "/tmp/" + file_name
    headed = False
    with open(local_file_name, "w") as csv_file:
        for data in process_records(event):
            # start the dict writer and add fields if this is the first entry
            if not headed:
                field_names = [key for key in data.keys()]
                entry_writer = csv.DictWriter(csv_file, field_names)
                entry_writer.writeheader()
                headed = True
            # write info
            entry_writer.writerow(data)
    # upload the file
    upload_file(
        {
            'src': local_file_name,
            'dest': file_name
        },
        s3,
        {
            'bucket': 'asp2-file-bucket',
            'folder': 'csv'
        }
    )


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
    logging.root.setLevel(logging.INFO) 

    # process records
    try:
        logging.info(event['Records'])
        logging.info("Processing %i records..." % len(event['Records']))
        write_entries_to_csv(event, S3CLIENT)
    except ClientError as cerr:
        logging.error(cerr)
    except Exception as ex:
        logging.error(ex)