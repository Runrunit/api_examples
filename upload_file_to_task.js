#!/usr/bin/env node

require('dotenv').config();

const FormData = require('form-data');
const axios = require('axios');
const fs = require('fs');

const APP_KEY = process.env.APP_KEY;
const USER_TOKEN = process.env.USER_TOKEN;

const createTask = async (title, description, board_id, project_id) => {
  const url = "https://runrun.it/api/v1.0/tasks";
  const payload = { task: { title, description, board_id, project_id } };
  const headers = { 'app-key': APP_KEY, 'user-token': USER_TOKEN, 'content-type': "application/json;charset=UTF-8" };
  try {
    const response = await axios.post(url, payload, { headers });
    console.log(response.data);
    return response.data;
  } catch (error) { console.error(error); }
};

const createDocument = async (task_id, filename) => {
  const url = `https://runrun.it/api/v1.0/documents?task_id=${task_id}`;
  const size = fs.statSync(`./${filename}`).size;
  const payload = { document: { data_file_name: filename, data_file_size: size, warning_duplicate: false } };
  const headers = { 'app-key': APP_KEY, 'user-token': USER_TOKEN, 'content-type': 'application/json', 'cache-control': 'no-cache' };

  const response = await axios.post(url, payload, { headers, params: { task_id } });
  const { id: document_id, fields} = response.data;

  const actionUrl = "https://gryvnagsfedj.compat.objectstorage.sa-saopaulo-1.oraclecloud.com/runrunit"

  const form = new FormData();
  form.append('key', fields.key);
  form.append('Policy', fields.Policy);
  form.append('X-Amz-Algorithm', fields['X-Amz-Algorithm']);
  form.append('X-Amz-Credential', fields['X-Amz-Credential']);
  form.append('X-Amz-Date', fields['X-Amz-Date']);
  form.append('X-Amz-Signature', fields['X-Amz-Signature']);
  form.append('success_action_status', '201');

  // Arquivo
  form.append('file', fs.createReadStream(`./${filename}`));

  const formHeaders = form.getHeaders();

  try {
    await axios.post(actionUrl, form, { headers: { ...formHeaders } });
    await axios.post(`https://runrun.it/api/v1.0/documents/${document_id}/mark_as_uploaded`, {}, { headers });
  } catch (error) {
    console.error(error?.response?.status, error?.response?.data || error.message);
  }
};

const title = "First Task";
const description = "My description";
const board_id = 493553;
const project_id = null;

createTask(title, description, board_id, project_id).then(task => {
  createDocument(task.id, "example.csv");
});
