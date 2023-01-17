from sgqlc.endpoint.http import HTTPEndpoint
from sgqlc.operation import Operation
from sgqlc.types.relay import Connection
from sgqlc.types import Type, Field, list_of
from boto3 import client
import os
import requests


class FileMetadata(Type):
    name = Field(str)
    value = Field(str)


class File(Type):
    fileId = Field(str)
    fileType = Field(str)
    fileMetadata = list_of(FileMetadata)


class Consignment(Connection):
    files = list_of(File)
    consignmentType = Field(str)
    userid = Field(str)


class Query(Type):
    getConsignment = Field(Consignment, args={'consignmentid': str})


def get_client_secret():
    client_secret_path = os.environ["CLIENT_SECRET_PATH"]
    ssm_client = client("ssm")
    response = ssm_client.get_parameter(
        Name=client_secret_path,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


def get_token(client_secret):
    client_id = os.environ["CLIENT_ID"]
    auth_url = f'{os.environ["AUTH_URL"]}/realms/tdr/protocol/openid-connect/token'
    grant_type = {"grant_type": "client_credentials"}
    auth_response = requests.post(auth_url, data=grant_type, auth=(client_id, client_secret))
    if auth_response.status_code != 200:
        raise RuntimeError(f"Non 200 status from Keycloak {auth_response.status_code}")
    return auth_response.json()['access_token']


def get_query(consignment_id):
    operation = Operation(Query)
    consignment = operation.getConsignment(consignmentid=consignment_id)
    consignment.consignmentType()
    consignment.userid()
    files = consignment.files()
    files.fileId()
    files.fileType()
    files.fileMetadata()
    return operation


def get_metadata_value(file, name):
    return [data['value'] for data in file.fileMetadata if data.name == name][0]


def process_file(file: File):
    return {
        'fileId': file.fileId,
        'originalPath': get_metadata_value(file, "ClientSideOriginalFilepath"),
        'fileSize': get_metadata_value(file, "ClientSideFileSize"),
        "clientChecksum": get_metadata_value(file, "SHA256ClientSideChecksum")
    }


def s3_list_files(prefix):
    s3_client = client("s3")
    truncated = True
    marker = ''
    response = None
    while truncated:
        response = s3_client.list_objects(
            Bucket=os.environ['BUCKET_NAME'],
            Prefix=prefix,
            Marker=marker
        )
        truncated = response["IsTruncated"]
        marker = response['Marker'] if truncated else ''
    return [entry["Key"].split("/")[2] for entry in response["Contents"]]


def validate_all_files_uploaded(prefix, consignment: Consignment):
    api_files = [file.fileId for file in consignment.files if file.fileType == "File"]
    s3_files = s3_list_files(prefix)
    api_files.sort()
    s3_files.sort()
    return api_files == s3_files


def consignment_statuses(consignment_id, status_name, status_value='InProgress', overwrite = False):
    return {
        "id": consignment_id,
        "statusType": "Consignment",
        "statusName": status_name,
        "statusValue": status_value,
        "overwrite": overwrite
    }


def handler(event, lambda_context):
    consignment_id = event["consignmentId"]
    query = get_query(consignment_id)
    client_secret = get_client_secret()
    api_url = os.environ["API_URL"]
    headers = {'Authorization': f'Bearer {get_token(client_secret)}'}
    endpoint = HTTPEndpoint(api_url, headers, 300)
    data = endpoint(query)
    if 'errors' in data:
        raise Exception("Error in response", data['errors'])
    consignment = (query + data).getConsignment
    user_id = consignment.userid
    are_all_files_uploaded = validate_all_files_uploaded(f"{user_id}/{consignment_id}", consignment)
    status_names = ['ServerFFID', 'ServerChecksum', 'ServerAntivirus']
    statuses = [consignment_statuses(consignment_id, status_name) for status_name in status_names]
    statuses.append(consignment_statuses(consignment_id, "Upload", "Completed", True))
    if are_all_files_uploaded:
        return {
            "results": [process_file(file) |
                        {'consignmentType': consignment.consignmentType, 'consignmentId': consignment_id, 'userId': user_id}
                        for file in consignment.files if file.fileType == "File"],

            "statuses": {
                "statuses": statuses
            }
        }
    else:
        return {
            "results": [],
            "statuses": {
                "statuses": [
                    consignment_statuses(consignment_id, "Upload", "CompletedWithIssues", True)
                ]
            }
        }
