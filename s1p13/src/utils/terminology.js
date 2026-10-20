export const KPI_ORDER = [
  'ARR', 'MRR', 'ARR_at_risk', 'P1_count', 'active_accounts', 'total_accounts', 'logo_churn_pct', 'revenue_churn_pct',
  'GRR_pct', 'NRR_pct', 'ARPA', 'avg_ltv_cac_pooled', 'avg_payback_months', 'model_pr_auc', 'model_roc_auc', 'scoring_source'
];

export function kpiMeta(term) {
  const cust = term('customer');
  const plural = term('customer', { plural: true });
  return {
    ARR: { label: 'Active ARR', format: 'currency' },
    MRR: { label: 'Active MRR', format: 'currency' },
    ARR_at_risk: { label: 'ARR at risk', format: 'currency', tone: 'danger' },
    P1_count: { label: `Urgent ${plural} (P1)`, format: 'integer', tone: 'warning' },
    active_accounts: { label: `Active ${plural}`, format: 'integer' },
    total_accounts: { label: `Total ${plural}`, format: 'integer' },
    logo_churn_pct: { label: `${cust} churn rate`, format: 'percent' },
    revenue_churn_pct: { label: 'Revenue churn rate', format: 'percent' },
    GRR_pct: { label: 'Gross revenue retention', format: 'percent' },
    NRR_pct: { label: 'Net revenue retention', format: 'percent' },
    ARPA: { label: `Avg ${term('revenue').split('/')[0].trim()} per ${cust}`, format: 'currency' },
    avg_ltv_cac_pooled: { label: 'Lifetime value vs acquisition cost', format: 'ratio' },
    avg_payback_months: { label: 'Avg acquisition payback', format: 'months' },
    model_pr_auc: { label: 'Prediction quality (PR-AUC)', format: 'decimal' },
    model_roc_auc: { label: 'Prediction quality (ROC-AUC)', format: 'decimal' },
    scoring_source: { label: 'Risk scoring method', format: 'text' }
  };
}
