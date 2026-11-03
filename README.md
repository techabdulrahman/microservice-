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

## Optional: deploy the private demo to your existing GKE cluster

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
been built/published. This repository still needs Helm charts and Argo CD
Applications. The workflow can record a desired image, but it will not create
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