import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from utils import *  # @module-import


def engineer(df, cfg, verbose=True):
    c = cfg
    T = c['THRESHOLDS']
    W = c['ENG_WEIGHTS']
    f = df.copy()
    umax = f[c['USAGE']].max()
    usage_scale = 100.0 if (pd.notna(umax) and umax > 1.5) else 1.0
    low_u = T['LOW_USAGE'] * usage_scale / 100.0
    high_u = T['HIGH_USAGE'] * usage_scale / 100.0
    # --- revenue ---
    f['mrr_per_seat'] = sdiv(f[c['MRR0']], f[c['SEATS']])       # Initial MRR: not an exit-time snapshot
    f['discount_depth_band'] = pd.cut(f[c['DISCOUNT']], [-np.inf, 0, 10, 20, np.inf],
                                      labels=['0', '1-10', '11-20', '20+']).astype(object)
    f['expansion_flag'] = (f[c['MRR']] > f[c['MRR0']]).astype(int)
    f['contraction_flag'] = (f[c['MRR']] < f[c['MRR0']]).astype(int)
    f['arr_at_risk'] = np.nan
    f['monthly_gp'] = f[c['MRR0']] * f[c['GM']] / 100.0
    # --- engagement ---
    f['login_recency_band'] = pd.cut(f[c['LOGIN_AGO']], [-np.inf, 7, 30, 60, np.inf],
                                     labels=['0-7', '8-30', '31-60', '60+']).astype(object)
    f['inactive_flag'] = (f[c['LOGIN_AGO']] >= T['INACTIVE_LOGIN_DAYS']).astype(int)
    f['usage_per_seat'] = sdiv(f[c['USAGE']], f[c['SEATS']])
    f['low_usage_flag'] = ((f[c['USAGE']] < low_u) & f[c['USAGE']].notna()).astype(int)
    # --- support / sentiment ---
    f['tickets_per_seat'] = sdiv(f[c['TICKETS']], f[c['SEATS']])
    f['high_ticket_flag'] = (f[c['TICKETS']] >= T['HIGH_TICKETS_90D']).astype(int)
    f['detractor_flag'] = (f[c['NPS']] <= T['DETRACTOR_NPS']).astype(int)
    f['promoter_flag'] = (f[c['NPS']] >= T['PROMOTER_NPS']).astype(int)
    # --- payment ---
    f['late_payer_flag'] = ((f[c['DAYS_PAY']] > T['LATE_PAY_DAYS']) | (f[c['LATE']] > T['LATE_INVOICES_MAX'])).astype(int)
    mrr_ref = f[c['MRR']].where(f[c['MRR']] > 0, f[c['MRR0']])
    f['balance_to_mrr'] = sdiv(f[c['BALANCE']], mrr_ref)
    f['annual_flag'] = f[c['CYCLE']].astype(str).str.lower().str.contains('annual|year').astype(int)
    # --- economics ---
    f['ltv_cac_ok'] = (f[c['LTV_CAC']] >= T['LTV_CAC_MIN']).astype(int)
    f['payback_ok'] = (f[c['PAYBACK']] <= T['PAYBACK_MAX_MONTHS']).astype(int)
    f['margin_per_seat'] = f['mrr_per_seat'] * f[c['GM']] / 100.0
    # --- composite engagement risk (0-100) ---
    comp = pd.DataFrame(index=f.index)
    comp['login'] = (f[c['LOGIN_AGO']] / 90.0).clip(0, 1)
    comp['usage'] = (1 - f[c['USAGE']] / usage_scale).clip(0, 1)
    comp['tickets'] = (f[c['TICKETS']] / (2.0 * T['HIGH_TICKETS_90D'])).clip(0, 1)
    comp['nps'] = (1 - f[c['NPS']] / 10.0).clip(0, 1)
    comp['late'] = pd.concat([(f[c['DAYS_PAY']] / (1.5 * T['LATE_PAY_DAYS'])).clip(0, 1),
                              (f[c['LATE']] / (2.0 * T['LATE_INVOICES_MAX'])).clip(0, 1)], axis=1).mean(axis=1)
    w = pd.Series(W)[comp.columns]
    avail = comp.notna().mul(w, axis=1).sum(axis=1)
    f['engagement_risk_score'] = (comp.fillna(0).mul(w, axis=1).sum(axis=1) / avail.where(avail > 0)) * 100.0
    # --- missing flags (imputation happens inside model pipelines only) ---
    f['usage_missing'] = f[c['USAGE']].isna().astype(int)
    f['login_missing'] = f[c['LOGIN_AGO']].isna().astype(int)
    f['nps_missing'] = f[c['NPS']].isna().astype(int)
    # --- combinations ---
    f['plan_x_cycle'] = f[c['PLAN']].astype(str) + ' | ' + f[c['CYCLE']].astype(str)
    sc = f[c['SIZE']].astype(str) + ' | ' + f[c['CHANNEL']].astype(str)
    top = sc.value_counts().head(8).index
    f['size_x_channel'] = sc.where(sc.isin(top), 'Other')
    # --- orders derived from data (never assumed) ---
    plan_order = f.groupby(c['PLAN'])[c['LIST_PRICE']].median().sort_values().index.tolist()

    def size_key(s):
        m = re.search(r'\d+', str(s))
        return int(m.group()) if m else 10 ** 9
    size_order = sorted([s for s in f[c['SIZE']].dropna().unique()], key=size_key)
    risk_pref = ['low', 'medium', 'high']
    present = [r for r in f[c['RISK']].dropna().unique()]
    risk_order = sorted(present, key=lambda r: risk_pref.index(str(r).lower()) if str(r).lower() in risk_pref else 99)
    f['plan_rank'] = f[c['PLAN']].map({p: i for i, p in enumerate(plan_order)})
    f['size_rank'] = f[c['SIZE']].map({p: i for i, p in enumerate(size_order)})
    f['risk_rank'] = f[c['RISK']].map({p: i for i, p in enumerate(risk_order)})
    # tenure_months is kept for survival analysis ONLY (never used by the classifier)
    f.to_csv(c['FEAT_CSV'], index=False, encoding='utf-8')
    meta = {'plan_order': plan_order, 'size_order': size_order, 'risk_order': risk_order, 'usage_scale': usage_scale}
    if verbose:
        print('Feature store saved:', c['FEAT_CSV'], f.shape)
        print('Plan order (by median list price):', plan_order)
        print('Company_Size order (from values found):', size_order)
        print('Churn_Risk order:', risk_order)
    return f, meta


