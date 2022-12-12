import urllib
from unittest.mock import patch
import pytest
from moto import mock_ssm, mock_s3
import boto3
from src import lambda_handler
from tests.utils.utils import *


@pytest.fixture(scope='function')
def ssm():
    with mock_ssm():
        yield boto3.client('ssm', region_name='eu-west-2')


@pytest.fixture(scope='function')
def s3():
    with mock_s3():
        yield boto3.client('s3', region_name='eu-west-2')


@patch('urllib.request.urlopen')
def test_files_are_returned(mock_url_open, ssm, s3):
    setup_env_vars()
    setup_ssm(ssm)
    setup_s3(s3)
    configure_mock_urlopen(mock_url_open, graphql_ok_multiple_files)
    event = {'userId': user_id, 'consignmentId': consignment_id}
    with patch('src.lambda_handler.requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = access_token
        response = lambda_handler.handler(event, None)["results"]
        response.sort(key=sort_by_id)
        file_one = response[0]
        file_two = response[1]
        assert file_one["fileId"] == "13702546-da63-4545-a9eb-a892df1aafba"
        assert file_one["originalPath"] == "testfile/subfolder/subfolder2.txt"
        assert file_one["userId"] == user_id
        assert file_one["consignmentId"] == consignment_id
        assert file_two["fileId"] == "1c2b9eeb-2e4c-4cfc-bc08-c193660f86d2"
        assert file_two["originalPath"] == "testfile/subfolder/subfolder1.txt"
        assert file_two["userId"] == user_id
        assert file_two["consignmentId"] == consignment_id


@patch('urllib.request.urlopen')
def test_error_from_graphql_api(mock_url_open, ssm, s3):
    setup_env_vars()
    setup_ssm(ssm)
    setup_s3(s3)
    err = urllib.error.HTTPError(
        'http://testserver.com',
        500,
        'Some Error',
        {'Xpto': 'abc'},
        io.BytesIO(b'xpto'),
    )
    event = {'userId': user_id, 'consignmentId': consignment_id}
    configure_mock_urlopen(mock_url_open, err)
    with patch('src.lambda_handler.requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = access_token
        with pytest.raises(Exception) as ex:
            lambda_handler.handler(event, None)
        assert ex.value.args[1][0]['message'] == 'HTTP Error 500: Some Error'


def test_error_from_keycloak(ssm, s3):
    setup_env_vars()
    setup_ssm(ssm)
    setup_s3(s3)
    event = {'userId': user_id, 'consignmentId': consignment_id}
    with patch('src.lambda_handler.requests.post') as mock_post:
        mock_post.return_value.status_code = 500
        with pytest.raises(RuntimeError) as ex:
            lambda_handler.handler(event, None)
        assert ex.value.args[0] == 'Non 200 status from Keycloak 500'


@patch('urllib.request.urlopen')
def test_error_if_s3_download_error(mock_url_open, ssm, s3):
    setup_env_vars()
    setup_ssm(ssm)
    event = {'userId': user_id, 'consignmentId': consignment_id}
    configure_mock_urlopen(mock_url_open, graphql_ok_multiple_files)
    with patch('src.lambda_handler.requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = access_token
        with pytest.raises(s3.exceptions.NoSuchBucket) as ex:
            lambda_handler.handler(event, None)

        assert ex.value.response['Error']['Message'] == 'The specified bucket does not exist'


@patch('urllib.request.urlopen')
def test_error_if_s3_files_mismatch(mock_url_open, ssm, s3):
    setup_env_vars()
    setup_ssm(ssm)
    setup_s3(s3, missing_file_id)
    event = {'userId': user_id, 'consignmentId': consignment_id}
    configure_mock_urlopen(mock_url_open, graphql_ok_multiple_files)
    with patch('src.lambda_handler.requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = access_token
        with pytest.raises(RuntimeError) as ex:
            lambda_handler.handler(event, None)
        assert ex.value.args[0] == f'Uploaded files do not match files from the API for {user_id}/{consignment_id}'
