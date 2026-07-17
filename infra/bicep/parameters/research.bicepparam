using '../main.bicep'

param location = 'westeurope'
param resourceGroupName = 'rg-mcift-benchmarks-weu'
param monthlyBudgetAmount = 20
param budgetContactEmails = []
param benchmarkImage = 'ghcr.io/corpobear/mcift-benchmarks:sha-unpublished'
param deployExathlonCompute = true
param deployContainerApps = true
