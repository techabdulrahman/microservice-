terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "application_images" {
  project       = var.project_id
  location      = var.region
  repository_id = "ecommerce-repo"
  description   = "E-commerce application images"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_artifact_registry_repository_iam_member" "image_publisher" {
  project    = google_artifact_registry_repository.application_images.project
  location   = google_artifact_registry_repository.application_images.location
  repository = google_artifact_registry_repository.application_images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:github-gke-deployer@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_container_cluster" "autopilot" {
  name                = var.cluster_name
  location            = var.region
  enable_autopilot    = true
  deletion_protection = false

  release_channel {
    channel = "REGULAR"
  }

  depends_on = [google_project_service.required]
}
