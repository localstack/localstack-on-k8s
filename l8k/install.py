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
        cmd = [bin_file, "kubeconfig", "merge", "-o", KUBE_CONFIG_FILE]
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

    cmd = ["helm", "install", "localstack", "localstack/localstack"]
    run(cmd)


def _create_ingress():
    # TODO: potentially move to Helm chart?
    with tempfile.NamedTemporaryFile() as f:
        f.write(to_bytes(KUBE_INGRESS))
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

    LOG.info("Installing LocalStack Helm chart in kube cluster")
    _install_helm_chart()
    _create_ingress()

    LOG.info("Waiting for LocalStack to be ready")
    _wait_for_ls_ready()

    LOG.info("Done.")
