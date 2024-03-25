#!/usr/bin/env python3 

import os
import requests
import pdb

APP_KEY = os.getenv('APP_KEY')
USER_TOKEN = os.getenv('USER_TOKEN')

def create_task(title, description, board_id, project_id):
    url = "https://runrun.it/api/v1.0/tasks"

    payload = {
            "task": {
                "title": title,
                "description": description,
                "board_id": board_id,
                "project_id": project_id,
                }
            }
    headers = {
            'app-key': APP_KEY,
            'user-token': USER_TOKEN,
            'content-type': "application/json;charset=UTF-8",
            }

    print(payload)
    response = requests.request("POST", url, json=payload, headers=headers)
    print(response)
    print(response.content)
    return response.json()

def create_document(task_id, filename):
    url = f'https://runrun.it/api/v1.0/documents?task_id={task_id}'

    querystring = {"task_id":task_id}

    size = os.path.getsize(f'./{filename}')

    payload = {
            "document": {
                "data_file_name": filename,
                "data_file_size": size,
                "warning_duplicate": False
                }
            }

    headers = {
            'app-key': APP_KEY,
            'user-token': USER_TOKEN,
            'content-type': "application/json",
            'cache-control': "no-cache",
            }

    response = requests.request("POST", url, json=payload, headers=headers, params=querystring)

    document = response.json()
    document_id = document['id']
    fields = document['fields']
    key = fields["key"]
    policy = fields["policy"]
    signature = fields["signature"]
    awsaccesskeyid = fields["AWSAccessKeyId"]
    content_type = fields["content_type"]

    upload_file_cmd = f'curl -H "Content-Type: multipart/form-data" \
    -F name={filename} \
    -F key={key} \
    -F acl=private \
    -F policy={policy} \
    -F signature={signature} \
    -F AWSAccessKeyId={awsaccesskeyid}\
    -F content_type={content_type} \
    -F filename={filename} \
    -F success_action_status=201 \
    -F file=@{filename} -X POST https://s3.amazonaws.com/runrunit'
    os.system(upload_file_cmd)

    url = f'https://runrun.it/api/v1.0/documents/{document_id}/mark_as_uploaded'

    response = requests.request("POST", url, headers=headers, params=querystring)

title = "First Task"
description = "My description"
board_id = 283180
project_id = None # COULD BE NECESSARY BASED ON ACCOUNT CONFIGURATION

task = create_task(title, description, board_id, project_id)

task_id = task["id"]
filename = "example.csv"
document = create_document(task_id, filename)
