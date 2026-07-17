param location string
param tags object

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-mcift-benchmarks'
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    sku: { name: 'PerGB2018' }
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-mcift-benchmarks'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    IngestionMode: 'LogAnalytics'
    RetentionInDays: 30
  }
}

output logAnalyticsWorkspaceId string = logs.id
output logAnalyticsCustomerId string = logs.properties.customerId
@secure()
output logAnalyticsSharedKey string = logs.listKeys().primarySharedKey
output applicationInsightsId string = insights.id