def channel_table(df, cfg):
    c = cfg
    d = df.copy()
    d['_gp'] = d[c['LIFE_GP']].where(d[c['CAC']].notna())
    d['_cac'] = d[c['CAC']].where(d[c['LIFE_GP']].notna())
    g = d.groupby(c['CHANNEL'])
    t = pd.DataFrame({'n': g.size(), 'cac_total': g[c['CAC']].sum(), 'cac_avg': g[c['CAC']].mean(),
                      'gp_total': g['_gp'].sum(), 'cac_paired': g['_cac'].sum(),
                      'payback_median': g[c['PAYBACK']].median(), 'monthly_gp_avg': g['monthly_gp'].mean(),
                      'churn_rate': g['is_churned'].mean()})
    t['ltv_cac'] = sdiv(t['gp_total'], t['cac_paired'])
    t['meets_benchmarks'] = ((t['ltv_cac'] >= cfg['THRESHOLDS']['LTV_CAC_MIN']) &
                             (t['payback_median'] <= cfg['THRESHOLDS']['PAYBACK_MAX_MONTHS']))
    return t.reset_index()


def _bar_rates(ax, g, title):
    ax.barh([str(i) for i in g.index], g['mean'] * 100, color='#2b6cb0')
    for i, (m, n) in enumerate(zip(g['mean'], g['count'])):
        ax.text(m * 100 + 0.5, i, 'n=%d' % n, va='center', fontsize=8)
    ax.set_title(title)
    ax.set_xlabel('Churn rate (%)')


