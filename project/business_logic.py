import os
import numpy as np
import pandas as pd
from utils import *  # @module-import
from features import channel_table  # @module-import

SEV_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}


def assign_alert(r, c, ctx):
    """Return the list of alerts (code, severity, action) that fire for one active account."""
    T = c['THRESHOLDS']
    out = []
    p = float(r['churn_prob'])
    arr = r[c['ARR']] if pd.notna(r[c['ARR']]) else 0.0
    if p >= c['BAND_EDGES']['high'] and arr >= ctx['arr_q']:
        out.append(('R1_HIGH_RISK_HIGH_ARR', 'critical', 'Executive call this week; offer success plan'))
    if r['inactive_flag'] == 1 and r['low_usage_flag'] == 1:
        out.append(('R2_DISENGAGED', 'high', 'Re-onboarding session; assign CSM'))
    if r['detractor_flag'] == 1 and r['high_ticket_flag'] == 1:
        out.append(('R3_UNHAPPY', 'high', 'Escalate open issues; service recovery'))
    if r['late_payer_flag'] == 1 or (pd.notna(r['balance_to_mrr']) and r['balance_to_mrr'] > 1.0):
        out.append(('R4_BILLING', 'medium', 'Billing follow-up; offer annual prepay or auto-pay'))
    if pd.notna(r[c['DISCOUNT']]) and r[c['DISCOUNT']] > T['MAX_HEALTHY_DISCOUNT'] and (r['inactive_flag'] == 1 or r['low_usage_flag'] == 1):
        out.append(('R5_DISCOUNT_LEAK', 'medium', 'Do not renew at deeper discount; tie to usage plan'))
    hi_u = ctx['usage_scale'] * T['HIGH_USAGE'] / 100.0
    if r['promoter_flag'] == 1 and pd.notna(r[c['USAGE']]) and r[c['USAGE']] >= hi_u and (pd.isna(r[c['EXPANSION']]) or r[c['EXPANSION']] <= 0):
        out.append(('R6_UPSELL', 'low', 'Upsell seats / next plan tier'))
    healthy = (pd.isna(r[c['HEALTH']]) or r[c['HEALTH']] >= T['LOW_HEALTH']) and p < c['BAND_EDGES']['medium']
    if r['annual_flag'] == 0 and pd.notna(r[c['USAGE']]) and r[c['USAGE']] >= hi_u and healthy:
        out.append(('R7_ANNUAL_OFFER', 'low', 'Offer annual plan discount to lock in'))
    return out


def priority_level(alerts, p, arr, ctx, c):
    sev = [a[1] for a in alerts]
    if 'critical' in sev:
        return 'P1'
    if 'high' in sev or p >= c['BAND_EDGES']['high']:
        return 'P2'
    if 'medium' in sev or p >= c['BAND_EDGES']['medium']:
        return 'P3'
    return 'P4'


def recommend(alerts, p):
    if not alerts:
        return 'Monitor; no action needed this week'
    al = sorted(alerts, key=lambda a: SEV_RANK[a[1]])
    return ' + '.join(dict.fromkeys(a[2] for a in al[:2]))


