# Deploy Go web app in Kubernetes

## Create the Docker image

First, we need to containerize our previous webserver application to be able to run it in Kubernetes. We will need a `Dockerfile` 
to instruct how we want to build it. Once it's created, we can run:

```bash
cd app
docker build -t webserver .
```

We can see the generated image by running:

```bash
docker image ls
---
webserver     latest    d94f50a32c7d   11 seconds ago   292MB
```

And we will need to push it to a repository. In my case I will use Docker Hub. For this, we will need to rename the image:

```bash
docker tag d94f50a32c7d docker.io/arnausenserrich/webserver:v1
---
arnausenserrich/webserver   latest    d94f50a32c7d   8 minutes ago   292MB
```

And push it to the repository:

```bash
docker push docker.io/arnausenserrich/webserver:v1
```

## Deploy to Kubernetes

We could just use `kubectl` comands to run this image in Kubernetes, but let's create a deployment to easily manage it. Let's apply it:

```bash
kubectl apply -f deployment.yaml
```

Next step is create a service, so all the endpoints can be accessible from inside the cluster with a fixed fqdn:

```bash
kubectl apply -f service.yaml
```

Now we can also expose it, in our case as load balancer service, so it can be accessible from the Internet:

```bash
kubectl apply -f service.yaml
```

Wait few seconds so the load balancer is created and get the public IP:

```bash
kubectl get svc pub-webserver --output jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Now this application is accessible publicly.
