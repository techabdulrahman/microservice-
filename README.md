# E-Commerce Microservices on GKE

Production-oriented, cost-conscious e-commerce platform built incrementally with
FastAPI, PostgreSQL, Docker, Helm, GKE, Argo CD, GitHub Actions, and Grafana
Cloud.

## Project status

**Colorful Market demo is implemented for local development.** It includes an
illustrated storefront, API Gateway, Product Service, and Order Service. No
cloud resources or GKE workloads were changed.

See [architecture.md](./architecture.md) for the architecture, service
responsibilities, boundaries, and delivery plan.

## Run the demo locally

The easiest way is Python; this does not need Docker, Google Cloud, or a
Kubernetes cluster. Python 3.12 is recommended.

In PowerShell from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/run_demo.py
```

Open **http://localhost:8080**. Browse the colorful products, add an item to
your bag, enter a first name, and place a demo order. The order is simulated;
there is no payment or email collection. Stop the services with **Ctrl+C** in
the terminal running the demo.

The API is also available at:

- **http://localhost:8000/docs** — API Gateway
- **http://localhost:8001/docs** — Product Service
- **http://localhost:8002/docs** — Order Service

If running in Google Cloud Shell instead, use `python3` and start the frontend
on the preview interface:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
DEMO_HOST=0.0.0.0 python3 scripts/run_demo.py
```

In Cloud Shell, choose **Web Preview → Preview on port 8080**. Stop the demo
with Ctrl+C in the terminal.

### Optional: run with Docker Compose

Start Docker Desktop first, then run:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Open **http://localhost:8080**. Stop the containers with **Ctrl+C**, then run:

```powershell
docker compose -f docker/docker-compose.yml down
```

The product catalog and orders are in memory for this learning demo. Restarting
the services clears demo orders. This is not a production checkout: there is no
login, persistent database, real payment, or public deployment. Do not expose
the demo to the public internet or enter real customer information.

Run the unit tests with:

```powershell
python -m pytest tests
```

## Deploy the private demo to GKE

The **Build and deploy application to GKE** GitHub Actions workflow runs
automatically when changes to the application, Helm chart, tests, or workflow
are pushed to `main`. It runs the tests, builds and publishes the four images
to Artifact Registry using the commit SHA as the image tag, and upgrades the
Helm release in the existing `ecommerce` namespace. It can also be started
manually from **Actions → Build and deploy application to GKE → Run workflow**
on `main`.

Before using it:

1. Make sure the GKE cluster `ecommerce-learning` and the Artifact Registry
   repository `ecommerce-repo` exist in project `abdulproject-510307`, region
   `asia-south1`.
2. Configure Workload Identity Federation for this GitHub repository and a
   dedicated Google service account. Restrict the identity provider to this
   repository and the `gke-bootstrap` GitHub environment. Add the environment
   secrets `GCP_WORKLOAD_IDENTITY_PROVIDER` (full provider resource name) and
   `GCP_SERVICE_ACCOUNT` (service-account email). Do not use a long-lived
   service-account key.
3. Grant that service account `roles/artifactregistry.writer` and
   `roles/container.developer` in the project. It needs permission to push
   images and deploy namespaced workloads.
4. Ensure the GKE node service account can pull images from `ecommerce-repo`
   (typically grant it `roles/artifactregistry.reader` on the repository).
5. Connect to the cluster as an administrator and create the application
   namespace once:

   ```bash
   gcloud container clusters get-credentials ecommerce-learning \
     --region=asia-south1 \
     --project=abdulproject-510307
   kubectl create namespace ecommerce
   ```

6. Push a change to one of the workflow's watched paths on `main`, or run the
   workflow manually. A successful run means the images were pushed and Helm
   reported the workloads ready.

The deployment uses internal `ClusterIP` services and does not create public
ingress or TLS. For private access from Cloud Shell, run
`kubectl port-forward service/colorful-market-frontend 8080:8080
--namespace=ecommerce`, then use **Web Preview → Preview on port 8080**.

