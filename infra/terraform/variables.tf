variable "project_id" {
  description = "Google Cloud project that owns the GKE cluster."
  type        = string
  default     = "abdulproject-510307"
}

variable "region" {
  description = "Region for the regional GKE Autopilot cluster."
  type        = string
  default     = "asia-south1"
}

variable "cluster_name" {
  description = "Name of the GKE Autopilot cluster."
  type        = string
  default     = "ecommerce-learning"
}
