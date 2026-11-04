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

## Deploy the private demo with GitOps

GitHub Actions builds and publishes the four application images, then commits
their immutable Artifact Registry digests to `environments/dev/`. Argo CD
watches the `main` branch and synchronizes the Helm chart from that Git state
to the existing GKE cluster. GitHub Actions does not apply the application
Helm release directly.

### Recreate the GKE cluster with Terraform

The Terraform configuration in `infra/terraform/` creates the regional
Autopilot cluster and ensures the required GKE APIs are enabled. It does not
manage or delete the existing Artifact Registry repository, container images,
GitHub Workload Identity Federation, service accounts, or IAM bindings.

Run these commands from the repository root in Cloud Shell after the old
`ecommerce-learning` cluster has been deleted:

```bash
gcloud config set project abdulproject-510307
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
terraform -chdir=infra/terraform output -raw get_credentials_command
```

Run the printed `gcloud container clusters get-credentials ...` command, then
verify the cluster with `kubectl get nodes`. Keep `infra/terraform/terraform.tfstate`
in the same working directory for future Terraform runs; it is intentionally
ignored by Git and must not be deleted if Terraform will manage this cluster.
Do not run `terraform destroy` unless you intend to delete the GKE cluster.

After the cluster is ready, run **Actions → Install Argo CD on GKE** from
`main`. That workflow installs Argo CD and syncs the application from the
existing image digests. Run **Actions → Deploy Grafana Alloy to GKE** to
reinstall telemetry collection. The `gke-bootstrap` GitHub environment,
Grafana secrets, and IAM/WIF configuration must remain in place.

### One-time prerequisites

The GKE Autopilot cluster `ecommerce-learning`, Artifact Registry repository
`ecommerce-repo`, and `ecommerce` namespace should exist in project
`abdulproject-510307`, region `asia-south1`. The GKE node service account must
have `roles/artifactregistry.reader` on the image repository.

Configure GitHub Actions Workload Identity Federation for this repository and
the `gke-deploy` and `gke-bootstrap` GitHub environments. Keep image publishing
and cluster administration in separate environments: the existing
`github-gke-deployer` account needs only `roles/artifactregistry.writer`, and
its `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` secrets belong
in `gke-deploy`. Do not use a long-lived service-account key.
Allow GitHub Actions to write repository contents, and ensure branch protection
permits its bot to commit the generated dev image overrides to `main`.

The existing Workload Identity provider condition currently allows only
`gke-bootstrap`. Update it to allow both protected deployment environments:

```bash
PROJECT_ID=abdulproject-510307
POOL_ID=github-actions
PROVIDER_ID=github

gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" \
  --attribute-condition="assertion.repository == 'techabdulrahman/microservice-' && (assertion.environment == 'gke-bootstrap' || assertion.environment == 'gke-deploy')"
```

The Argo CD bootstrap workflow needs elevated cluster permissions to install
Argo CD's cluster-scoped resources. Use a separate bootstrap account rather
than elevating the image publisher:

```bash
PROJECT_ID=abdulproject-510307
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
BOOTSTRAP_SA=github-gke-bootstrap
BOOTSTRAP_EMAIL="${BOOTSTRAP_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
POOL_ID=github-actions

gcloud iam service-accounts create "$BOOTSTRAP_SA" \
  --project="$PROJECT_ID" \
  --display-name="GitHub GKE bootstrap"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BOOTSTRAP_EMAIL}" \
  --role="roles/container.admin"
gcloud iam service-accounts add-iam-policy-binding "$BOOTSTRAP_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/techabdulrahman/microservice-"
```

In the `gke-bootstrap` GitHub environment, add
`GCP_BOOTSTRAP_SERVICE_ACCOUNT` with value
`github-gke-bootstrap@abdulproject-510307.iam.gserviceaccount.com` and the
`GCP_WORKLOAD_IDENTITY_PROVIDER` secret. Also add
`GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` to `gke-deploy`.
Restrict access to `gke-bootstrap` and protect approvals. The `container.admin`
role is powerful; remove its project binding after bootstrap if you do not
need to rerun the bootstrap workflow.

### Bootstrap and ongoing deployments

1. Push the GitOps workflow and Argo CD manifests to `main`.
2. Wait for **Build images and update GitOps manifests** to finish. It runs
   tests, publishes images, and commits their digests to the four dev override
   files. This must finish before the first Argo CD sync so the existing
   deployment is not replaced with stale image references. The bootstrap
   workflow checks that each file points to its expected image and fails
   safely if this step has not finished.
3. In **Actions → Install Argo CD on GKE → Run workflow**, select `main`.
   It installs Argo CD, registers the restricted `colorful-market` project
   and Application, then waits for the application to become Synced and
   Healthy. The application adopts the existing `colorful-market` Helm
   resources; after this, do not run `helm upgrade` for that release.
4. For future changes, push to `main`. The build workflow updates image digests
   in Git and Argo CD reconciles those changes to GKE. The manual
   **Promote image to GKE** workflow also updates a dev image override that
   Argo CD watches.

The Argo CD server and app services are internal-only. For private storefront
access from Cloud Shell, run:

```bash
kubectl port-forward service/colorful-market-frontend 8080:8080 \
  --namespace=ecommerce
```

Then choose **Web Preview → Preview on port 8080**. If the GitHub repository is
private, configure repository credentials in Argo CD before registering the
Application; never commit a GitHub token to this repository.

### Manual Helm deployment (alternative)

Use the following manual Helm procedure only before Argo CD takes ownership of
the `colorful-market` release. Do not run `helm upgrade` for that release after
the GitOps Application is synced.

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
`services.<service>.image` value. The current Argo CD Application watches the
`dev` environment only; staging and production need their own Application
definitions and approval policies before those overrides deploy.

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