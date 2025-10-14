# Secure Test Server (HTTPS)

This component provides a simple, self-contained HTTPS server used as a secure target for the `load-gen` traffic generator. It is designed to be fully deployable using standard Docker and Kubernetes manifests, relying on embedded certificates rather than runtime secrets.

The server listens on port 8080 and requires a valid TLS certificate (`server.crt`) and private key (`server.key`) to start.

## Prerequisites and Certificate Setup

Before building the Docker image, you must generate the server's TLS certificate, signed by the same Private CA that the `load-gen` client trusts.

1. Generate Server Certs

Execute the `ssl_setup.sh` script, providing the internal Kubernetes Service FQDN as the hostname.

**Required Files**: You must have the following files available in the `src/` folder and `ca.crt` in the app root:

- `server.crt` (Server Public Key, signed by CA)
- `server.key` (Server Private Key)

Example Execution:

```bash
# This generates server.crt, server.key, ca.crt, and ca.key
./ssl_setup.sh secure-server.default.svc.cluster.local
```

## Docker Deployment

The final image will contain the `server.crt` and `server.key` required to start the HTTPS listener.

1. Build and Push Image

Use the Dockerfile for the secure server to build and tag the image, assuming the necessary certificate files are in the context directory.

```bash
# Build the secure server image using the specific Dockerfile
docker build --no-cache --load --platform linux/amd64 -t arnausenserrich/secure-server:latest -f Dockerfile .

# Push the image to the registry
docker push arnausenserrich/secure-server:latest
```

2. Local Test Execution

To test the server locally, you must map the port and ensure the required certificates are available in the current directory (or mounted):

```bash
# Run the server and expose port 8080
docker run -d -p 8080:8080 arnausenserrich/secure-server:latest
```

## Kubernetes Deployment (Kustomize)

The server deployment relies on simple Deployment and Service objects, as the certificates are embedded.

1. Deployment Strategy

Since the certificates are embedded, the deployment manifest does not require `volumes` or `volumeMounts` for TLS data.

Apply the Deployment and Service by running:

```bash
kubectl apply -f k8s/conf.yaml
```

2. Access Information

The internal URL for the load-gen client to test is:

https://secure-server.default.svc.cluster.local
