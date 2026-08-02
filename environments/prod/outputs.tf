output "resource_group_name" {
  description = "Production resource group name"
  value       = module.resource_group.resource_group_name
}

output "resource_group_id" {
  description = "Production resource group ID"
  value       = module.resource_group.resource_group_id
}