The manual image-promotion workflow below only records an image digest for the
separate GitOps flow; it is not needed for this direct GitHub Actions deploy.

### Manual Helm deployment (alternative)

This uses Cloud Build to build the four container images, Artifact Registry to
store them, and Helm to install the application. It does **not** create a
cluster, install Argo CD, create a public load balancer, or set up a TLS
certificate. Cloud Build and the Autopilot workloads can incur charges.

In Cloud Shell, if you have not cloned the repository yet:

```bash
git clone https://github.com/techabdulrahman/Microserviceapplicationgke.git
cd Microserviceapplicationgke
```

If you already cloned it, run `cd Microserviceapplicationgke` and
`git pull --ff-only origin main`. Then connect to the existing demo cluster:

```bash
gcloud config set project abdulproject-510307
gcloud container clusters get-credentials ecommerce-learning \
  --location=asia-south1 \
  --project=abdulproject-510307
kubectl config current-context
kubectl get namespace ecommerce
```

Confirm the context is
`gke_abdulproject-510307_asia-south1_ecommerce-learning` before continuing.
Build and publish the demo images to the existing `ecommerce-repo` Artifact
Registry repository:

```bash
PROJECT_ID=abdulproject-510307
REGION=asia-south1
REPOSITORY=ecommerce-repo
TAG="demo-$(git rev-parse --short HEAD)"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}"

gcloud builds submit frontend \
  --project="$PROJECT_ID" \
  --tag="${REGISTRY}/colorful-frontend:${TAG}"
gcloud builds submit api-gateway \
  --project="$PROJECT_ID" \
  --tag="${REGISTRY}/api-gateway:${TAG}"
gcloud builds submit services/product-service \
  --project="$PROJECT_ID" \
  --tag="${REGISTRY}/product-service:${TAG}"
gcloud builds submit services/order-service \
  --project="$PROJECT_ID" \
  --tag="${REGISTRY}/order-service:${TAG}"
```

Get the immutable image digests created by those builds:

```bash
FRONTEND_DIGEST=$(gcloud artifacts docker images describe \
  "${REGISTRY}/colorful-frontend:${TAG}" \
  --project="$PROJECT_ID" \
  --format='value(image_summary.digest)')
GATEWAY_DIGEST=$(gcloud artifacts docker images describe \
  "${REGISTRY}/api-gateway:${TAG}" \
  --project="$PROJECT_ID" \
  --format='value(image_summary.digest)')
PRODUCT_DIGEST=$(gcloud artifacts docker images describe \
  "${REGISTRY}/product-service:${TAG}" \
  --project="$PROJECT_ID" \
  --format='value(image_summary.digest)')
ORDER_DIGEST=$(gcloud artifacts docker images describe \
  "${REGISTRY}/order-service:${TAG}" \
  --project="$PROJECT_ID" \
  --format='value(image_summary.digest)')
```

Install the chart into the existing namespace and wait for the workloads:

```bash
helm upgrade --install colorful-market ./helm/ecommerce-demo \
  --namespace=ecommerce \
  --create-namespace \
  --wait --timeout=5m \
  --set-string "services.frontend.image=${REGISTRY}/colorful-frontend@${FRONTEND_DIGEST}" \
  --set-string "services.api-gateway.image=${REGISTRY}/api-gateway@${GATEWAY_DIGEST}" \
  --set-string "services.product-service.image=${REGISTRY}/product-service@${PRODUCT_DIGEST}" \
  --set-string "services.order-service.image=${REGISTRY}/order-service@${ORDER_DIGEST}"

kubectl get deployments,services,pods --namespace=ecommerce
kubectl rollout status deployment/colorful-market-frontend --namespace=ecommerce
kubectl rollout status deployment/colorful-market-api-gateway --namespace=ecommerce
kubectl rollout status deployment/colorful-market-product-service --namespace=ecommerce
kubectl rollout status deployment/colorful-market-order-service --namespace=ecommerce
```

