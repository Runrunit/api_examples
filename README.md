# Utilização

Para fazer upload de um arquivo no Runrun.it utilizamos a API `documents`.
O processo envolve a comunicação com o Runrun.it para adquirir credenciais de upload, upload do arquivo no S3 e depois confirmação do upload.
Somente após a confirmação do upload o arquivo irá aparecer no sistema.
Caso a confirmação do upload não seja feita o registro será apagado depois de um tempo.
As credenciais de upload possuem validade e deverão ser utilizadas imediatamente após geradas.

O diagrama de sequência abaixo mostra o fluxo utilizado nos exemplos.

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API as API Runrun.it
    participant S3 as S3 AWS

    C->>API: POST /tasks (cria tarefa)
    Note over C,API: Inclui app-key, user-token, e detalhes da tarefa
    API-->>C: Resposta com ID da tarefa

    C->>API: POST /documents?task_id= (cria documento)
    Note over C,API: Inclui app-key, user-token, nome do arquivo, e tamanho
    API-->>C: Resposta com campos para upload S3

    C->>S3: POST (upload do arquivo)
    Note over C,S3: Inclui campos recebidos da API, arquivo, e metadados
    S3-->>C: Confirmação do upload

    C->>API: POST /documents/{document_id}/mark_as_uploaded (atualiza documento)
    Note over C,API: Indica que o arquivo foi transferido
    API-->>C: Confirmação da atualização do documento
```

# Como executar os exemplos

Ë necessário utilizar um par de APP_KEY e USER_TOKEN para fazer upload. O par abaixo são exemplos e deverão ser trocados por credenicias reais para funcionar.
É necessário também editar os exemplos e substituir o código do quadro e outros dados.
As credenciais são nominais, ou seja, o dono da credencial irá aparecer como quem fez upload do arquivo.

## PHP

`APP_KEY=f9c650c98eeb28e345e0a38a184d20cb USER_TOKEN=roBknmkPI0ALmwkRuC1q php upload_file_to_task.php`

## PYTHON

`APP_KEY=f9c650c98eeb28e345e0a38a184d20cb USER_TOKEN=roBknmkPI0ALmwkRuC1q python3 upload_file_to_task.py`

## Node.js

`npm install`
`APP_KEY=f9c650c98eeb28e345e0a38a184d20cb USER_TOKEN=roBknmkPI0ALmwkRuC1q node upload_file_to_task.js`
