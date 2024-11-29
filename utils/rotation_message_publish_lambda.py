# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import boto3

s3 = boto3.client('s3')
iot = boto3.client('iot')
iot_data = boto3.client('iot-data')


def download_s3_file(bucket_name, s3_key, tmp_file_path):
    """
    Download a file from S3 to a temporary file.
    """
    try:
        s3.download_file(bucket_name, s3_key, tmp_file_path)
    except Exception as e:
        print(f"Error downloading file from S3: {e}")
        raise


def load_json_file(file_path):
    """
    Load JSON data from a file into a variable.
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading JSON data: {e}")
        raise


def get_certificate_arn(cert_id):
    """
    Get the ARN for a given certificate ID.
    """
    cert_desc_response = iot.describe_certificate(certificateId=cert_id)
    return cert_desc_response["certificateDescription"]["certificateArn"]


def get_things_for_certificate(cert_arn):
    """
    Get the list of things associated with a given certificate ARN.
    """
    things_resp = iot.list_principal_things(
        maxResults=100,
        principal=cert_arn
    )
    return things_resp["things"]


def publish_rotation_message(thing_name, cert_id):
    """
    Publish a message to a thing to initiate certificate rotation.
    """
    payload = {
        "task": "Rotate Certificate!"
    }
    response = iot_data.publish(
        topic=f'thing/{thing_name}/cert/{cert_id}/rotate',
        qos=1,
        payload=json.dumps(payload),
    )
    return response


def lambda_handler(event, context):
    publish_payloads = []
    event_message = json.loads(event["Records"][0]["Sns"]["Message"])

    # Filter for actionable check violations
    for audit in event_message["auditDetails"]:
        if (audit["checkName"] == "DEVICE_CERTIFICATE_EXPIRING_CHECK") and (
                audit['checkRunStatus'] == "COMPLETED_NON_COMPLIANT"):
            has_results_s3_bucket = "resultsS3Bucket" in audit.keys()
            has_results_s3_key = "resultsS3Key" in audit.keys()

            if has_results_s3_bucket and has_results_s3_key:
                s3_key = audit['resultsS3Key']
                s3_bucket_name = audit['resultsS3Bucket']
                tmp_file_path = f"/tmp/{s3_key.split('/')[-1]}"

                # Download the JSON file from S3 to the temporary file
                download_s3_file(s3_bucket_name, s3_key, tmp_file_path)

                # Load the JSON data from the temporary file into a variable
                audit_results = load_json_file(tmp_file_path)

            else:
                # Initialize the list with all impacted things
                audit_results = iot.list_audit_findings(
                    taskId=event_message["taskId"],
                    checkName=audit["checkName"]
                )

            for finding in audit_results["findings"]:
                expiring_cert = finding["nonCompliantResource"]["resourceIdentifier"]["deviceCertificateId"]

                # Get the ARN for the certificate
                cert_arn = get_certificate_arn(expiring_cert)

                # Get things for this cert
                things = get_things_for_certificate(cert_arn)

                # Publish message
                for thing in things:
                    publish_rotation_message(thing, expiring_cert)

    return {
        'statusCode': 200,
        'body': json.dumps('Executed Certificate Rotation Initiation Event!')
    }