> [!IMPORTANT]
> This repository has been archived.
> 
> Please use our official helm chart (https://github.com/localstack/helm-charts) to deploy LocalStack to kubernetes.

# LocalStack on Kubernetes

Sample repository that illustrates running LocalStack on Kubernetes (k8s).

## Prerequisites

This sample requires the following tools installed on your machine:
* Python 3.7+
* [`awslocal`](https://github.com/localstack/awscli-local)
* [Docker](https://www.docker.com)
* [Git](https://git-scm.com)
* [Helm](https://helm.sh)
* [`kubectl`](https://kubernetes.io/docs/tasks/tools/#kubectl)
* [Serverless](https://www.npmjs.com/package/serverless)

## Installing

To install the Python dependencies in a virtualenv:
```
make install
```

To create an embedded Kubernetes (k3d) cluster in Docker and install LocalStack in it (via Helm):
```
make init
```

After initialization, your `kubectl` command-line should be automatically configured to point to the local cluster context:
```
$ kubectl config current-context
k3d-ls-cluster
```

## Deploying the sample app

Once LocalStack is installed in the Kubernetes cluster, we can deploy the sample app on the LocalStack instance:
```
make deploy
```

## Interacting with the sample app

Once the sample app is deployed, the Kubernetes environment should contain the following resources:

```
$ kubectl get all
NAME                              READY   STATUS    RESTARTS   AGE
pod/localstack-6fd5b98f59-zcx2t   1/1     Running   0          5m

NAME                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)                         AGE
service/kubernetes   ClusterIP   10.43.0.1       <none>        443/TCP                         5m
service/localstack   NodePort    10.43.100.167   <none>        4566:31566/TCP,4571:31571/TCP   5m

NAME                         READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/localstack   1/1     1            1           5m

NAME                                    DESIRED   CURRENT   READY   AGE
replicaset.apps/localstack-6fd5b98f59   1         1         1       5m
```

The LocalStack instance should be available via the local ingress port `8081`. We can verify that the resources were successfully created by running a few `awslocal` commands against the local endpoint:
```
$ awslocal sqs --endpoint-url=http://localhost:8081 list-queues
{
    "QueueUrls": [
        "http://localhost:8081/000000000000/requestQueue"
    ]
}
$ awslocal apigateway --endpoint-url=http://localhost:8081 get-rest-apis
{
    "items": [
        {
            "id": "ses2pi5oap",
            "name": "local-localstack-demo",
...
```

We can then use a browser to open the [Web UI](http://localhost:8081/archive-bucket/index.html), which should have been deployed to an S3 bucket inside LocalStack. The Web UI can be used to interact with the sample application, send new requests to the backend, inspect the state of existing requests, etc.

## License

This code is available under the Apache 2.0 license.
