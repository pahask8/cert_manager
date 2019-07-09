# k8s ssl certificate manager
k8s certification manager automation

## Installation

### Helm

```bash
cert_manager/helm/cert_manager $ helm install -n cert-manager . --wait --namespace=test
NAME:   cert-manager
LAST DEPLOYED: Sat Jul  6 18:54:41 2019
NAMESPACE: test
STATUS: DEPLOYED

RESOURCES:
==> v1/ClusterRole
NAME          AGE
cert-manager  17s

==> v1/ClusterRoleBinding
NAME          AGE
cert-manager  17s

==> v1/Deployment
NAME          READY  UP-TO-DATE  AVAILABLE  AGE
cert-manager  1/1    1           1          17s

==> v1/PersistentVolumeClaim
NAME          STATUS  VOLUME                                    CAPACITY  ACCESS MODES  STORAGECLASS  AGE
cert-manager  Bound   pvc-2fb0bd38-a05a-11e9-beef-42010a020007  1Gi       RWO           standard      17s

==> v1/Pod(related)
NAME                           READY  STATUS   RESTARTS  AGE
cert-manager-59c5f589cd-s7rhm  1/1    Running  0         17s

==> v1/Secret
NAME          TYPE    DATA  AGE
cert-manager  Opaque  1     17s

==> v1/ServiceAccount
NAME          SECRETS  AGE
cert-manager  1        17s

==> v1beta1/CustomResourceDefinition
NAME                         AGE
certificates.development.io  17s
```

### Docker-compose

Build:
```yaml
$ docker-compose build
Building certmanager
Step 1/12 : FROM python:3.6
..................
Successfully built 1da16cef2d37
Successfully tagged cert_manager_certmanager:latest
```

Put your GCP credentials file to `secrets/gcp.json`

Run:
```bash
$ docker-compose up
Recreating certmanager ... done
Attaching to certmanager
```

## Usage
| Modify `examples/certificate-example.yaml` file:
```yaml
apiVersion: development.io/v1alpha1
kind: Certificate
metadata:
  name: pavelt
spec:
  domain: "*.example.com"
  email: "test@test.com"  # Email used for registration and recovery contact. Use comma to register multiple emails
  staging: "True"  # Use the staging server to obtain or revoke test (invalid) certificates; equivalent to --server https://acme-staging-v02.api.letsencrypt.org/directory
  debug: "True"  # Show tracebacks in case of errors, and allow certbot- auto execution on experimental platforms
  dry_run: "True"  # Perform a test run of the client, obtaining test (invalid) certificates but not saving them to disk

```
Create example object:
```bash
$ kubectl create -f examples/certificate-example.yaml
certificate.development.io "examplecom" created
$
```
Verify:
```yaml
$ kubectl create -f /examples/example-pod.yaml
pod/examplecom created

$ kubectl exec -it examplecom sh
/ # ls -la /certificate/
total 4
drwxrwxrwt    3 root     root           120 Jul  7 04:50 .
drwxr-xr-x    1 root     root          4096 Jul  7 04:50 ..
drwxr-xr-x    2 root     root            80 Jul  7 04:50 ..2019_07_07_04_50_22.724996376
lrwxrwxrwx    1 root     root            31 Jul  7 04:50 ..data -> ..2019_07_07_04_50_22.724996376
lrwxrwxrwx    1 root     root            14 Jul  7 04:50 tls.crt -> ..data/tls.crt
lrwxrwxrwx    1 root     root            14 Jul  7 04:50 tls.key -> ..data/tls.key
/ #
/ # head /certificate/tls.crt -n 2
-----BEGIN CERTIFICATE-----
MIIFMDCCBBigAwIBagIggAPoovAtMaAN9ek68izBG+hdkjANBgaqhkiG9w0BAQsF
/ #
/ # head /certificate/tls.key -n2
-----BEGIN PRIVATE KEY-----
MIIEvdIBADAnBgkghkiG9w0BaQEFAAScBKcwggSjAgEAAoIgAQCqdZF2YS+aXzQq
/ #
```
