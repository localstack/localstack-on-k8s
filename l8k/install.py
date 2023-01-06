import json
import logging
import os
import tempfile

import requests
from localstack import config
from localstack.utils.files import chmod_r
from localstack.utils.http import download
from localstack.utils.platform import get_arch, is_linux, is_mac_os
from localstack.utils.run import is_command_available, run
from localstack.utils.strings import to_bytes
from localstack.utils.sync import retry

LOG = logging.getLogger(__name__)

# URL pattern for k3d binaries
K3D_VERSION = "v5.4.6"
K3D_URL_PATTERN = f"https://github.com/rancher/k3d/releases/download/{K3D_VERSION}/k3d-<os-arch>"
# default k3d configs
K3D_LB_PORT = int(os.environ.get("K3D_LB_PORT") or 8081)
K3D_CLUSTER_NAME = "ls-cluster"
K3D_LB_PORT_INTERNAL = 6443
K3D_STARTUP_TIMEOUT = 60
K3D_LB_STARTUP_TIMEOUT = 360

KUBE_CONFIG_FILE = os.path.expanduser("~/.kube/config")

KUBE_INGRESS = """
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: localstack
  annotations:
    ingress.kubernetes.io/ssl-redirect: "false"
spec:
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: localstack
            port:
              number: 4566
"""

K3D_ACCOUNT_PERMS = """
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: localstack
subjects:
- kind: ServiceAccount
  name: localstack
  namespace: default
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: ""
"""


class KubeCluster:
    def install(self):
        os_name = "linux" if is_linux() else "darwin" if is_mac_os() else None
        os_arch = get_arch()
        if not os_name:
            raise Exception(
                "Unsupported operating system (currently only Linux/MacOS are supported)"
            )
        bin_file = os.path.join(config.TMP_FOLDER, f"k3d.{os_name}.bin")
        if not os.path.exists(bin_file):
            os_arch = f"{os_name}-{os_arch}"
            download_url = K3D_URL_PATTERN.replace("<os-arch>", os_arch)
            download(download_url, bin_file)
            chmod_r(bin_file, 0o777)
        return bin_file

    def create(self):
        bin_file = self.install()

        # check if cluster exists
        clusters = json.loads(run([bin_file, "cluster", "list", "-o", "json"]))
        matching = [c for c in clusters if c["name"] == K3D_CLUSTER_NAME]
        if matching:
            LOG.debug("Target k3d cluster '%s' already exists", K3D_CLUSTER_NAME)
            return

        cmd = [
            bin_file,
            "cluster",
            "create",
            K3D_CLUSTER_NAME,
            "--api-port",
            str(K3D_LB_PORT_INTERNAL),
            "-p",
            f"{K3D_LB_PORT}:80@loadbalancer",
        ]
        LOG.debug("Creating k8d cluster: %s", " ".join(cmd))
        run(cmd)

    def wait_for(self):
        lb_url = f"http://localhost:{K3D_LB_PORT}"
        LOG.debug("Waiting for connectivity on EKS load balancer from container: %s", lb_url)
        try:
            retries = int(K3D_LB_STARTUP_TIMEOUT / 2)
            retry(lambda: requests.get(lb_url, verify=False), sleep=2, retries=retries)
        except Exception as e:
            raise Exception(f"Error waiting for k3d cluster to become available: {e}")

    def write_kubectl_config(self):
        bin_file = self.install()
        cmd = [bin_file, "kubeconfig", "merge", "-o", KUBE_CONFIG_FILE, K3D_CLUSTER_NAME]
        run(cmd)


def _create_cluster():
    cluster = KubeCluster()
    cluster.install()
    cluster.create()
    cluster.wait_for()
    cluster.write_kubectl_config()


def _install_helm_chart():
    try:
        cmd = ["helm", "repo", "add", "localstack", "https://localstack.github.io/helm-charts"]
        run(cmd)
    except Exception as e:
        if "already exists" not in str(e):
            raise

    env_vars = {
        "DISABLE_CORS_CHECKS": "1",
        "DNS_ADDRESS": "0",
    }

    if os.getenv("LOCALSTACK_API_KEY"):
        env_vars["LOCALSTACK_API_KEY"] = os.getenv("LOCALSTACK_API_KEY")
        env_vars["PROVIDER_OVERRIDE_LAMBDA"] = "asf"
        env_vars["LAMBDA_RUNTIME_EXECUTOR"] = "kubernetes"
        env_vars["LOCALSTACK_K8S_SERVICE_NAME"] = "default"
        env_vars["LOCALSTACK_K8S_NAMESPACE"] = "default"

    if os.getenv("LAMBDA_RUNTIME_IMAGE_MAPPING"):
        env_vars["LAMBDA_RUNTIME_IMAGE_MAPPING"] = os.getenv("LAMBDA_RUNTIME_IMAGE_MAPPING")

    cmd = [
        "helm",
        "install",
        "localstack",
        "localstack/localstack",
        "--set",
        "debug=true",
    ]

    i = 0
    for key, value in env_vars.items():
        cmd += [
            "--set",
            f"extraEnvVars[{i}].name={key}",
            "--set-string",
            f"extraEnvVars[{i}].value={value}",
        ]
        i += 1

    run(cmd)


def _create_ingress():
    # TODO: potentially move to Helm chart?
    _apply_k8s_config(KUBE_INGRESS)


def _create_rbac_auth():
    # TODO: potentially move to Helm chart?
    _apply_k8s_config(K3D_ACCOUNT_PERMS)


def _apply_k8s_config(config_str: str):
    with tempfile.NamedTemporaryFile() as f:
        f.write(to_bytes(config_str))
        f.flush()
        run(["kubectl", "apply", "-f", f.name])


def _wait_for_ls_ready():
    def _check_ready():
        result = requests.get(health_url)
        assert result.ok

    health_url = f"http://localhost:{K3D_LB_PORT}/health"
    retry(_check_ready, sleep=2, retries=60)


def _check_prereqs():
    prereqs = ["kubectl", "helm", "git", "serverless"]
    for command in prereqs:
        if not is_command_available(command):
            raise Exception(f"Please install the '{command}' command line interface")


def install():
    _check_prereqs()

    LOG.info("Create local k3d Kubernetes cluster inside Docker")
    _create_cluster()

    LOG.info("Installing LocalStack Helm chart in Kubernetes cluster")
    _install_helm_chart()
    _create_ingress()

    LOG.info("Waiting for LocalStack to be ready")
    _wait_for_ls_ready()

    LOG.info("Done.")
