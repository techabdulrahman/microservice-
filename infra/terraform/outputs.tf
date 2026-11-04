output "cluster_name" {
  description = "Name of the GKE cluster."
  value       = google_container_cluster.autopilot.name
}

output "cluster_location" {
  description = "Region of the GKE cluster."
  value       = google_container_cluster.autopilot.location
}

output "get_credentials_command" {
  description = "Command to configure kubectl for this cluster."
  value       = "gcloud container clusters get-credentials ${google_container_cluster.autopilot.name} --location=${google_container_cluster.autopilot.location} --project=${var.project_id}"
}