All four Services are internal `ClusterIP` Services. View the storefront
privately through Cloud Shell:

```bash
kubectl port-forward service/colorful-market-frontend 8080:8080 \
  --namespace=ecommerce
```

Leave that command running, then choose **Web Preview → Preview on port 8080**
in Cloud Shell. Stop the port-forward with Ctrl+C. When you want to remove this
demo release, use `helm uninstall colorful-market --namespace=ecommerce`; this
does not delete the cluster or namespace.

This first GKE path uses Helm directly to keep the learning steps visible. The
Argo CD image-promotion workflow is separate and will not deploy this chart
until an Argo CD Application is configured.

### Install Argo CD with GitHub Actions

The **Install Argo CD on GKE** workflow bootstraps Argo CD in the existing
`ecommerce-learning` cluster; it does not create or modify the cluster itself.
Before running it:

1. Configure GitHub Actions Workload Identity Federation for this repository
   and a dedicated Google service account. Restrict the provider to this
   repository and the `gke-bootstrap` GitHub environment; do not use a
   long-lived service-account key.
2. Grant the service account only the GKE access needed to install a
   cluster-scoped Helm release. Bootstrap requires cluster-admin-equivalent
   permissions; restrict who can assume the account and approve runs.
3. Create the GitHub environment named `gke-bootstrap` and add these
   environment secrets:
   - `GCP_WORKLOAD_IDENTITY_PROVIDER`: full Workload Identity Provider resource
     name.
   - `GCP_SERVICE_ACCOUNT`: service-account email used for impersonation.
4. From the `main` branch, run **Actions → Install Argo CD on GKE → Run
   workflow**. The workflow installs the pinned Argo CD Helm chart into the
   `argocd` namespace. Re-running it upgrades/reconciles that Helm release.

The Argo CD server is installed as an internal `ClusterIP` service; this
workflow does not expose it publicly, configure SSO/repository credentials, or
create Argo CD Projects and Applications. Use a private access method such as
`kubectl port-forward` for initial administration, then configure authentication
and GitOps Applications before relying on it for deployments.

### Deploy Grafana Alloy to Grafana Cloud

The **Deploy Grafana Alloy to GKE** workflow installs Grafana Alloy as a
DaemonSet in the `monitoring` namespace of the existing GKE cluster. Alloy
tails Kubernetes container logs through the Kubernetes API, selecting only
pods on its own node to avoid duplicate ingestion, and forwards them to Grafana
Cloud Loki. It scrapes Prometheus metrics only from pods annotated with
`prometheus.io/scrape: "true"`; add the scrape port annotation and, when needed,
`prometheus.io/path` to opt a pod in. The current demo services do not expose
Prometheus metrics yet.

Add these secrets to the `gke-bootstrap` GitHub environment, along with the two
Workload Identity secrets described above:

- `GRAFANA_CLOUD_LOKI_URL`, `GRAFANA_CLOUD_LOKI_USERNAME`, and
  `GRAFANA_CLOUD_LOKI_PASSWORD` for a Grafana Cloud Logs/ Loki endpoint and
  credentials.
- `GRAFANA_CLOUD_PROMETHEUS_URL`, `GRAFANA_CLOUD_PROMETHEUS_USERNAME`, and
  `GRAFANA_CLOUD_PROMETHEUS_PASSWORD` for the Grafana Cloud Prometheus remote
  write endpoint and credentials.

Use the full remote-write and Loki push URLs provided by Grafana Cloud, and an
access policy token with only the required logs-write and metrics-write scopes.
The workflow creates or updates the `grafana-cloud` Kubernetes Secret from
these GitHub environment secrets, then installs the pinned Grafana Alloy Helm
chart using [monitoring/alloy/values.yaml](./monitoring/alloy/values.yaml).
Secret values are not stored in the repository. The Google service account
needs permission to manage the `monitoring` namespace and the chart's
cluster-wide pod-discovery RBAC resources.