def run_logic(act, ch_t, cfg, usage_scale=100.0, verbose=True):
    c = cfg
    a = act.reset_index(drop=True).copy()
    ctx = {'arr_q': float(a[c['ARR']].quantile(c['TOP_ARR_QUANTILE'])), 'usage_scale': usage_scale}
    codes, tops, prios, recs, nal = [], [], [], [], []
    for _, r in a.iterrows():
        al = assign_alert(r, c, ctx)
        arr = r[c['ARR']] if pd.notna(r[c['ARR']]) else 0.0
        codes.append(', '.join(x[0] for x in al))
        tops.append(sorted(al, key=lambda x: SEV_RANK[x[1]])[0][0] if al else '')
        prios.append(priority_level(al, float(r['churn_prob']), arr, ctx, c))
        recs.append(recommend(al, float(r['churn_prob'])))
        nal.append(len(al))
    a['alerts'] = codes
    a['top_alert'] = tops
    a['priority'] = prios
    a['recommendation'] = recs
    a['n_alerts'] = nal
    ps = a.groupby('priority').agg(accounts=(c['ID'], 'size'), arr=(c['ARR'], 'sum'), arr_at_risk=('arr_at_risk', 'sum')).reindex(['P1', 'P2', 'P3', 'P4']).fillna(0)
    headline = float(ps.loc[['P1', 'P2'], 'arr_at_risk'].sum())
    print('Priority counts and ARR at risk:')
    print(ps.round(0).to_string())
    print('HEADLINE: ARR at risk in P1+P2 = %.0f' % headline)
    T = c['THRESHOLDS']
    chn = ch_t.copy()
    chn['recommendation'] = np.where((chn['ltv_cac'] < T['LTV_CAC_MIN']) | (chn['payback_median'] > T['PAYBACK_MAX_MONTHS']),
                                     "Cut or reprice this channel's CAC", 'Keep / scale within payback limits')
    chn.loc[chn['n'] < c['MIN_GROUP_N'], 'recommendation'] = 'Insufficient data (n<%d)' % c['MIN_GROUP_N']
    a.sort_values(['priority', 'arr_at_risk'], ascending=[True, False]).to_csv('data/processed/business_logic_output.csv', index=False, encoding='utf-8')
    return {'act': a, 'priority_summary': ps.reset_index(), 'headline_arr_at_risk': headline, 'channel_recs': chn, 'ctx': ctx}


def assemble_master(feat, scored, seg_df, logic_act, fc_acc, cfg):
    """One account-level table (all accounts) used by the export, Excel and dashboard."""
    c = cfg
    m = scored.copy()
    m = m.merge(seg_df[[c['ID'], 'segment', 'is_anomaly', 'anomaly_reason']], on=c['ID'], how='left')
    m = m.merge(logic_act[[c['ID'], 'alerts', 'top_alert', 'priority', 'recommendation', 'n_alerts']], on=c['ID'], how='left')
    if fc_acc is not None and len(fc_acc):
        keep = [k for k in fc_acc.columns if k not in (c['COMPANY'], 'current_mrr')]
        m = m.merge(fc_acc[keep], on=c['ID'], how='left')
    m['is_anomaly'] = m['is_anomaly'].fillna(0).astype(int)
    m.to_csv('data/processed/account_master.csv', index=False, encoding='utf-8')
    print('Account master saved:', m.shape)
    return m


def snapshot_retention(m, cfg):
    c = cfg
    d = m[m['is_churned'].notna()]
    act, chd = d[d['is_churned'] == 0], d[d['is_churned'] == 1]
    start = float(d[c['MRR0']].sum())
    churned = float(chd[c['MRR0']].sum())
    contr = float((act[c['MRR0']] - act[c['MRR']]).clip(lower=0).sum())
    expn = float((act[c['MRR']] - act[c['MRR0']]).clip(lower=0).sum())
    grr = (start - churned - contr) / max(start, 1e-9) * 100
    nrr = (start - churned - contr + expn) / max(start, 1e-9) * 100
    return {'starting_mrr': start, 'churned_mrr': churned, 'contraction_mrr': contr, 'expansion_mrr': expn,
            'grr_pct': grr, 'nrr_pct': nrr, 'label': 'snapshot approximation (signup-to-as-of window, not annualized)'}


