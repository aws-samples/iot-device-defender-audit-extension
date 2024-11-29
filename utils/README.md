# AWS IoT Certificate Manager (for testing) and Sample lambda

This folder contains two Python scripts:
1. `cert_manager.py`
2. `retained_message_publish_lambda.py`

## cert_manager.py

`cert_manager.py` is a script for generating and registering test certificates in AWS IoT. It provides the following functionality:

- `deploy`: Generates and registers a random number of certificates (between 2000 and 5000) with random validity periods (between 1 day and 6 years). The certificate IDs are stored in a local file `certs_data/cert_ids.txt`.
- `deploy_w_even_dist`: Generates and registers a random number of certificates (between 2000 and 5000) with evenly distributed validity periods ranging from 1 day to 6 years. The certificate IDs are stored in a local file `certs_data/cert_ids.txt`.
- `cleanup`: Revokes and deletes the certificates registered by the `deploy` or `deploy_w_even_dist` actions. If any certificates fail to delete, their IDs are kept in the `certs_data/cert_ids.txt` file.
- `purge`: Revokes and deletes all certificates in the AWS IoT account.

### Usage

Alter lines 20 and 21 to alter the range of certificates being created

```
20     MIN_NUM_CERTS = 100
21     MAX_NUM_CERTS = 200
```

```
python cert_manager.py <action>
```

Replace `<action>` with one of the following:

- `deploy`: Generate and register certificates with random validity periods.
- `deploy_w_even_dist`: Generate and register certificates with evenly distributed validity periods.
- `cleanup`: Revoke and delete the previously registered certificates.
- `purge`: Revoke and delete all certificates in the AWS IoT account.


## Prerequisites

Before running these scripts, make sure you have the following:

- Python 3.7 or later installed
- AWS CLI configured with appropriate credentials and permissions
- The required Python packages installed (`boto3`, `cryptography`)
    ```bash
    pip install -r requirements.txt
    ```

- Additionally, for `cert_manager.py`, you'll need permissions to create, update, and delete certificates in AWS IoT.

## retained_message_publish_lambda.py

`retained_message_publish_lambda.py` is a sample lambda function that showcases how to make use of the notification coming the last leg of the architecture. 

In the script you can see how we can integrate this solution into already existing code that makes use of Device Defender Audit for certificate rotation. Here is a sample of that section in the code

```python
    # Filter for actionable check violations
    for audit in event_message["auditDetails"]:
        if (audit["checkName"] == "DEVICE_CERTIFICATE_EXPIRING_CHECK") and (
                audit['checkRunStatus'] == "COMPLETED_NON_COMPLIANT"):
            has_results_s3_bucket = "resultsS3Bucket" in audit.keys()
            has_results_s3_key = "resultsS3Key" in audit.keys()
            
            # If incoming payload came from this custom solution
            if has_results_s3_bucket and has_results_s3_key:
                s3_key = audit['resultsS3Key']
                s3_bucket_name = audit['resultsS3Bucket']
                tmp_file_path = f"/tmp/{s3_key.split('/')[-1]}"

                # Download the JSON file from S3 to the temporary file
                download_s3_file(s3_bucket_name, s3_key, tmp_file_path)

                # Load the JSON data from the temporary file into a variable
                audit_results = load_json_file(tmp_file_path)
            
            # If incoming payload came from Device Defender Audit 
            else:
                # Initialize the list with all impacted things
                audit_results = iot.list_audit_findings(
                    taskId=event_message["taskId"],
                    checkName=audit["checkName"]
                )
            
            # Parse the findings and capture certificate IDs
            for finding in audit_results["findings"]:
                expiring_cert = finding["nonCompliantResource"]["resourceIdentifier"]["deviceCertificateId"]

                # Take action
```