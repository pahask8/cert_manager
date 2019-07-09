import base64
import logging
import os
import random
import string

from certbot.main import main as certbot_main


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


class CertbotGoogleDns:
    def __init__(self, email=None, staging=True, debug=True, dry_run=True):
        """
        :param email: Email used for registration and recovery contact. Use comma to register multiple emails
        :param staging: Use the staging server to obtain or revoke test (invalid) certificates; equivalent
        to --server https://acme-staging-v02.api.letsencrypt.org/directory
        :param debug: Show tracebacks in case of errors, and allow certbot- auto execution on experimental platforms
        :param dry_run: Perform a test run of the client, obtaining test (invalid) certificates but not saving them
        to disk
        """

        self.email = email
        self.staging = staging
        self.debug = debug
        self.dry_run = dry_run

        self.letsencrypt_dir = os.environ.get("LETSENCRYPT_DIR", "/letsencrypt")
        self.letsencrypt_log_dir = f"{self.letsencrypt_dir}/logs"
        self.letsencrypt_work_dir = f"{self.letsencrypt_dir}/work"
        self.google_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/gcp.json")
        self.letsencrypt_cert_location = f"{self.letsencrypt_dir}/live"
        self.dns_google_propagation_seconds = 90

        LOG.info(f"Initiating CertbotGoogleDns, letsencrypt_dir: {self.letsencrypt_dir}, letsencrypt_log_dir: "
                 f"{self.letsencrypt_log_dir}, letsencrypt_work_dir: {self.letsencrypt_work_dir}, google_credentials: "
                 f"{self.google_credentials}, letsencrypt_cert_location: {self.letsencrypt_cert_location}, "
                 f"dns_google_propagation_seconds: {self.dns_google_propagation_seconds}")

    def display_certificates(self):
        """
        Displays the list of managed certificates

        :return:
        """
        cli_args = [
            "certificates",
            f"--config-dir={self.letsencrypt_dir}",
            f"--logs-dir={self.letsencrypt_log_dir}",
            f"--work-dir={self.letsencrypt_work_dir}"
        ]

        certbot_main(cli_args=cli_args)

    def _read_certificate_from_file(self, domain):
        """
        Reads fullchain and privkey from fullchain.pem/privkey.pem from {letsencrypt_dir}/live/{domain} directory

        :param domain: domain
        :return: base64 of fullchain and privkey
        """
        domain = domain.replace("*.", "")  # remove wildcard
        r = {
            "fullchain": "",
            "privkey": "",
        }

        for name in r.keys():
            with open(os.path.join(self.letsencrypt_cert_location, domain, f"{name}.pem"), "r") as f:
                r[name] = base64.b64encode(f.read().encode("utf-8")).decode("utf-8")
        LOG.info(f"Read certificate result: {r}")
        return r

    def revoke_certificate(self, domain):
        """

        :param domain:
        :return:
        """

        cli_args = [
            "revoke",
            f"--cert-name={domain.replace('*.', '')}",
            f"--config-dir={self.letsencrypt_dir}",
            f"--logs-dir={self.letsencrypt_log_dir}",
            f"--work-dir={self.letsencrypt_work_dir}",
            "--delete-after-revoke"
        ]

        if self.email:
            LOG.info(f"Using email address in certificate revoke event, address: {self.email}.")
            cli_args.append(f"-m {self.email}")

        if self.staging:
            LOG.warning("Using letsencrypt staging.")
            cli_args.append("--staging")

        if self.debug:
            LOG.info("Using certbot debug mode.")
            cli_args.append("--debug")

        LOG.info(f"Using certbot cli args: {cli_args}")
        if self.dry_run:
            LOG.warning(f"Certbot does not support revoke certificate in dry_run mode, simulating.")
        else:
            certbot_main(cli_args=cli_args)

    def get_certificate(self, domain):
        """
        Allocate certificate from letsencrypt using google cloud dns plugin

        :param domain: domain
        :return: base64 of fullchain and privkey
        """

        cli_args = [
            "certonly",
            "--dns-google",
            f"--dns-google-credentials={self.google_credentials}",
            f"--dns-google-propagation-seconds={self.dns_google_propagation_seconds}",
            f"--config-dir={self.letsencrypt_dir}",
            f"--logs-dir={self.letsencrypt_log_dir}",
            f"--work-dir={self.letsencrypt_work_dir}",
            "--agree-tos",  # Agree to the ACME Subscriber Agreement (default: Ask)
            f"-d {domain}"
        ]

        if self.email:
            LOG.info(f"Using email address in certificate request, address: {self.email}.")
            cli_args.append(f"-m {self.email}")
        else:
            LOG.warning("Getting certificate without email address.")
            cli_args.append("--register-unsafely-without-email")

        if self.staging:
            LOG.warning("Using letsencrypt staging.")
            cli_args.append("--staging")

        if self.debug:
            LOG.info("Using certbot debug mode.")
            cli_args.append("--debug")

        if self.dry_run:
            LOG.info("Using certbot in dry run mode.")
            cli_args.append("--dry-run")

        LOG.info(f"Using certbot cli args: {cli_args}")
        certbot_main(cli_args=cli_args)

        if self.dry_run:
            LOG.warning(f"Using 'dry_run' option, simulating letsencrypt response.")
            dry_run_certificate = {
                "fullchain": "".join([random.choice(string.ascii_letters + string.digits) for _ in range(0, 128)]),
                "privkey": "".join([random.choice(string.ascii_letters + string.digits) for _ in range(0, 128)]),
            }
            result = dry_run_certificate

        else:
            # read certificate from file and convert it to base64
            result = self._read_certificate_from_file(domain)
        return result


if __name__ == "__main__":
    manager = CertbotGoogleDns(email="pahask8@gmail.com")
    manager.get_certificate(domain="*.pahask8.pw")
