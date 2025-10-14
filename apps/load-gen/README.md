# Traffic generator app

This application is a continuous load generator designed to monitor the availability and performance of a list of external HTTP/S endpoints. It performs requests concurrently and exports detailed duration and response code metrics via a Prometheus endpoint.

## Key Features

- **Concurrency**: Uses Python's ThreadPoolExecutor to perform requests in parallel, overcoming the limitations of sequential execution in previous versions.
- **Prometheus Metrics**: Exposes request counts (by status code, including "502" for connection errors) and latency histograms on port 9090.
- **Configurable Rate**: The overall request rate (RPS) is configurable via a command-line argument.
- **Robustness**: Uses requests with robust error handling for timeouts and connection failures.
- **Custom CA Bundle Support**: Automatically respects the REQUESTS_CA_BUNDLE environment variable for handling custom or internal SSL certificates.

## Deployment Instructions (Docker)

Due to potential architecture conflicts (e.g., building on M1/M2 Mac but deploying on Linux AMD64), the build command uses the `--platform` flag for maximum compatibility.

### 1. Build the Docker Image
Use the following command to build the image and tag it directly for your public repository, ensuring it's compiled for the standard server architecture (`linux/amd64`):

```bash
docker build \
  --no-cache \
  --load \
  --platform linux/amd64 \
  -t arnausenserrich/load-gen:latest .
```

`--load`: Ensures the resulting image is loaded into your local Docker cache after building, preventing the "image does not exist" error.

`--platform linux/amd64`: CRITICAL for avoiding the `exec format error` on standard Linux servers.

### 2. Push to Docker Hub

Push the newly built image:

```bash
docker push arnausenserrich/load-gen:latest
```

### 3. Running the Container

The application **requires** the `URLS_LIST` environment variable to locate the list of endpoints to test. It also exposes Prometheus metrics on port 9090.

Required Environment Variables 
| Variable Name | Description | Example Value |
| -------- | ------- | ------- |
| `URLS_LIST` | **Required**. Path to the file containing the list of URLs inside the container. | `/config/urls` |
| `REQUESTS_CA_BUNDLE` | **Optional**. Path to a custom CA certificate bundle (PEM format) for internal SSL verification. | `/etc/secrets/ca/ca.crt` |

### Example Execution Command (For Local Docker Testing)

When running locally with Docker, you must map the path to simulate the Kubernetes structure:

```bash 
docker run -d \
  -p 9090:9090 \
  -v /path/to/your/local/urls.txt:/config/urls \
  -v /path/to/your/local/certs:/etc/secrets/ca \
  -e URLS_LIST=/config/urls \
  -e REQUESTS_CA_BUNDLE=/etc/secrets/ca/ca.crt \
  arnausenserrich/load-gen:latest
```

### Checking Metrics
Once the container is running, you can access the Prometheus metrics endpoint from your host machine:

http://localhost:9090/metrics

## Deployment Instructions (Kubernetes)

The application is designed to be deployed using Kustomize, which manages all necessary resources including the ConfigMap for the URL list.

### Kustomize Directory Structure

The `k8s` directory defines the base resources needed for deployment. The key files are:

```bash
resources:
- namespace.yaml
- sa.yaml
- ca-cert.yaml #(Optional Secret for REQUESTS_CA_BUNDLE)
- cm-urls.yaml
- deployment.yaml
- service.yaml

namespace: load-gen
```

### Deployment Steps

1. **Prepare Configuration**: Ensure your local `urls.txt` file is correctly referenced by the `cm-urls.yaml` ConfigMap manifest.
2. **Apply the Resources**: Use the idiomatic Kubernetes command to build and apply the Kustomize manifests.

```bash
kubectl apply -k k8s/
```

3. **Verify Deployment**: Check the status of the Pods in the load-gen namespace.

```bash
kubectl get pods -n load-gen
```
