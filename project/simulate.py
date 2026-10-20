import os
import numpy as np
import pandas as pd
from utils import *  # @module-import


def _elasticity(lab, c):
    x = pd.to_numeric(lab[c['DISCOUNT']], errors='coerce')
    y = lab['is_churned'].astype(float)
    m = x.notna() & y.notna()
    x, y = x[m], y[m]
    base = float(y.mean())
    if len(x) < 30 or x.std() == 0 or base <= 0:
        return None, 'insufficient data'
    xc = x - x.mean()
    slope = float((xc * (y - y.mean())).sum() / (xc ** 2).sum())
    resid = y - (y.mean() + slope * xc)
    se = float(np.sqrt((resid ** 2).sum() / max(len(x) - 2, 1) / (xc ** 2).sum()))
    t = slope / se if se > 0 else 0.0
    if abs(t) > 2 and slope < 0:
        return float(np.clip(-slope / base * 100.0, 0.1, 3.0)), 'data-derived (slope %.4f per discount pt, t=%.2f)' % (slope, t)
    return None, 'slope not significant or wrong sign (t=%.2f)' % t


def run_simulations(m, ch_t, cfg, verbose=True):
    c = cfg
    outdir = 'output/decide/simulations'
    os.makedirs(outdir, exist_ok=True)
    lab = m[m['is_churned'].notna()]
    act = m[m[c['STATUS']] == c['ACTIVE_VALUE']].copy()
    mrr = act[c['MRR']].fillna(act[c['MRR0']]).fillna(0).values
    p = act['churn_prob'].values
    gm = float(lab[c['GM']].mean() / 100.0)
    # 1. price change
    eps, how = _elasticity(lab, c)
    scen = [('data-derived', eps)] if eps is not None else [('low (assumed)', 0.5), ('base (assumed)', 1.0), ('high (assumed)', 1.5)]
    print('Price elasticity:', how, '-> scenarios', scen)
    base_ret = float((mrr * (1 - p)).sum())
    res = []
    for pc in [-10, -5, 0, 5, 10, 15]:
        for nm, e in scen:
            p2 = np.clip(p * (1 + e * pc / 100.0), 0, 1)
            new_ret = float((mrr * (1 + pc / 100.0) * (1 - p2)).sum())
            res.append({'input': {'price_change_pct': pc, 'elasticity_scenario': nm, 'elasticity': e},
                        'outputs': {'delta_mrr': new_ret - base_ret, 'delta_churned_accounts': float((p2 - p).sum()), 'net_arr_change': (new_ret - base_ret) * 12}})
    save_json(os.path.join(outdir, 'price_change_impact.json'), {
        'variable': 'price_change_pct', 'range': [-10, 15, 5],
        'assumptions': ['Elasticity: %s' % how, 'Relative change in each account 90-day churn probability = elasticity x price change %',
                        'Outputs compare expected retained MRR over 90 days vs. no change; applies to active accounts only'], 'results': res})
    # 2. retention campaign ROI
    hi = act[act['churn_band'] == 'High']
    if len(hi) == 0:
        hi = act.sort_values('churn_prob', ascending=False).head(max(1, int(len(act) * 0.1)))
    res = []
    for sr in range(5, 45, 5):
        for cost in c['CAMPAIGN_COST_PER_ACCOUNT']:
            saved = float(hi['arr_at_risk'].sum() * sr / 100.0)
            tot_cost = float(len(hi) * cost)
            res.append({'input': {'save_rate_pct': sr, 'cost_per_account': cost},
                        'outputs': {'accounts_targeted': int(len(hi)), 'saved_arr': saved, 'campaign_cost': tot_cost, 'roi': (saved * gm - tot_cost) / max(tot_cost, 1e-9)}})
    save_json(os.path.join(outdir, 'retention_campaign_roi.json'), {
        'variable': 'save_rate_pct x cost_per_account', 'range': [5, 40, 5],
        'assumptions': ['Targets High-risk accounts (or top 10 percent by risk if none); saved ARR = expected ARR at risk x save rate',
                        'ROI = (saved ARR x average gross margin %.0f%% - cost) / cost' % (gm * 100), 'Cost per account values are assumptions in CONFIG'], 'results': res})
    # 3. discount policy
    band_rate = lab.groupby('discount_depth_band')['is_churned'].agg(['mean', 'count'])
    overall = float(lab['is_churned'].mean())

    def rate(b):
        return float(band_rate.loc[b, 'mean']) if (b in band_rate.index and band_rate.loc[b, 'count'] >= c['MIN_GROUP_N']) else overall

    def band_of(x):
        return '0' if x <= 0 else ('1-10' if x <= 10 else ('11-20' if x <= 20 else '20+'))
    res = []
    d0 = act[c['DISCOUNT']].fillna(0).values
    lp = (act[c['SEATS']] * act[c['LIST_PRICE']]).fillna(0).values
    for cap in [10, 15, 20, 25]:
        over = d0 > cap
        d_mrr = np.where(over, lp * (d0 - cap) / 100.0, 0.0)
        dp = np.array([max(0.0, rate(band_of(cap)) - rate(band_of(x))) if o else 0.0 for x, o in zip(d0, over)])
        new_ret = float(((mrr + d_mrr) * (1 - np.clip(p + dp, 0, 1))).sum())
        res.append({'input': {'discount_cap_pct': cap}, 'outputs': {
            'accounts_affected': int(over.sum()), 'mrr_gained_if_no_churn': float(d_mrr.sum()), 'margin_gained_monthly': float((d_mrr * gm).sum()),
            'added_expected_churned_accounts': float(dp.sum()), 'net_expected_mrr_change': new_ret - base_ret, 'net_arr_change': (new_ret - base_ret) * 12}})
    save_json(os.path.join(outdir, 'discount_policy_impact.json'), {
        'variable': 'discount_cap_pct', 'range': [10, 25, 5],
        'assumptions': ['Added churn = churn-rate gap between the capped band and the current band (only increases counted; bands with n<%d use overall rate)' % c['MIN_GROUP_N'],
                        'Discount reduction raises MRR by seats x list price x discount points removed', 'Margin gain uses average gross margin'], 'results': res})
    # 4. channel budget shift
    t = ch_t[ch_t['n'] >= c['MIN_GROUP_N']].dropna(subset=['ltv_cac', 'cac_avg', 'monthly_gp_avg'])
    res, note = [], 'insufficient channels with n>=%d' % c['MIN_GROUP_N']
    if len(t) >= 2:
        w, b = t.loc[t['ltv_cac'].idxmin()], t.loc[t['ltv_cac'].idxmax()]
        eff = 0.8
        tot_cac = float(t['cac_total'].sum())
        gp0 = float((t['n'] * t['monthly_gp_avg']).sum())
        pb0 = tot_cac / max(gp0, 1e-9)
        for s in [10, 20, 30]:
            moved = float(w['n'] * (s / 100.0))
            gained = moved * w['cac_avg'] / max(b['cac_avg'], 1e-9) * eff
            gp1 = gp0 - moved * w['monthly_gp_avg'] + gained * b['monthly_gp_avg']
            res.append({'input': {'shift_pct': s, 'from_channel': str(w[c['CHANNEL']]), 'to_channel': str(b[c['CHANNEL']])},
                        'outputs': {'accounts_lost': moved, 'accounts_gained': gained, 'blended_payback_before_months': pb0,
                                    'blended_payback_after_months': tot_cac / max(gp1, 1e-9), 'payback_change_months': tot_cac / max(gp1, 1e-9) - pb0}})
        note = 'ok'
    save_json(os.path.join(outdir, 'channel_budget_shift.json'), {
        'variable': 'shift_pct_of_worst_channel_cac', 'range': [10, 30, 10],
        'assumptions': ['Total CAC spend constant; blended payback = total CAC / monthly gross profit of acquired accounts',
                        'Marginal efficiency of added spend in the best channel = 80 percent of its average (assumption)', 'Average CAC and monthly gross profit per account are held constant; status: ' + note], 'results': res})
    print('Simulations written to', outdir)
    return {'elasticity': eps, 'elasticity_basis': how}
