param location string
param tags object
param identityId string
param identityClientId string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param benchmarkImage string
param storageAccountName string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-mcift-benchmarks'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: { customerId: logAnalyticsCustomerId, sharedKey: logAnalyticsSharedKey }
    }
  }
}

resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-mcift-ims'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identityId}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 7200
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
    }
    template: {
      containers: [
        {
          name: 'ims'
          image: benchmarkImage
          command: ['python', '-m', 'mcift_benchmarks']
          args: ['validate-config', '--config', '/app/configs/ims-set2-v1.yaml']
          env: [
            { name: 'AZURE_CLIENT_ID', value: identityClientId }
            { name: 'AZURE_STORAGE_ACCOUNT', value: storageAccountName }
            { name: 'MCIFT_LOG_REQUIRED_FIELDS', value: 'job_execution_id,source_commit,image_digest,config_hash,dataset_manifest_hash,state,error_summary' }
          ]
          resources: { cpu: json('4.0'), memory: '8Gi' }
        }
      ]
    }
  }
}

output jobName string = job.name
output environmentName string = environment.name