def run_eda(df, cfg, verbose=True):
    c = cfg
    MIN_N = cfg['MIN_GROUP_N']
    charts = {}
    d = df[df['is_churned'].notna()]
    act, chd = d[d['is_churned'] == 0], d[d['is_churned'] == 1]
    # 1. MRR waterfall + cohort retention
    new = float(d[c['MRR0']].sum())
    exp = float((act[c['MRR']] - act[c['MRR0']]).clip(lower=0).sum())
    con = float((act[c['MRR0']] - act[c['MRR']]).clip(lower=0).sum())
    lost = float(chd[c['MRR0']].sum())
    end_mrr = float(act[c['MRR']].sum())
    fig, ax = plt.subplots(1, 2, figsize=(15, 5))
    steps = [('New MRR', new), ('Expansion', exp), ('Contraction', -con), ('Churn', -lost)]
    cum = 0.0
    for i, (lab, v) in enumerate(steps):
        ax[0].bar(lab, v, bottom=cum if i else 0, color='#2f855a' if v >= 0 else '#c53030')
        cum += v
    ax[0].bar('Active MRR now', end_mrr, color='#2b6cb0')
    ax[0].set_title('Q1. MRR waterfall: new, expansion, contraction, churn')
    ax[0].set_ylabel('MRR')
    coh = d.assign(m=d[c['SIGNUP']].dt.to_period('M').astype(str)).groupby('m').apply(
        lambda x: pd.Series({'n': len(x), 'ret': x.loc[x['is_churned'] == 0, c['MRR']].sum() / max(x[c['MRR0']].sum(), 1e-9) * 100}))
    ax[1].bar(coh.index, coh['ret'], color='#2b6cb0')
    for i, n in enumerate(coh['n']):
        ax[1].text(i, coh['ret'].iloc[i] + 1, 'n=%d' % n, ha='center', fontsize=7)
    ax[1].axhline(100, color='grey', ls='--')
    ax[1].set_title('Retained MRR % by signup month (current / initial)')
    ax[1].tick_params(axis='x', rotation=60)
    savefig(fig, 'reports/01_mrr_waterfall_cohorts.png')
    charts['mrr_waterfall'] = {'type': 'bar', 'title': 'MRR waterfall', 'data': xy_list(
        ['New MRR', 'Expansion', 'Contraction', 'Churn', 'Active MRR now'], [new, exp, -con, -lost, end_mrr])}
    charts['cohort_retained_mrr_pct'] = {'type': 'bar', 'title': 'Retained MRR % by signup month',
                                         'data': xy_list(coh.index, coh['ret'])}
    # 2. churn by plan/industry/region
    fig, axs = plt.subplots(1, 3, figsize=(17, 5))
    for ax_, key, nm in zip(axs, ['PLAN', 'INDUSTRY', 'REGION'], ['plan', 'industry', 'region']):
        g = d.groupby(c[key])['is_churned'].agg(['mean', 'count'])
        sup = int((g['count'] < MIN_N).sum())
        g = g[g['count'] >= MIN_N].sort_values('mean')
        _bar_rates(ax_, g, 'Q2. Churn rate by %s (n>=%d%s)' % (nm, MIN_N, ', %d suppressed' % sup if sup else ''))
        charts['churn_by_' + nm] = {'type': 'bar', 'title': 'Churn rate by ' + nm,
                                    'data': xy_list(g.index, g['mean'] * 100)}
    savefig(fig, 'reports/02_churn_by_segment.png')
    # 3. churn reasons by MRR lost (Pareto)
    rs = chd.groupby(c['REASON'])['mrr_lost'].sum().sort_values(ascending=False)
    if len(rs):
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(rs.index.astype(str), rs.values, color='#c05621')
        ax2 = ax.twinx()
        ax2.plot(rs.index.astype(str), rs.cumsum() / rs.sum() * 100, color='black', marker='o')
        ax2.set_ylabel('Cumulative %')
        ax.set_title('Q3. Why do accounts leave? (MRR lost, not counts)')
        ax.tick_params(axis='x', rotation=40)
        savefig(fig, 'reports/03_churn_reasons_pareto.png')
        charts['churn_reason_mrr_lost'] = {'type': 'bar', 'title': 'MRR lost by churn reason', 'data': xy_list(rs.index, rs.values)}
    # 4. channel economics
    ch_t = channel_table(df, cfg)
    ct = ch_t[ch_t['n'] >= MIN_N].sort_values('ltv_cac')
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    axs[0].barh(ct[c['CHANNEL']].astype(str), ct['ltv_cac'], color='#2b6cb0')
    axs[0].axvline(cfg['THRESHOLDS']['LTV_CAC_MIN'], color='red', ls='--', label='3.0x benchmark')
    axs[0].set_title('Q4. Realized LTV:CAC by channel (pooled)')
    axs[0].legend()
    axs[1].barh(ct[c['CHANNEL']].astype(str), ct['payback_median'], color='#805ad5')
    axs[1].axvline(cfg['THRESHOLDS']['PAYBACK_MAX_MONTHS'], color='red', ls='--', label='12-month benchmark')
    axs[1].set_title('Median CAC payback (months)')
    axs[1].legend()
    for i, n in enumerate(ct['n']):
        axs[0].text(0.02, i, 'n=%d' % n, va='center', color='white', fontsize=8)
    savefig(fig, 'reports/04_channel_economics.png')
    charts['channel_ltv_cac'] = {'type': 'bar', 'title': 'LTV:CAC by channel', 'data': xy_list(ct[c['CHANNEL']], ct['ltv_cac'])}
    charts['channel_payback'] = {'type': 'bar', 'title': 'CAC payback months by channel', 'data': xy_list(ct[c['CHANNEL']], ct['payback_median'])}
    # 5. discount vs churn and margin
    order = ['0', '1-10', '11-20', '20+']
    g = d.groupby('discount_depth_band').agg(rate=('is_churned', 'mean'), n=('is_churned', 'size'), gp=('margin_per_seat', 'mean')).reindex(order).dropna(how='all')
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(g.index, g['rate'] * 100, color='#2b6cb0')
    for i, n in enumerate(g['n']):
        ax.text(i, g['rate'].iloc[i] * 100 + 0.5, 'n=%d' % n, ha='center', fontsize=8)
    ax.set_ylabel('Churn rate (%)')
    ax2 = ax.twinx()
    ax2.plot(g.index, g['gp'], color='#c05621', marker='o')
    ax2.set_ylabel('Monthly gross profit per seat')
    ax.set_title('Q5. Discount depth vs churn and margin')
    savefig(fig, 'reports/05_discount_churn_margin.png')
    charts['discount_band_churn_pct'] = {'type': 'bar', 'title': 'Churn rate by discount band', 'data': xy_list(g.index, g['rate'] * 100)}
    charts['discount_band_margin_per_seat'] = {'type': 'bar', 'title': 'Margin per seat by discount band', 'data': xy_list(g.index, g['gp'])}
    # 6. engagement signals by status
    fig, axs = plt.subplots(1, 3, figsize=(16, 4))
    for ax_, key, ttl in zip(axs, ['LOGIN_AGO', 'USAGE', 'NPS'], ['Last login (days ago)', 'Usage score', 'NPS']):
        for lab, sub, col in [('Active', act, '#2f855a'), ('Churned', chd, '#c53030')]:
            v = sub[c[key]].dropna()
            if len(v):
                ax_.hist(v, bins=15, alpha=0.5, density=True, label=lab, color=col)
        ax_.set_title('Q6. ' + ttl)
        ax_.legend()
    savefig(fig, 'reports/06_engagement_by_status.png')
    lg = d.groupby('login_recency_band')['is_churned'].mean().reindex(['0-7', '8-30', '31-60', '60+']).dropna() * 100
    charts['churn_by_login_recency'] = {'type': 'bar', 'title': 'Churn rate by login recency (%)', 'data': xy_list(lg.index, lg.values)}
    # 7. Kaplan-Meier by plan
    fig, ax = plt.subplots(figsize=(9, 5))
    tmax = float(d['tenure_months'].max())
    grid = np.arange(0, int(np.ceil(tmax)) + 1)
    t_all, s_all = km_curve(d['tenure_months'], d['is_churned'])
    charts['survival_all'] = {'type': 'line', 'title': 'Survival (all accounts)', 'data': xy_list(grid, km_at(t_all, s_all, grid))}
    for p, gp_ in d.groupby(c['PLAN']):
        if len(gp_) < MIN_N:
            continue
        t_, s_ = km_curve(gp_['tenure_months'], gp_['is_churned'])
        ax.step(t_, s_, where='post', label='%s (n=%d)' % (p, len(gp_)))
        charts['survival_plan_' + str(p).lower().replace(' ', '_')] = {'type': 'line', 'title': 'Survival: ' + str(p),
                                                                      'data': xy_list(grid, km_at(t_, s_, grid))}
    ax.set_xlabel('Tenure (months)')
    ax.set_ylabel('Share of accounts still active')
    ax.set_title('Q7. Is retention improving? Kaplan-Meier by plan')
    ax.legend()
    savefig(fig, 'reports/07_survival_by_plan.png')
    # 8. correlation heatmap (optional)
    cols = [c['USAGE'], c['LOGIN_AGO'], c['TICKETS'], c['NPS'], c['DAYS_PAY'], c['LATE'], c['BALANCE'],
            c['DISCOUNT'], c['SEATS'], c['MRR0'], c['CAC'], 'engagement_risk_score', 'is_churned']
    cm = d[cols].corr()
    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(cm.values, cmap='coolwarm', vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=75, ha='right', fontsize=8)
    ax.set_yticks(range(len(cols)))
    ax.set_yticklabels(cols, fontsize=8)
    fig.colorbar(im)
    ax.set_title('Correlation heatmap (optional chart 8)')
    savefig(fig, 'reports/08_correlation_heatmap.png')
    charts['correlation_heatmap'] = {'type': 'heatmap', 'title': 'Correlation heatmap', 'data': xy_list(
        ['%s | %s' % (a, b) for a in cols for b in cols], [cm.loc[a, b] for a in cols for b in cols])}
    add_charts(charts)
    return charts, ch_t
