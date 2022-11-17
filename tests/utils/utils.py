import os
import io

user_id = '030cf12c-8d5d-46b9-b86a-38e0920d0e1a'
consignment_id = 'e7073993-0bed-4d5f-bb2a-5bea1b2a87d3'
all_file_ids = ['1c2b9eeb-2e4c-4cfc-bc08-c193660f86d2', '13702546-da63-4545-a9eb-a892df1aafba']
missing_file_id = ['13702546-da63-4545-a9eb-a892df1aafba']

graphql_ok_multiple_files = b'''{
  "data": {
    "getConsignment": {
      "files": [
        {
          "fileId": "1c2b9eeb-2e4c-4cfc-bc08-c193660f86d2",
          "fileType": "File",
          "fileMetadata": [
            {
              "name": "ClientSideOriginalFilepath",
              "value": "testfile/subfolder/subfolder1.txt"
            }
          ]
        },
        {
          "fileId": "13702546-da63-4545-a9eb-a892df1aafba",
          "fileType": "File",
          "fileMetadata": [
            {
              "name": "ClientSideOriginalFilepath",
              "value": "testfile/subfolder/subfolder2.txt"
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


def setup_s3(s3, file_ids=None):
    if file_ids is None:
        file_ids = all_file_ids
    s3.create_bucket(Bucket='test-bucket',
                     CreateBucketConfiguration={
                         'LocationConstraint': 'eu-west-2',
                     })
    for file_id in file_ids:
        s3.delete_object(Bucket="test-bucket", Key=f"{user_id}/{consignment_id}/{file_id}")
        s3.put_object(
            Body=b'filetoupload',
            Bucket='test-bucket',
            Key=f"{user_id}/{consignment_id}/{file_id}",
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


def sort_by_id(file):
    return file["fileId"]
