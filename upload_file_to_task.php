#!/usr/bin/env php
<?php

#define('APP_KEY', 'f9c650c98eeb28e345e0a38a184d20cb');
#define('USER_TOKEN', 'roBknmkPI0ALmwkRuC1q');
define('APP_KEY', getenv('APP_KEY'));
define('USER_TOKEN', getenv('USER_TOKEN'));

function createTask($title, $description, $boardId, $projectId) {
    $url = "https://runrun.it/api/v1.0/tasks";

    $payload = json_encode(array(
        "task" => array(
            "title" => $title,
            "description" => $description,
            "board_id" => $boardId,
            "project_id" => $projectId
        )
    ));

    $headers = array(
        'app-key: ' . APP_KEY,
        'user-token: ' . USER_TOKEN,
        'Content-Type: application/json;charset=UTF-8',
    );

    $curl = curl_init($url);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);

    $response = curl_exec($curl);
    curl_close($curl);

    return json_decode($response, true);
}

function createDocument($taskId, $filename) {
    $url = "https://runrun.it/api/v1.0/documents?task_id=$taskId";

    $size = filesize($filename);

    $payload = json_encode(array(
        "document" => array(
            "data_file_name" => $filename,
            "data_file_size" => $size,
            "warning_duplicate" => false
        )
    ));

    $headers = array(
        'app-key: ' . APP_KEY,
        'user-token: ' . USER_TOKEN,
        'Content-Type: application/json',
        'cache-control: no-cache',
    );

    $curl = curl_init($url);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);

    $response = curl_exec($curl);
    $document = json_decode($response, true);
    $documentId = $document['id'];
    $fields = $document['fields'];
    $contentType= $fields['content_type'];
    curl_close($curl);

    # Prepare the file upload to S3

    $filePath = realpath($filename);
    $fileCurl = curl_file_create($filePath, $contentType, $filename);

    $postFields = array(
        'name' => $filename,
        'key' => $fields["key"],
        'acl' => 'private',
        'policy' => $fields["policy"],
        'signature' => $fields["signature"],
        'AWSAccessKeyId' => $fields["AWSAccessKeyId"],
        'content_type' => $contentType,
        'filename' => $filename,
        'success_action_status' => 201,
        'file' => $fileCurl,
    );

    $uploadCurl = curl_init('https://s3.amazonaws.com/runrunit');
    curl_setopt($uploadCurl, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($uploadCurl, CURLOPT_POST, true);
    curl_setopt($uploadCurl, CURLOPT_POSTFIELDS, $postFields);
    $uploadResponse = curl_exec($uploadCurl);
    curl_close($uploadCurl);

    # Update document status

    $url = "https://runrun.it/api/v1.0/documents/$documentId/mark_as_uploaded";

    $curl = curl_init($url);
    curl_setopt($uploadCurl, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($curl, CURLOPT_CUSTOMREQUEST, 'POST');
    curl_setopt($curl, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);

    $response = curl_exec($curl);
    curl_close($curl);
}

$title = "First Task";
$description = "My description"
$boardId = 283180;
$projectId = NULL; # COULD BE NECESSARY BASED ON ACCOUNT CONFIGURATION

$task = createTask($title, $description, $boardId, $projectId);

$taskId = $task["id"];
$filename = "example.csv";
createDocument($taskId, $filename);

?>