def run_goals_alerts(m, fc, cfg, verbose=True):
    c = cfg
    T = c['THRESHOLDS']
    goals = {
        'mrr_target': {'value': None, 'unit': 'monthly', 'client_sets': True},
        'grr_target': {'value': T['GRR_TARGET'], 'unit': 'percent', 'description': 'Gross revenue retention target (annual)'},
        'nrr_target': {'value': T['NRR_TARGET'], 'unit': 'percent', 'description': 'Net revenue retention target (annual)'},
        'alert_mrr_drop_pct': {'value': 5, 'unit': 'percent', 'description': 'Alert if forecast MRR falls this % in a month'},
        'at_risk_arr_share': {'value': 15, 'unit': 'percent', 'description': 'Alert if High-risk ARR exceeds this share of ARR'},
        'inactive_days': {'value': T['INACTIVE_LOGIN_DAYS'], 'unit': 'days'},
        'forecast_horizon': {'value': c['FORECAST_MONTHS'], 'unit': 'months'}}
    if os.path.exists('config/goals.json'):
        old = load_json('config/goals.json', {}) or {}
        for k, v in goals.items():
            if k in old and isinstance(old[k], dict) and 'value' in old[k]:
                goals[k]['value'] = old[k]['value']
    save_json('config/goals.json', goals)
    ret = snapshot_retention(m, c)
    act = m[m[c['STATUS']] == c['ACTIVE_VALUE']]
    mrr_now = float(act[c['MRR']].sum())
    arr_now = float(act[c['ARR']].sum())
    high_arr = float(act.loc[act['churn_band'] == 'High', c['ARR']].sum())
    share = high_arr / max(arr_now, 1e-9) * 100
    prog = {'grr': {'actual_pct': ret['grr_pct'], 'target_pct': goals['grr_target']['value'], 'met': bool(ret['grr_pct'] >= goals['grr_target']['value'])},
            'nrr': {'actual_pct': ret['nrr_pct'], 'target_pct': goals['nrr_target']['value'], 'met': bool(ret['nrr_pct'] >= goals['nrr_target']['value'])},
            'mrr': {'actual': mrr_now, 'target': goals['mrr_target']['value'],
                    'met': None if goals['mrr_target']['value'] in (None, 0) else bool(mrr_now >= goals['mrr_target']['value'])},
            'logo_churn_pct': {'actual': float((m['is_churned'] == 1).sum() / max(m['is_churned'].notna().sum(), 1) * 100)},
            'high_risk_arr_share_pct': {'actual': share, 'limit': goals['at_risk_arr_share']['value'], 'met': bool(share <= goals['at_risk_arr_share']['value'])},
            'basis': ret['label'], 'retention_detail': ret}
    alerts = []
    mf = fc['monthly'] if fc and len(fc.get('monthly', [])) else pd.DataFrame()
    if len(mf) > 1:
        chg = mf['mrr_base'].pct_change().fillna(0) * 100
        worst = float(chg.min())
        if worst <= -goals['alert_mrr_drop_pct']['value']:
            alerts.append({'severity': 'high', 'type': 'forecast_mrr_drop', 'message': 'Forecast MRR falls %.1f%% in a single month' % abs(worst)})
    if share > goals['at_risk_arr_share']['value']:
        alerts.append({'severity': 'high', 'type': 'at_risk_arr_share', 'message': 'High-risk ARR is %.1f%% of ARR (limit %s%%)' % (share, goals['at_risk_arr_share']['value'])})
    inact = act[act[c['LOGIN_AGO']] >= goals['inactive_days']['value']]
    if len(inact):
        alerts.append({'severity': 'medium', 'type': 'inactivity', 'message': '%d active accounts inactive for %d+ days (ARR %.0f)' % (len(inact), goals['inactive_days']['value'], inact[c['ARR']].sum()),
                       'accounts': inact.sort_values(c['ARR'], ascending=False)[c['ID']].head(10).tolist()})
    od = act[(act[c['LATE']] > 0) & (act[c['BALANCE']] > 0)]
    if len(od):
        alerts.append({'severity': 'medium', 'type': 'overdue_invoices', 'message': '%d accounts with late invoices and an open balance (total %.0f)' % (len(od), od[c['BALANCE']].sum()),
                       'accounts': od.sort_values(c['BALANCE'], ascending=False)[c['ID']].head(10).tolist()})
    low_h = act[(act[c['HEALTH']] < T['LOW_HEALTH'])]
    if len(low_h):
        alerts.append({'severity': 'medium', 'type': 'low_health', 'message': '%d active accounts have health score below %s' % (len(low_h), T['LOW_HEALTH']),
                       'accounts': low_h.sort_values(c['ARR'], ascending=False)[c['ID']].head(10).tolist()})
    p1 = act[act['priority'] == 'P1']
    if len(p1):
        alerts.append({'severity': 'critical', 'type': 'p1_accounts', 'message': '%d P1 accounts need action this week (ARR at risk %.0f)' % (len(p1), p1['arr_at_risk'].sum()),
                       'accounts': p1.sort_values('arr_at_risk', ascending=False)[c['ID']].head(10).tolist()})
    save_json(os.path.join(c['REPORTS_DIR'], 'goal_progress.json'), prog)
    save_json(os.path.join(c['REPORTS_DIR'], 'alerts.json'), alerts)
    print('GRR %.1f%% | NRR %.1f%% (%s)' % (ret['grr_pct'], ret['nrr_pct'], ret['label']))
    print('Alerts raised:', len(alerts))
    return {'goals': goals, 'progress': prog, 'alerts': alerts, 'retention': ret}


