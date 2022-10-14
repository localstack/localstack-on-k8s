# LocalStack on Kubernetes

Sample repository that illustrates running LocalStack on Kubernetes (k8s).

## Prerequisites

This sample requires the following tools installed on your machine:
* Python 3.7+
* Docker
* `git`
* `kubectl`
* [`helm`](https://helm.sh/)
* [`serverless`](https://www.npmjs.com/package/serverless)

## Installing

To install the Python dependencies in a virtualenv:
```
make install
```

To create an embedded kubernetes (k3d) cluster in Docker and install LocalStack in it (via Helm):
```
make init
```

## Running the app

Once LocalStack is installed in the k8s cluster, we can deploy the sample app on the LocalStack instance:
```
make deploy
```

More details for running and using the sample app following soon...

## License

This code is available under the Apache 2.0 license.
