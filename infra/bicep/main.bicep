targetScope = 'subscription'

@description('Deployment region.')
param location string = 'westeurope'
param resourceGroupName string = 'rg-mcift-benchmarks-weu'
param monthlyBudgetAmount int = 20
param budgetStartDate string = utcNow('yyyy-MM-01')
@description('Budget alert recipients. Empty means notifications are disabled until explicitly configured.')
param budgetContactEmails array = []
param benchmarkImage string = 'ghcr.io/corpobear/mcift-benchmarks:sha-unpublished'
@description('Deploy intended AML compute only after regional quota/availability is confirmed.')
param deployExathlonCompute bool = true
@description('Deploy Container Apps resources only when West Europe managed-environment capacity is available.')
param deployContainerApps bool = true
param ownerTag string = 'Martin-Kasala'

var tags = {
  project: 'MCIFT'
  workload: 'public-benchmarks'
  environment: 'research'
  owner: ownerTag
  'managed-by': 'bicep'
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module identity 'modules/identity.bicep' = {
  name: 'identity'
  scope: resourceGroup
  params: { location: location, tags: tags }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    principalId: identity.outputs.principalId
    subscriptionId: subscription().subscriptionId
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: { location: location, tags: tags }
}

module containerApps 'modules/container-apps.bicep' = if (deployContainerApps) {
  name: 'container-apps'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    identityId: identity.outputs.identityId
    identityClientId: identity.outputs.clientId
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: monitoring.outputs.logAnalyticsSharedKey
    benchmarkImage: benchmarkImage
    storageAccountName: storage.outputs.storageAccountName
  }
}

module machineLearning 'modules/machine-learning.bicep' = {
  name: 'machine-learning'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    identityId: identity.outputs.identityId
    storageAccountId: storage.outputs.storageAccountId
    applicationInsightsId: monitoring.outputs.applicationInsightsId
    benchmarkImage: benchmarkImage
    deployCompute: deployExathlonCompute
  }
}

module budget 'modules/budget.bicep' = {
  name: 'budget'
  scope: resourceGroup
  params: {
    monthlyBudgetAmount: monthlyBudgetAmount
    startDate: budgetStartDate
    contactEmails: budgetContactEmails
  }
}

output resourceGroupName string = resourceGroup.name
output location string = location
output storageAccountName string = storage.outputs.storageAccountName
output managedIdentityName string = identity.outputs.name
output containerAppsJobName string = 'caj-mcift-ims'
output machineLearningWorkspaceName string = machineLearning.outputs.workspaceName
output machineLearningComputeName string = machineLearning.outputs.computeName
