# TDR File Upload Data

This is the replacement for the tdr-download files lambda. 
It receives `{"consignmentId": "xxxx-xxxx-xxxx"}` as input with optional fields `s3SourceBucket` and `s3SourceBucketKey` then:

* Calls the API to get a list of fileIds and original path data
* Gets the list of files from S3
* Compares the two and throws an error if there is a mismatch
* Returns:
    ```
    [
        {
            "consignmentId": "xxxx-xxxx-xxxx",
            "fileId": "xxxx-xxxx-xxxx" ,
            "originalPath": "/original/file/path",
            "userId": "xxxx-xxxx-xxxx",
            "s3SourceBucket": "{bucket name}",
            "s3SourceBucketKey": "{key prefix}/{file id}"
        },
        ... etc ...
     ]
    ```

* Optional input fields `s3SourceBucket` and `s3SourceBucketKey` will use default values if not present in the input

This array will then be passed to the map function in the step function which will call each of the backend checks in turn.
  
## Running locally
You will need credentials for the AWS environment you are running this for set either as environment variables in the debug configuration or as a profile in `~/.aws/credentials`

In the [lambda_runner](src/lambda_runner.py) file, replace the `user_id` and `consignment_id` variables with valid values.

Set the following environment variables. These are for integration but can be replaced for other environments. 
```
CLIENT_SECRET_PATH=/intg/keycloak/backend_checks_client/secret
AUTH_URL=https://auth.tdr-integration.nationalarchives.gov.uk
CLIENT_ID=tdr-backend-checks
API_URL=https://api.tdr-integration.nationalarchives.gov.uk/graphql
BUCKET_NAME=tdr-upload-files-cloudfront-dirty-intg
```
Run `lambda_runner.py`

## Running the tests
The tests can be run in PyCharm by creating [a pytest configuration](https://www.jetbrains.com/help/pycharm/run-debug-configuration-py-test.html).

They can also be run in the terminal. You need python3.9 running on your system.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m pytest 
```
