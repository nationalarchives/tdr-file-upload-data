import os
import io
import json

user_id = '030cf12c-8d5d-46b9-b86a-38e0920d0e1a'
consignment_id = 'e7073993-0bed-4d5f-bb2a-5bea1b2a87d3'
file_one_id = "13702546-da63-4545-a9eb-a892df1aafba"
file_two_id = "1c2b9eeb-2e4c-4cfc-bc08-c193660f86d2"
all_file_ids = [file_two_id, file_one_id]
missing_file_id = [file_two_id]
file_one_match_id = "matchId1"
file_two_match_id = "matchId2"
all_match_ids = [file_two_match_id, file_one_match_id]


graphql_ok_multiple_files = b'''{
  "data": {
    "getConsignment": {
      "consignmentType": "standard",
      "userid": "030cf12c-8d5d-46b9-b86a-38e0920d0e1a",
      "files": [
        {
          "fileId": "1c2b9eeb-2e4c-4cfc-bc08-c193660f86d2",
          "uploadMatchId": "matchId2",
          "fileType": "File",
          "fileMetadata": [
            {
              "name": "ClientSideOriginalFilepath",
              "value": "testfile/subfolder/subfolder1.txt"
            },
            {
              "name": "SHA256ClientSideChecksum",
              "value": "achecksum"
            },
            {
              "name": "ClientSideFileSize",
              "value": "0"
            }
          ]
        },
        {
          "fileId": "13702546-da63-4545-a9eb-a892df1aafba",
          "uploadMatchId": "matchId1",
          "fileType": "File",
          "fileMetadata": [
            {
              "name": "ClientSideOriginalFilepath",
              "value": "testfile/subfolder/subfolder2.txt"
            },
            {
              "name": "SHA256ClientSideChecksum",
              "value": "achecksum"
            },
            {
              "name": "ClientSideFileSize",
              "value": "0"
            }
          ]
        }
      ]
    }
  }
}
'''


def setup_ssm(ssm):
    ssm.put_parameter(
        Name="/test/client/secret",
        Description="description",
        Value="client-secret",
        Type="SecureString",
        Overwrite=True,
    )


def get_result_from_s3(s3, prefix):
    bucket = 'test-backend-checks-bucket'
    objects = s3.list_objects(Bucket=bucket, Prefix=prefix + "/")
    obj = s3.get_object(Bucket='test-backend-checks-bucket', Key=objects['Contents'][0]['Key'])
    return json.loads(obj['Body'].read().decode("utf-8"))


def setup_s3(s3, file_ids=None, match_ids=None, bucket='test-bucket', prefix=None):
    object_ids = []
    if prefix is None:
        prefix = f"{user_id}/{consignment_id}/"
    if "sharepoint" in prefix and match_ids is None:
            object_ids = all_match_ids
    elif file_ids is None:
        object_ids = all_file_ids
    s3.create_bucket(Bucket='test-backend-checks-bucket',
                     CreateBucketConfiguration={
                         'LocationConstraint': 'eu-west-2'
                     })
    s3.create_bucket(Bucket='test-bucket',
                     CreateBucketConfiguration={
                         'LocationConstraint': 'eu-west-2',
                     })
    s3.create_bucket(Bucket='override-bucket',
                     CreateBucketConfiguration={
                         'LocationConstraint': 'eu-west-2',
                     })
    for object_id in object_ids:
        s3.delete_object(Bucket="test-bucket", Key=f"{prefix}{object_id}")
        s3.put_object(
            Body=b'filetoupload',
            Bucket=f'{bucket}',
            Key=f"{prefix}{object_id}",
        )


def configure_mock_urlopen(mock_urlopen, payload):
    if isinstance(payload, Exception):
        mock_urlopen.side_effect = payload
    else:
        mock_urlopen.return_value = io.BytesIO(payload)


def access_token():
    return {'access_token': 'ABCD'}


def setup_env_vars():
    os.environ["CLIENT_SECRET_PATH"] = "/test/client/secret"
    os.environ["AUTH_URL"] = "http://localhost"
    os.environ["CLIENT_ID"] = "id"
    os.environ["API_URL"] = "http://localhost"
    os.environ["BUCKET_NAME"] = "test-bucket"
    os.environ['AWS_DEFAULT_REGION'] = 'eu-west-2'
    os.environ['BACKEND_CHECKS_BUCKET_NAME'] = "test-backend-checks-bucket"


def sort_by_id(file):
    return file["fileId"]
