import boto3
import os
import random
import argparse
import shutil
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta, timezone

iot = boto3.client('iot')

# Global variables for certificate validity range.
# 1 day to 6 years
MIN_DAYS = 1
MAX_DAYS = 6 * 365
# 1000 to 5000 certificates
MIN_NUM_CERTS = 100
MAX_NUM_CERTS = 200

def generate_certificate(days_valid):
    """Generates a self-signed X.509 certificate valid for the specified number of days."""

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u'Test Certificate'),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(datetime.now(timezone.utc)  # Use datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=days_valid)  # Use datetime.now(timezone.utc)
    ).sign(private_key, hashes.SHA256())

    return cert, private_key

def register_certificate(cert_pem):
    """Registers the certificate with AWS IoT and returns the certificate ID.
    Randomly assigns one of the specified states, with a higher probability for ACTIVE."""

    possible_states = ['ACTIVE', 'INACTIVE']
    # Assign weights to favor ACTIVE state
    weights = [5, 1]  # ACTIVE has 5 times the probability of other states

    chosen_state = random.choices(possible_states, weights=weights)[0]

    response = iot.register_certificate_without_ca(
        certificatePem=cert_pem,
        status=chosen_state
    )
    return response['certificateId']

def deploy_certificates():
    """Generates, registers, and stores certificates."""

    # Create the folder if it doesn't exist
    os.makedirs('certs_data', exist_ok=True)

    num_certs = random.randint(MIN_NUM_CERTS, MAX_NUM_CERTS)

    print(f"Generating {num_certs} certificates...")

    with open('certs_data/cert_ids.txt', 'a') as f:  # Open in append mode
        for _ in range(num_certs):
            days_valid = random.randint(MIN_DAYS, MAX_DAYS)
            cert, _ = generate_certificate(days_valid)
            cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            cert_id = register_certificate(cert_pem)
            print(f"Registered certificate: {cert_id}")
            f.write(cert_id + '\n')  # Write each ID immediately

    print(f"Generated and registered {num_certs} certificates.")

def deploy_certificates_w_even_dist():
    """Generates, registers, and stores certificates with evenly spread validity periods."""

    num_certs = random.randint(MIN_NUM_CERTS, MAX_NUM_CERTS)
    min_days = MIN_DAYS
    max_days = MAX_DAYS
    days_increment = (max_days - min_days) / num_certs

    # Create the folder if it doesn't exist
    os.makedirs('certs_data', exist_ok=True)

    print(f"Generating {num_certs} certificates...")
    with open('certs_data/cert_ids.txt', 'a') as f:
        for i in range(num_certs):
            days_valid = int(min_days + i * days_increment)
            cert, _ = generate_certificate(days_valid)
            cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            cert_id = register_certificate(cert_pem)
            print(f"Registered certificate: {cert_id}")
            f.write(cert_id + '\n')

    print(f"Generated and registered {num_certs} certificates.")

def cleanup_certificates():
    """Deletes the registered certificates and removes their IDs from the local file."""

    shutil.copy('certs_data/cert_ids.txt', 'certs_data/cert_ids.txt.bak')

    with open('certs_data/cert_ids.txt', 'r') as f:  # Specify the folder path
        cert_ids = f.read().splitlines()

    remaining_cert_ids = []
    for cert_id in cert_ids:
        try:
            iot.update_certificate(certificateId=cert_id, newStatus='REVOKED')
            iot.delete_certificate(certificateId=cert_id)
            print(f"Deleted certificate: {cert_id}")
        except Exception as e:
            print(f"Error deleting certificate {cert_id}: {e}")
            remaining_cert_ids.append(cert_id)  # Keep IDs that failed to delete

    # Update cert_ids.txt with only the remaining IDs
    with open('certs_data/cert_ids.txt', 'w') as f:
        for cert_id in remaining_cert_ids:
            f.write(cert_id + '\n')

    if remaining_cert_ids:
        print("Some certificates could not be deleted. Their IDs are still in certs_data/cert_ids.txt.")
    else:
        os.remove('certs_data/cert_ids.txt')
        print("Cleanup complete. All certificates deleted.")


def purge_certificates():
    """Deletes all certificates in AWS IoT."""

    paginator = iot.get_paginator('list_certificates')
    for page in paginator.paginate():
        for cert in page['certificates']:
            cert_id = cert['certificateId']
            try:
                iot.update_certificate(certificateId=cert_id, newStatus='REVOKED')
                iot.delete_certificate(certificateId=cert_id)
                print(f"Deleted certificate: {cert_id}")
            except Exception as e:
                print(f"Error deleting certificate {cert_id}: {e}")

    print("Purge complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy, cleanup, or purge test certificates in AWS IoT.")
    parser.add_argument("action", choices=["deploy", "deploy_w_even_dist", "cleanup", "purge"], help="Action to perform: deploy, deploy_w_even_dist, cleanup, or purge")
    args = parser.parse_args()

    if args.action == "deploy":
        deploy_certificates()
    elif args.action == "cleanup":
        cleanup_certificates()
    elif args.action == "purge":
        purge_certificates()
    elif args.action == "deploy_w_even_dist":
        deploy_certificates_w_even_dist()