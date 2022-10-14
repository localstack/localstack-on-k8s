import logging
import os.path

from localstack import config
from localstack.utils.run import run

LOG = logging.getLogger(__name__)

GIT_REPO_URL = "git@github.com:localstack/localstack-demo.git"


def _deploy_app():
    repo_dir = _clone_repo()
    run(["npm", "install"], cwd=repo_dir)
    run(["serverless", "deploy"], cwd=repo_dir, env_vars={"EDGE_PORT": "8081"})


def _clone_repo() -> str:
    repo_dir = os.path.join(config.TMP_FOLDER, "localstack-demo")
    if not os.path.exists(repo_dir):
        LOG.info("Cloning sample app repository")
        run(["git", "clone", GIT_REPO_URL], cwd=config.TMP_FOLDER)
    return repo_dir


def deploy():
    _clone_repo()
    _deploy_app()
