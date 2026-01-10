import json
import os
import boto3
import yaml

s3 = boto3.client('s3')
secrets = boto3.client('secretsmanager')

def lambda_handler(event, context):
    config_bucket = os.environ['CONFIG_BUCKET']
    config_key = event.get('config_key', 'reddit_icp.yaml')
    output_bucket = os.environ['RESULTS_BUCKET']
    
    # Fetch config from S3
    response = s3.get_object(Bucket=config_bucket, Key=config_key)
    config_data = yaml.safe_load(response['Body'].read())
    
    # Fetch credentials from Secrets Manager
    secret_name = os.environ['SECRET_NAME']
    secret_response = secrets.get_secret_value(SecretId=secret_name)
    credentials = json.loads(secret_response['SecretString'])
    
    # Build task list for each ICP
    tasks = []
    for icp in config_data.get('icps', []):
        tasks.append({
            'icp_name': icp['name'],
            'icp_config': icp,
            'defaults': config_data.get('defaults', {}),
            'credentials': credentials,
            'output_bucket': output_bucket,
            'config_version': config_data.get('version', 1)
        })
    
    return {'tasks': tasks}
