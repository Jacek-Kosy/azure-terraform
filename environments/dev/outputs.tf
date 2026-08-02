output "resource_group_name" {
  description = "Development resource group name"
  value       = module.resource_group.resource_group_name
}

output "resource_group_id" {
  description = "Development resource group ID"
  value       = module.resource_group.resource_group_id
}
