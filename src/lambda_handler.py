import json
import os
import uuid
from dataclasses import dataclass
from typing import Optional

import requests
from boto3 import resource, client
from sgqlc.endpoint.http import HTTPEndpoint
from sgqlc.operation import Operation
from sgqlc.types import Type, Field, list_of
from sgqlc.types.relay import Connection


class FileMetadata(Type):
    name = Field(str)
    value = Field(str)


class File(Type):
    fileId = Field(str)
    matchId = Field(str)
    fileType = Field(str)
    fileMetadata = list_of(FileMetadata)


class Consignment(Connection):
    files = list_of(File)
    consignmentType = Field(str)
    userid = Field(str)


class Query(Type):
    getConsignment = Field(Consignment, args={'consignmentid': str})


@dataclass(frozen=True)
class BuildSettings:
    consignment_id: str
    s3_source_bucket: Optional[str] = None
    s3_source_bucket_prefix: Optional[str] = None


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
    files.matchId()
    files.fileType()
    files.fileMetadata()
    return operation


def get_metadata_value(file, name):
    return [data['value'] for data in file.fileMetadata if data.name == name][0]


def get_object_identifier(prefix, file: File):
    obj_identifier = file.fileId
    if "sharepoint" in prefix:
        obj_identifier = file.matchId
    return obj_identifier


def process_file(s3_source_bucket, prefix, file: File):
    obj_identifier = get_object_identifier(prefix, file)
    return {
        's3SourceBucket': s3_source_bucket,
        's3SourceBucketKey': f'{prefix}/{obj_identifier}',
        'fileId': file.fileId,
        'originalPath': get_metadata_value(file, "ClientSideOriginalFilepath"),
        'fileSize': get_metadata_value(file, "ClientSideFileSize"),
        "clientChecksum": get_metadata_value(file, "SHA256ClientSideChecksum"),
        "fileCheckResults": {
            "antivirus": [],
            "checksum": [],
            "fileFormat": []
        }
    }


def s3_list_files(s3_source_bucket, prefix):
    s3 = resource("s3")
    bucket = s3.Bucket(s3_source_bucket)
    objs = bucket.objects.filter(Prefix=prefix)
    return [entry.key.rsplit("/", 1)[1] for entry in objs]


def validate_all_files_uploaded(s3_source_bucket, prefix, consignment: Consignment):
    api_files = [get_object_identifier(prefix, file) for file in consignment.files if file.fileType == "File"]
    s3_files = s3_list_files(s3_source_bucket, prefix)
    api_files.sort()
    s3_files.sort()
    if api_files != s3_files:
        raise RuntimeError(f"Uploaded files do not match files from the API for {prefix}")


def consignment_statuses(consignment_id, status_name, status_value='InProgress', overwrite=False):
    return {
        "id": consignment_id,
        "statusType": "Consignment",
        "statusName": status_name,
        "statusValue": status_value,
        "overwrite": overwrite
    }


def write_results_json(json_result, consignment_id):
    s3 = client("s3")
    key = f"{consignment_id}/{uuid.uuid4()}/results.json"
    bucket = os.environ["BACKEND_CHECKS_BUCKET_NAME"]
    s3.put_object(
        Body=json_result,
        Bucket=bucket,
        Key=key,
    )
    return {
        "key": key,
        "bucket": bucket
    }


def build_settings(event: dict) -> BuildSettings:
    dirty_s3_source_bucket = os.environ['BUCKET_NAME']
    consignment_id = event["consignmentId"]
    s3_source_bucket = event.get("s3SourceBucket", dirty_s3_source_bucket)
    s3_source_bucket_prefix = event.get("s3SourceBucketPrefix", None)
    return BuildSettings(
        consignment_id=consignment_id,
        s3_source_bucket=s3_source_bucket,
        s3_source_bucket_prefix=s3_source_bucket_prefix
    )


def handler(event, lambda_context):
    settings = build_settings(event)
    consignment_id = settings.consignment_id
    s3_source_bucket = settings.s3_source_bucket

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
    prefix = f"{user_id}/{consignment_id}"
    if settings.s3_source_bucket_prefix is not None:
        prefix = settings.s3_source_bucket_prefix
    validate_all_files_uploaded(s3_source_bucket, prefix, consignment)
    status_names = ['ServerFFID', 'ServerChecksum', 'ServerAntivirus']
    results = {
        "results": [process_file(s3_source_bucket, prefix, file) |
                    {'consignmentType': consignment.consignmentType, 'consignmentId': consignment_id, 'userId': user_id}
                    for file in consignment.files if file.fileType == "File"],
        "statuses": {
            "statuses": [consignment_statuses(consignment_id, status_name) for status_name in status_names]
        },
        "redactedResults": {
            "redactedFiles": [],
            "errors": []
        }
    }
    bucket_info = write_results_json(json.dumps(results), consignment_id)
    return {
        "key": bucket_info["key"],
        "bucket": bucket_info["bucket"]
    }
