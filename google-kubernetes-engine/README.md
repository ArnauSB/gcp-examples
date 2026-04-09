# Deploy Go web app in Kubernetes

## Create the Docker image

First, we need to containerize our previous webserver application to be able to run it in Kubernetes. We will need a `Dockerfile` 
to instruct how we want to build it. The Dockerfile uses a multi-stage build: Go toolchain compiles the binary in the first stage, and only the static binary is copied into a minimal Alpine image, keeping the final image small. Once it's created, we can run:

```bash
cd app
docker build -t webserver .
```

We can see the generated image by running:

```bash
docker image ls
---
webserver     latest    d94f50a32c7d   11 seconds ago   ~20MB
```

The app exposes the following endpoints:

| Path | Description |
|------|-------------|
| `/` | Hostname, remote addr, user-agent, and env vars (`PROJECT_ID`, `ZONE`, `INSTANCE_ID`) |
| `/headers` | All request headers as JSON |
| `/env` | All environment variables as JSON — useful for verifying K8s ConfigMaps/Secrets |
| `/info` | Live GCP instance metadata (hostname, zone, machine-type, id) |
| `/healthz` | Health check — returns `{"status":"ok"}` — used for liveness/readiness probes |

All endpoints return `application/json`. Logs are emitted as structured JSON to stdout, compatible with Google Cloud Logging.

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
kubectl apply -f lb-service.yaml
```

Wait few seconds so the load balancer is created and get the public IP:

```bash
kubectl get svc pub-webserver --output jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Now this application is accessible publicly.
