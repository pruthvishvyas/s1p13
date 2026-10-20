// Tolerant field access for account-level rows exported by the pipeline.
const n = (v) => (v === null || v === undefined || v === '' || Number.isNaN(Number(v)) ? 0 : Number(v));
export const F = {
  id: (r) => r.Customer_ID ?? r.customer_id ?? r.id ?? '',
  company: (r) => r.Company ?? r.company ?? '',
  plan: (r) => r.Plan ?? r.plan ?? '',
  arr: (r) => n(r.ARR_Current ?? r.arr),
  risk: (r) => n(r.arr_at_risk),
  prob: (r) => n(r.churn_prob)
};