def build_insights(m, cfg, model_card=None, fc_meta=None, ch_t=None):
    c = cfg
    T = c['THRESHOLDS']
    MIN_N = c['MIN_GROUP_N']
    act = m[m[c['STATUS']] == c['ACTIVE_VALUE']]
    lab = m[m['is_churned'].notna()]
    ins = []

    def add(cat, finding, evidence, action, impact):
        ins.append({'severity': 'MEDIUM', 'category': cat, 'finding': finding, 'evidence': evidence, 'action': action,
                    'outcome': 'DECIDE', '_impact': float(impact)})
    arr = float(act[c['ARR']].sum())
    risk = float(act['arr_at_risk'].sum())
    top = act.sort_values('arr_at_risk', ascending=False).head(5)
    add('Revenue Retention', 'Expected ARR at risk is %.0f (%.1f%% of active ARR)' % (risk, risk / max(arr, 1e-9) * 100),
        'Top accounts: ' + '; '.join('%s (%.0f)' % (r[c['COMPANY']], r['arr_at_risk']) for _, r in top.iterrows()),
        'Work the Save List top-down this week; start with P1 accounts.', risk)
    g = lab.groupby(c['PLAN'])['is_churned'].agg(['mean', 'count'])
    g = g[g['count'] >= MIN_N]
    if len(g):
        w = g['mean'].idxmax()
        add('Revenue Retention', 'Highest-churn plan is %s at %.1f%% (n=%d)' % (w, g.loc[w, 'mean'] * 100, g.loc[w, 'count']),
            'Overall churn rate %.1f%%' % (lab['is_churned'].mean() * 100), 'Review onboarding and pricing for this plan.',
            g.loc[w, 'mean'] * lab.loc[lab[c['PLAN']] == w, c['MRR0']].sum() * 12)
    rs = lab[lab['is_churned'] == 1].groupby(c['REASON'])['mrr_lost'].sum().sort_values(ascending=False)
    if len(rs):
        add('Revenue Retention', 'Largest churn reason by MRR lost: %s (%.0f MRR, %.0f%% of lost MRR)' % (rs.index[0], rs.iloc[0], rs.iloc[0] / rs.sum() * 100),
            'Top 3 reasons: ' + ', '.join('%s %.0f' % (k, v) for k, v in rs.head(3).items()), 'Build a retention play aimed at this reason.', rs.iloc[0] * 12)
    ct = ch_t if ch_t is not None else pd.DataFrame()
    ctn = ct[ct['n'] >= MIN_N] if len(ct) else ct
    if len(ctn):
        bw, bb = ctn.loc[ctn['ltv_cac'].idxmin()], ctn.loc[ctn['ltv_cac'].idxmax()]
        add('Channel Performance', 'Worst channel %s: LTV:CAC %.2f, payback %.1f months (n=%d); best %s: %.2f, %.1f months' % (
            bw[c['CHANNEL']], bw['ltv_cac'], bw['payback_median'], bw['n'], bb[c['CHANNEL']], bb['ltv_cac'], bb['payback_median']),
            'Benchmarks: LTV:CAC >= %.1f, payback <= %d months. Realized LTV is based on account age so young cohorts look worse.' % (T['LTV_CAC_MIN'], T['PAYBACK_MAX_MONTHS']),
            'Shift budget from the worst to the best channel (see channel_budget_shift simulation).', float(bw['cac_total']) if pd.notna(bw['cac_total']) else 0.0)
        under = ctn[(ctn['ltv_cac'] < T['LTV_CAC_MIN']) | (ctn['payback_median'] > T['PAYBACK_MAX_MONTHS'])]
        add('Unit Economics', '%d of %d channels miss the LTV:CAC or payback benchmark' % (len(under), len(ctn)),
            'Missing: ' + ', '.join(under[c['CHANNEL']].astype(str).tolist()[:6]), 'Cut or reprice CAC in the flagged channels.', float(under['cac_total'].sum()) * 0.2)
    gd = lab.groupby('discount_depth_band')['is_churned'].agg(['mean', 'count'])
    gd = gd[gd['count'] >= MIN_N]
    if len(gd) >= 2:
        add('Pricing & Discounts', 'Churn by discount band: ' + ', '.join('%s: %.1f%% (n=%d)' % (i, r['mean'] * 100, r['count']) for i, r in gd.iterrows()),
            '%d active accounts exceed the %d%% healthy-discount line' % (int((act[c['DISCOUNT']] > T['MAX_HEALTHY_DISCOUNT']).sum()), T['MAX_HEALTHY_DISCOUNT']),
            'Tie deeper discounts to usage commitments; do not renew deep discounts blindly.', float(act.loc[act[c['DISCOUNT']] > T['MAX_HEALTHY_DISCOUNT'], c['ARR']].sum()) * 0.1)
    inact = act[act['inactive_flag'] == 1]
    add('Customer Health', '%.1f%% of active accounts (%d) have not logged in for %d+ days' % (len(inact) / max(len(act), 1) * 100, len(inact), T['INACTIVE_LOGIN_DAYS']),
        'Their ARR: %.0f' % inact[c['ARR']].sum(), 'Run a re-onboarding session for these accounts.', float(inact[c['ARR']].sum()) * 0.3)
    lp = act[(act['late_payer_flag'] == 1)]
    add('Collections', '%d late-paying active accounts carry %.0f outstanding balance' % (len(lp), lp[c['BALANCE']].sum()),
        'Total open balance on active accounts: %.0f' % act[c['BALANCE']].sum(), 'Offer auto-pay or annual prepay; start billing follow-up.', float(lp[c['BALANCE']].sum()))
    ex = act[(act['promoter_flag'] == 1) & (act[c['USAGE']] >= (T['HIGH_USAGE'] * (100.0 if act[c['USAGE']].max() > 1.5 else 1.0) / 100.0)) & (act[c['EXPANSION']].fillna(0) <= 0)]
    add('Expansion Opportunity', '%d promoter, high-usage accounts have not expanded' % len(ex), 'Their ARR: %.0f' % ex[c['ARR']].sum(),
        'Offer seat or tier upsell.', float(ex[c['ARR']].sum()) * 0.1)
    if model_card:
        mt = model_card['metrics_holdout']
        exc = [k for k, v in model_card['excluded_features'].items()]
        add('Revenue Retention', 'Churn model hold-out: PR-AUC %.2f (base rate %.2f), ROC-AUC %.2f, recall@top20%% %.0f%%; primary scoring = %s' % (
            mt['pr_auc'], mt['base_rate_test'], mt['roc_auc'], mt['recall_at_top20'] * 100, model_card['primary_scoring']),
            'Leakage columns excluded: ' + ', '.join(exc[:10]) + '; shuffled-target AUC %.2f' % model_card['shuffled_target_auc'],
            'Use probabilities to rank accounts; revisit signal if acceptance targets are not met.', 0.0)
    else:
        add('Revenue Retention', 'Rule-based scoring is in use (ML gate failed or model skipped)', 'See validation_report.json', 'Collect more churn history to enable ML.', 0.0)
    ins.sort(key=lambda x: -x['_impact'])
    for i, x in enumerate(ins):
        x['severity'] = 'HIGH' if i < 3 else ('MEDIUM' if i < 6 else 'LOW')
        x.pop('_impact', None)
    save_json(os.path.join(c['REPORTS_DIR'], 'insights.json'), ins)
    return ins
