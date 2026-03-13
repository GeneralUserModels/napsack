# BigQuery Client

The BigQuery client uses Google Cloud's `AI.GENERATE` to run vision-language models on your session data, keeping data within your GCP project.

## Prerequisites

- A GCP project with BigQuery and Cloud Storage enabled
- A GCS bucket for uploading video chunks
- A BigQuery object table pointing at that bucket
- Authenticated via Application Default Credentials:

```shell
gcloud auth application-default login
```

## Usage

```shell
napsack-label --session-dir ./logs/session_name \
  --client bigquery \
  --model gemini-2.0-flash-001 \
  --bq-project my-gcp-project \
  --bq-bucket-name my-gcs-bucket \
  --bq-gcs-prefix my_prefix \
  --bq-object-table-location us.screenomics-gemini
```

## Arguments

| Argument | Description |
|----------|-------------|
| `--model` | Model name as used in the BigQuery `AI.GENERATE` endpoint (e.g. `gemini-2.0-flash-001`) |
| `--bq-project` | GCP project ID |
| `--bq-bucket-name` | GCS bucket name for uploading video chunks |
| `--bq-gcs-prefix` | Folder prefix within the GCS bucket (default: `video_chunks`) |
| `--bq-object-table-location` | BigQuery object table location (e.g. `us.screenomics-gemini`) |
