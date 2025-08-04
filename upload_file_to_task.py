#!/usr/bin/env python3

import os
import requests

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
    response = requests.post(url, json=payload, headers=headers)
    print(response)
    print(response.content)
    return response.json()

def create_document(task_id, filename):
    url = f'https://runrun.it/api/v1.0/documents?task_id={task_id}'

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

    response = requests.post(url, json=payload, headers=headers)

    document = response.json()
    document_id = document['id']
    fields = document['fields']

    action_url = "https://gryvnagsfedj.compat.objectstorage.sa-saopaulo-1.oraclecloud.com/runrunit"

    form_data = {
        'key': fields['key'],
        'Policy': fields['Policy'],
        'X-Amz-Algorithm': fields['X-Amz-Algorithm'],
        'X-Amz-Credential': fields['X-Amz-Credential'],
        'X-Amz-Date': fields['X-Amz-Date'],
        'X-Amz-Signature': fields['X-Amz-Signature'],
        'success_action_status': '201',
    }

    with open(filename, 'rb') as f:
        files = {'file': (filename, f)}
        upload_response = requests.post(action_url, data=form_data, files=files)
        print(f'Upload response: {upload_response.status_code} {upload_response.text}')

    url = f'https://runrun.it/api/v1.0/documents/{document_id}/mark_as_uploaded'

    response = requests.post(url, headers=headers)
    print(f'Mark as uploaded response: {response.status_code} {response.text}')

title = "First Task"
description = "My description"
board_id = 283180
project_id = None # COULD BE NECESSARY BASED ON ACCOUNT CONFIGURATION

task = create_task(title, description, board_id, project_id)

task_id = task["id"]
filename = "example.csv"
document = create_document(task_id, filename)
