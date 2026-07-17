param monthlyBudgetAmount int
param startDate string
param contactEmails array

var notificationsEnabled = length(contactEmails) > 0
resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: 'budget-mcift-benchmarks'
  properties: union({
    amount: monthlyBudgetAmount
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: { startDate: startDate, endDate: '2035-12-31' }
  }, notificationsEnabled ? {
    notifications: {
      actual50: { enabled: notificationsEnabled, operator: 'GreaterThanOrEqualTo', threshold: 50, thresholdType: 'Actual', contactEmails: contactEmails }
      actual80: { enabled: notificationsEnabled, operator: 'GreaterThanOrEqualTo', threshold: 80, thresholdType: 'Actual', contactEmails: contactEmails }
      actual100: { enabled: notificationsEnabled, operator: 'GreaterThanOrEqualTo', threshold: 100, thresholdType: 'Actual', contactEmails: contactEmails }
    }
  } : {})
}

output budgetName string = budget.name
output notificationsConfigured bool = notificationsEnabled
