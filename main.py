import logging
import os
from datetime import datetime

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

from plugins.certbot_letsencrypt_dns import CertbotGoogleDns


logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(levelname)s "
                                               "%(module)s - %(funcName)s: %(message)s")
LOG = logging.getLogger(__name__)


class CertificateController:
    def __init__(self, debug):
        self._group = "development.io"
        self._plural = "certificates"
        self._version = "v1alpha1"
        self._success_status = "Success"
        self._failed_status = "Failed"
        self.debug = debug

        self._setup_client()

    @staticmethod
    def _setup_client():
        if os.environ.get("KUBECONFIG"):
            config_file = os.environ.get("KUBECONFIG")
            config.load_kube_config(config_file=config_file)
        elif os.environ.get("LOCAL_K8S"):
            config.load_kube_config()
        else:
            LOG.debug(f"Using k8s service account access")
            config.load_incluster_config()

    def _process_delete_event(self, body: dict):
        """

        :param body: k8s certificate body
        :return:
        """
        LOG.info(f"Processing {self._plural} delete event, body: {body}")
        email = body["spec"].get("email")
        domain = body["spec"].get("domain")
        staging = body["spec"].get("staging")
        dry_run = body["spec"].get("dry_run")

        # revoke certificate
        letsencrypt_manager = CertbotGoogleDns(email=email, staging=staging, debug=self.debug, dry_run=dry_run)
        letsencrypt_manager.revoke_certificate(domain=domain)

        name = body["metadata"]["name"]
        namespace = body["metadata"]["namespace"]
        self._delete_secret(name, namespace)

    def _change_certificate_status(self, name: str, namespace: str, body: dict):
        """

        :param name: k8s certificate name
        :param namespace: namespace
        :param body: k8s certificate body
        :return:
        """
        try:
            # update customObject status
            client.CustomObjectsApi().replace_namespaced_custom_object_status(
                group=self._group,
                version=self._version,
                namespace=namespace,
                plural=self._plural,
                name=name,
                body=body
            )
        except ApiException as e:
            LOG.error(f"Exception when calling CustomObjectsApi->patch_cluster_custom_object, error: {e}")

    def _process_add_event(self, body: dict):
        """

        :param body:
        :return:
        """
        LOG.info(f"Processing {self._plural} add event, body: {body}")

        name = body["metadata"]["name"]
        namespace = body["metadata"]["namespace"]

        body["status"] = {
            "status": self._success_status,
        }

        email = body["spec"].get("email")
        domain = body["spec"].get("domain")
        staging = body["spec"].get("staging")
        dry_run = body["spec"].get("dry_run")

        try:
            letsencrypt_manager = CertbotGoogleDns(email=email, staging=staging, debug=self.debug, dry_run=dry_run)
            certificate_data = letsencrypt_manager.get_certificate(domain=domain)
        except Exception as e:
            LOG.error(f"Letsenrypt plugin create failed, updating certificate status, error:: {e}")
            body["status"]["status"] = self._failed_status
            self._change_certificate_status(name, namespace, body)
            return

        ssl_certificate = certificate_data.get("fullchain")
        ssl_certificate_key = certificate_data.get("privkey")

        # create or update existing secret with certificate and key
        error = self._create_secret(name=name, namespace=namespace, ssl_certificate=ssl_certificate,
                                    ssl_certificate_key=ssl_certificate_key, domain=domain)
        if error:
            body["status"]["status"] = self._failed_status
            body["status"]["message"] = error

        self._change_certificate_status(name, namespace, body)

    @staticmethod
    def _generate_secret_body(name, namespace, domain, data):
        """

        :param name: secret name
        :param namespace: namespace
        :param domain: domain
        :param data: secret data
        :return:
        """
        body = client.V1Secret(
            api_version="v1",
            kind="Secret",
            type="kubernetes.io/tls",
            data=data,
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=namespace,
                labels={
                    "domain": domain.replace("*.", ""),
                }
            )
        )
        return body

    def _create_secret(self, name: str, namespace: str, ssl_certificate: str, ssl_certificate_key: str,
                       domain: str) -> str:
        """

        :param name: secret name
        :param namespace: namespace
        :param ssl_certificate: ssl certificate
        :param ssl_certificate_key: ssl certificate key
        :param domain: domain
        :return:
        """
        LOG.info(f"Creating or updating secret, name: {name}, domain: {domain}")

        error = ""

        data = {
            "tls.crt": ssl_certificate,
            "tls.key": ssl_certificate_key
        }

        body = self._generate_secret_body(name=name, namespace=namespace, domain=domain, data=data)

        # backup existing secret if exists
        try:
            # k8s api returns ApiException: Not Found if secret object does not exist
            secret = client.CoreV1Api().read_namespaced_secret(name=name, namespace=namespace)
            # making a backup
            backup_name = f"{name}-{datetime.now().strftime('%Y%m%d%H%M')}"
            old_data = secret.data
            backup_body = self._generate_secret_body(name=backup_name, namespace=namespace, domain=domain,
                                                     data=old_data)
            # delete existing secret
            client.CoreV1Api().delete_namespaced_secret(name=name, namespace=namespace)
            client.CoreV1Api().create_namespaced_secret(namespace=namespace, body=backup_body)
        except client.rest.ApiException as e:
            if e.reason == "Not Found":
                LOG.warning(f"Secret not found, secret: {name}, namespace: {namespace}")
            else:
                LOG.error(f"Got error while trying to read the secret, name: {name}, namespace: {namespace}")
                error = e

        LOG.info(f"Trying to create a secret, name: {name}")
        # try to create a new secret
        try:
            client.CoreV1Api().create_namespaced_secret(namespace=namespace, body=body)
            return error
        except ApiException as e:
            LOG.error(f"Unable to create secret, name: {name}, body: {body}, error: {e}")
            error = e.body
            return error

    @staticmethod
    def _delete_secret(name: str, namespace: str):
        """

        :param name: secret name
        :param namespace: namespace
        :return:
        """
        try:
            body = client.V1DeleteOptions()
            client.CoreV1Api().delete_namespaced_secret(name=name, namespace=namespace, body=body)
        except ApiException as e:
            LOG.error(f"Unable to delete secret, name: {name}, namespace: {namespace}, error: {e}")

    def _display_certificates(self):
        """
        Displays managed certificates

        :return:
        """
        letsencrypt_manager = CertbotGoogleDns(debug=self.debug)
        letsencrypt_manager.display_certificates()

    def run(self):
        while True:
            stream = watch.Watch().stream(
                func=client.CustomObjectsApi().list_cluster_custom_object,
                group=self._group,
                version=self._version,
                plural=self._plural
            )
            try:
                for event in stream:
                    obj = event["object"]
                    event_type = event["type"]  # ADDED, MODIFIED, DELETED
                    metadata = obj.get("metadata")
                    name = metadata["name"]
                    LOG.info(f"operation: {event_type}, name: {name}")
                    if event_type == "ADDED":
                        if obj.get("status"):
                            LOG.warning(f"Skipping {event_type} for {name} certificate because of completed status, "
                                        f"status: {obj['status']}")
                        else:
                            self._process_add_event(obj)
                    elif event_type == "MODIFIED":
                        LOG.warning(f"Not implemented k8s event: {event_type}")
                    elif event_type == "DELETED":
                        self._process_delete_event(obj)

                    # display managed certificates
                    self._display_certificates()
            except Exception as e:
                LOG.error(f"Error occured during event: {event}, error: {e}")


if __name__ == "__main__":
    debug = os.environ.get("DEBUG")
    watch_timeout = int(os.environ.get("WATCH_TIMEOUT", "30"))
    controller = CertificateController(debug=debug)
    controller.run()
