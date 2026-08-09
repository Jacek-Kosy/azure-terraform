variable "name" {
  description = "Name of the Container App. Also prefixes the identity, environment, and Log Analytics workspace."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to create everything in"
  type        = string
}

variable "location" {
  description = "Azure region. Container Apps is not available everywhere; check with `az provider show -n Microsoft.App`."
  type        = string
}

variable "registry_name" {
  description = "Container registry name. Must be globally unique and alphanumeric only."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{5,50}$", var.registry_name))
    error_message = "Registry names must be 5-50 characters of lowercase letters and digits only."
  }
}

variable "registry_sku" {
  description = "Registry SKU. Basic is sufficient for a single small image and is the cheapest tier that supports Entra ID authentication."
  type        = string
  default     = "Basic"
}

variable "registry_login_server" {
  description = "Login server the app pulls from, normally the registry created here. Null on the first apply, when the image is still a public placeholder and no registry credentials are needed."
  type        = string
  default     = null
}

variable "container_image" {
  description = "Fully qualified image reference. Must be linux/amd64: Container Apps does not run arm64, and an arm64 image pushes successfully then crash-loops with an exec format error."
  type        = string
}

variable "image_push_principal_ids" {
  description = "Object IDs granted AcrPush, for whoever builds and pushes the image locally"
  type        = list(string)
  default     = []
}

variable "target_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8000
}

variable "min_replicas" {
  description = "Minimum replicas. Zero lets the app scale to nothing when idle, at the cost of a cold start on the next request."
  type        = number
  default     = 0
}

variable "max_replicas" {
  description = "Maximum replicas"
  type        = number
  default     = 2
}

variable "cpu" {
  description = "vCPU per replica. Must pair with memory in a supported combination: 0.5 vCPU goes with 1Gi."
  type        = number
  default     = 0.5
}

variable "memory" {
  description = "Memory per replica, paired with cpu"
  type        = string
  default     = "1Gi"
}

variable "environment_variables" {
  description = "Plain environment variables for the container. Not for secrets: these are visible in the resource definition."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "Log Analytics retention. 30 is the minimum billable period."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to every resource in the module"
  type        = map(string)
  default     = {}
}