## Deployment target

| Setting | Value |
|---|---|
| Google Cloud project | `abdulproject-510307` |
| Preferred region | `asia-south1` |
| Demo cluster | `ecommerce-learning` (Autopilot) |
| Kubernetes namespace | `ecommerce` |
| Existing image repository | `ecommerce-repo` (Artifact Registry) |
| Monitoring | Grafana Cloud |

The originally mentioned `ecommerce-cluster` did not appear in the cluster
listing you shared. These demo instructions use `ecommerce-learning`, which was
shown as your active cluster in Cloud Shell.

These are deployment targets, not authorization to create or modify resources.
Inspect the existing project and cluster before making infrastructure changes.

## GKE image promotion workflow

The **Promote image to GKE** workflow in `.github/workflows/deploy-gke.yml`
records a previously built image digest as the desired version for a service and
environment. Argo CD, not the GitHub runner, is responsible for applying that
desired state to GKE.

To run it, open **Actions → Promote image to GKE → Run workflow** on `main`,
select the environment and service, and provide the full immutable Artifact
Registry image reference, for example:

```text
asia-south1-docker.pkg.dev/abdulproject-510307/REPOSITORY/IMAGE@sha256:<64 lowercase hex characters>
```

The workflow commits an image override to
`environments/<environment>/<service>.yaml` using the chart's
`services.<service>.image` value, so the file can be passed to Helm with `-f`. Configure GitHub environment
protection rules for staging/production approvals as appropriate. No GCP
credentials are granted to the workflow; Argo CD must already be configured to
watch this repository and sync the corresponding chart.

**Current limitation:** Dockerfiles exist, but the new demo images have not yet
been built/published. A Helm chart exists, but Argo CD Applications are not
configured. The workflow can record a desired image, but it will not create
running workloads until images are published and Argo CD is configured. It does
not create, recreate, or modify the GKE cluster.

## Repository layout

```text
frontend/                         Customer web application
api-gateway/                      Public API entry point
services/
  user-service/                   Identity, registration, profiles
  product-service/                Product catalog and categories
  order-service/                  Order lifecycle and history
  inventory-service/              Stock and reservations
  payment-service/                Simulated, idempotent payments
  notification-service/           Simulated customer notifications
shared/                           Small, versioned shared Python packages
database/
  migrations/                     Database migration assets
  init/                           Local development initialization
docker/                           Local compose and development assets
helm/                             Deployable Helm charts
kubernetes/
  namespaces/                     Namespace resources
  networking/                     Ingress and network policies
  security/                       Service accounts and RBAC
  policies/                       Pod and cluster policy examples
argocd/
  applications/                   Environment Application definitions
  projects/                       Argo CD project boundaries
environments/
  dev/                            Development overrides
  staging/                        Staging overrides
  production/                     Production overrides
monitoring/
  dashboards/                     Grafana Cloud dashboard definitions
  alerts/                         Alert rules and recording rules
  otel/                           OpenTelemetry Collector configuration
.github/workflows/                CI and GitOps image update workflows
tests/                            Cross-service and acceptance tests
docs/                             Operational and user documentation
```

## Initial development principles

- Each service owns its API and data. Services do not query another service's
  tables.
- Keep cloud credentials out of Git. Use workload identity and Secret Manager
  integrations rather than service-account key files.
- GitHub Actions tests and publishes immutable images. Argo CD reconciles
  deployment configuration from Git; CI does not apply to the live cluster.
- Keep the learning environment cost-conscious, while documenting which
  production or GKE Standard features are optional.
- Inspect the current GCP project and cluster before suggesting or performing
  infrastructure changes.

Cloud deployment proceeds in the phases described in
[architecture.md](./architecture.md). The local demo is intentionally separate
from the existing GKE cluster until its container images and deployment
configuration have been prepared and reviewed.
#   m i c r o s e r v i c e -  
 