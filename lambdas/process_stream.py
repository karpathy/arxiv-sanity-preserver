import boto3
import logging
import csv
import os
import requests
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeDeserializer
from multiprocessing import Process, Pipe

#leverage freezing
TABLE = None
S3CLIENT = None
DESERIALIZER = None
BUCKET_NAME = os.environ['BUCKET_NAME']

def upload_file(target_names, bucket_details):
    # upload file to S3 bucket
    
    if sub_folder := bucket_details['folder']:
        object_name = sub_folder + "/{}".format(target_names['dest']) 
    else:
        object_name = target_names['dest']
    try:
        response = S3CLIENT.upload_file(
            target_names['src'], 
            bucket_details['bucket'], 
            object_name
        )
    except ClientError as e:
        logging.error(e)
        return False
    return True


def extract_record_data(event):
    # extract entry metadata
    for record in event['Records']:
        if record['eventName'] == "INSERT":
            yield {
                key: DESERIALIZER.deserialize(val) for key, val in record['dynamodb']['NewImage'].items()
            }

def create_csv_name():
    # generate a csv file name from the current time 
    now = datetime.now()
    file_name = now.strftime("%a_%b_%d_%y_%H%M%S.%f.csv")
    return file_name

def write_to_csv(file_name, event):
    # write event data to specified csv file
    headed = False
    with open(file_name, "w") as csv_file:
        for data in extract_record_data(event):
            # start the dict writer and add fields if this is the first entry
            if not headed:
                field_names = [key for key in data.keys()]
                entry_writer = csv.DictWriter(csv_file, field_names)
                entry_writer.writeheader()
                headed = True
            # write info
            entry_writer.writerow(data)
    # delete if empty (TODO: a different way to handle mass deletions)
    if os.stat(file_name).st_size == 0:
        os.remove(file_name)


def generate_csv(event):
    # write and upload a csv file containing the record data from the stream
    # this data shall be put in an RD solution later
    file_name = create_csv_name()
    local_file_name = "/tmp/" + file_name
    write_to_csv(local_file_name, event)
    # upload the csv file
    upload_file(
        {
            'src': local_file_name,
            'dest': file_name
        },
        {
            'bucket': BUCKET_NAME,
            'folder': 'csv'
        }
    )

def extract_pdf_link(data):
    # return the first pdf in the record
    return next(
        (
            link['href'] for link in data['links'] 
            if link['type'] == "application/pdf"
        ), "")

def fetch_pdf(raw_id, url, conn):
    # stream response from url into pdf file
    file_name = raw_id + ".pdf"
    local_file_name = "/tmp/" + file_name
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(local_file_name, 'wb') as pdf_file:
            for chunk in response.raw:
                pdf_file.write(chunk)
        # upload the pdf file
        upload_file(
            {
                'src': local_file_name,
                'dest': file_name
            },
            {
                'bucket': BUCKET_NAME,
                'folder': 'pdf'
            }
        )
    conn.close()


def download_pdfs(event):
    # download and then upload article pdfs to s3 storage
    # leverage pipes for parallel execution (pools and queues not available in Lambda)
    procs = []
    for data in extract_record_data(event):
        raw_id = data['rawid']
        url = extract_pdf_link(data)
        # one process per download
        parent_conn, child_conn = Pipe()
        process = Process(target=fetch_pdf, args=(raw_id, url, child_conn))
        procs.append(process)
    # start
    for proc in procs:
        proc.start()
    # join
    for proc in procs:
        proc.join()



def process_records(event):
    # create a csv in an s3 bucket containing the entry data recorded in the event
    # download the article pdfs to an s3 bucket
    generate_csv(event)
    download_pdfs(event)
    



def main(event, context):
    global S3CLIENT, DESERIALIZER
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
        process_records(event)
    except ClientError as cerr:
        logging.error(cerr)
    except Exception as ex:
        logging.error(ex)