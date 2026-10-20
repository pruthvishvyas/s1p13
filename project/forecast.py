import os
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from utils import *  # @module-import
from classify import make_pre  # @module-import


def _curves(d, cfg, min_n=30):
    c = cfg
    out = {('ALL',): km_curve(d['tenure_months'], d['is_churned'])}
    for p, g in d.groupby(c['PLAN']):
        if len(g) >= min_n:
            out[(p,)] = km_curve(g['tenure_months'], g['is_churned'])
    for (p, cy), g in d.groupby([c['PLAN'], c['CYCLE']]):
        if len(g) >= min_n:
            out[(p, cy)] = km_curve(g['tenure_months'], g['is_churned'])
    return out


def _paths(a, curves, cfg, H):
    """Conditional survival S(t+h)/S(t), h=1..H, using Plan x Cycle curve (n>=30) -> Plan -> pooled."""
    c = cfg
    n = len(a)
    cond = np.ones((n, H))
    hs = np.arange(1, H + 1)
    tt = a['tenure_months'].values
    plans, cyc = a[c['PLAN']].values, a[c['CYCLE']].values
    for i in range(n):
        s0, times, S = 1.0, None, None
        for key in ((plans[i], cyc[i]), (plans[i],), ('ALL',)):
            if key in curves:
                times, S = curves[key]
                s0 = float(km_at(times, S, tt[i]))
                if s0 > 0.05 or key == ('ALL',):
                    break
        cond[i] = np.clip(km_at(times, S, tt[i] + hs) / max(s0, 1e-6), 0, 1)
    return np.minimum.accumulate(cond, axis=1)


def _blend(cond, p, H):
    """Blend 3-month survival: average of survival-curve value and (1 - classifier churn_prob); rescale the path."""
    hs = np.arange(1, H + 1) / 3.0
    c3 = cond[:, 2]
    b3 = 0.5 * c3 + 0.5 * (1 - np.asarray(p, dtype=float))
    ok = c3 > 1e-6
    adj = np.where(ok, b3 / np.maximum(c3, 1e-6), 0.0)
    path = np.where(ok[:, None], cond * adj[:, None] ** hs[None, :], np.maximum(b3, 0)[:, None] ** hs[None, :])
    return np.minimum.accumulate(np.clip(path, 0, 1), axis=1)


def backtest(d, cfg, as_of, months=3, min_n=30):
    c = cfg
    cut = as_of - pd.DateOffset(months=months)
    e = d[d[c['SIGNUP']] < cut].copy()
    churned = e['is_churned'] == 1
    ended = churned & (e['end_date'] <= cut)
    alive = ~ended
    endc = e['end_date'].where(e['end_date'] <= cut, cut)
    e['tenure_months'] = ((endc - e[c['SIGNUP']]).dt.days / 30.4375).clip(lower=0)
    e['is_churned'] = ended.astype(int)
    if len(e) < 100 or int(alive.sum()) < min_n or int(ended.sum()) < 10:
        return {'available': False, 'reason': 'not enough history to hold out the last %d months' % months}
    curves = _curves(e, c, min_n)
    a = e[alive].copy()
    cond = _paths(a, curves, c, months)[:, months - 1]
    still = (d.loc[a.index, 'is_churned'] == 0).values
    w = a[c['MRR0']].fillna(0).values
    exp_, act_ = float((w * cond).sum()), float((w * still).sum())
    mape = abs(exp_ - act_) / max(act_, 1e-9) * 100
    per = {}
    for p, g in a.groupby(c['PLAN']):
        if len(g) >= c['MIN_GROUP_N']:
            ix = a.index.get_indexer(g.index)
            ge, ga = float((w[ix] * cond[ix]).sum()), float((w[ix] * still[ix]).sum())
            per[str(p)] = {'n': int(len(g)), 'expected': ge, 'actual': ga, 'abs_pct_error': abs(ge - ga) / max(ga, 1e-9) * 100}
    return {'available': True, 'months_held_out': months, 'expected_retained_mrr': exp_, 'actual_retained_mrr': act_,
            'mape_pct': mape, 'per_plan': per, 'n_accounts': int(len(a)),
            'label': 'backtested' if mape <= 10 else 'indicative'}


def expansion_model(act, cfg):
    c = cfg
    a = act[act[c['EXPANSION']].notna()].copy()
    if len(a) < 150:
        return {'used': False, 'reason': 'fewer than 150 active rows (%d)' % len(a)}, None
    num = [k for k in [c['USAGE'], c['LOGIN_AGO'], c['TICKETS'], c['NPS'], c['SEATS'], c['DISCOUNT'], c['DAYS_PAY'],
                       'engagement_risk_score', 'mrr_per_seat', 'tenure_months'] if k in a.columns]
    cat = [c['PLAN'], c['INDUSTRY'], c['REGION'], c['SIZE'], c['CHANNEL']]
    X = a[num + cat].copy()
    for k in cat:
        X[k] = X[k].astype(object).where(X[k].notna(), np.nan)
    y = a[c['EXPANSION']].values
    pipe = Pipeline([('pre', make_pre(num, cat)), ('reg', GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=c['RANDOM_STATE']))])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=c['TEST_SIZE'], random_state=c['RANDOM_STATE'])
    pipe.fit(Xtr, ytr)
    pr = pipe.predict(Xte)
    mae, r2 = float(mean_absolute_error(yte, pr)), float(r2_score(yte, pr))
    if r2 < 0.1:
        return {'used': False, 'mae': mae, 'r2': r2, 'reason': 'R2 %.3f < 0.1: expansion is not predictable from these signals; regression dropped' % r2}, None
    pipe.fit(X, y)
    return {'used': True, 'mae': mae, 'r2': r2}, pd.Series(pipe.predict(X), index=a.index)


def run_forecast(df, cfg, as_of, verbose=True):
    c = cfg
    H, B = int(c['FORECAST_MONTHS']), int(c['BOOTSTRAP'])
    d = df[df['is_churned'].notna()].reset_index(drop=True)
    a = d[d['is_churned'] == 0].reset_index(drop=True)
    meta = {'horizon_months': H, 'method': 'Kaplan-Meier by Plan x Billing_Cycle (n>=30, else Plan, else pooled), conditional on tenure; '
            '3-month survival blended 50/50 with classifier churn_prob; bands from %d bootstrap resamples (10th/90th pct)' % B,
            'blend_note': 'bands reflect survival-curve uncertainty only; churn_prob held fixed'}
    if len(d) < 100 or int(d['is_churned'].sum()) < 10 or len(a) == 0:
        print('Forecast skipped: not enough accounts/churn events.')
        meta['available'] = False
        save_json(os.path.join(c['REPORTS_DIR'], 'forecast_meta.json'), meta)
        return {'monthly': pd.DataFrame(), 'accounts': pd.DataFrame(), 'meta': meta}
    curves = _curves(d, c)
    p = a['churn_prob'].fillna(a['churn_prob'].mean()).values
    mrr = a[c['MRR']].fillna(a[c['MRR0']]).fillna(0).values
    cond = _paths(a, curves, c, H)
    path = _blend(cond, p, H)
    base = (mrr[:, None] * path).sum(axis=0)
    rng = np.random.default_rng(c['RANDOM_STATE'])
    sims = np.zeros((B, H))
    for b in range(B):
        ix = rng.integers(0, len(d), len(d))
        cb = _curves(d.iloc[ix], c)
        sims[b] = (mrr[:, None] * _blend(_paths(a, cb, c, H), p, H)).sum(axis=0)
    low = np.minimum(np.percentile(sims, 10, axis=0), base)
    high = np.maximum(np.percentile(sims, 90, axis=0), base)
    now = float(mrr.sum())
    labels = [str((as_of + pd.DateOffset(months=h)).strftime('%Y-%m')) for h in range(0, H + 1)]
    monthly = pd.DataFrame({'month_index': range(0, H + 1), 'month': labels,
                            'mrr_base': [now] + list(base), 'mrr_worst': [now] + list(low), 'mrr_best': [now] + list(high)})
    monthly['arr_base'] = monthly['mrr_base'] * 12
    monthly['pct_vs_now'] = (monthly['mrr_base'] / max(now, 1e-9) - 1) * 100
    monthly.to_csv('data/processed/forecast_output.csv', index=False, encoding='utf-8')
    acc = pd.DataFrame({c['ID']: a[c['ID']], c['COMPANY']: a[c['COMPANY']], 'current_mrr': mrr,
                        'survival_90d': path[:, 2], 'exp_mrr_3m': mrr * path[:, 2], 'exp_mrr_%dm' % H: mrr * path[:, H - 1]})
    bt = backtest(d, c, as_of)
    meta['backtest'] = bt
    meta['label'] = bt.get('label', 'indicative') if bt.get('available') else 'indicative'
    if bt.get('available'):
        print('Backtest (last 3 months held out): MAPE %.1f%% -> forecast labelled "%s"' % (bt['mape_pct'], meta['label']))
    else:
        print('Backtest unavailable (%s) -> forecast labelled "indicative"' % bt.get('reason'))
    reg_info, reg_pred = expansion_model(a, c)
    meta['expansion_model'] = reg_info
    if reg_pred is not None:
        acc['expansion_pred_pct'] = reg_pred.values
    else:
        print('Expansion regression:', reg_info.get('reason'))
    acc.to_csv('data/processed/forecast_accounts.csv', index=False, encoding='utf-8')
    surv = {str(k): {'times': v[0].tolist(), 'survival': v[1].tolist()} for k, v in curves.items()}
    joblib.dump({'survival_tables': surv, 'params': {'horizon': H, 'bootstrap': B, 'as_of': str(as_of.date()), 'blend': 0.5}},
                os.path.join(c['MODELS_DIR'], 'forecast_model.pkl'))
    save_json(os.path.join(c['REPORTS_DIR'], 'forecast_meta.json'), meta)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(monthly['month'], monthly['mrr_base'], marker='o', label='Base')
    ax.fill_between(monthly['month'], monthly['mrr_worst'], monthly['mrr_best'], alpha=0.25, label='10th-90th pct band')
    ax.set_title('6-month MRR run-off of the current active base (%s)' % meta['label'])
    ax.set_ylabel('MRR')
    ax.legend()
    ax.tick_params(axis='x', rotation=45)
    savefig(fig, 'reports/07_mrr_forecast.png')
    add_charts({'forecast_mrr_base': {'type': 'line', 'title': 'MRR run-off (base)', 'data': xy_list(monthly['month'], monthly['mrr_base'])},
                'forecast_mrr_worst': {'type': 'line', 'title': 'MRR run-off (worst)', 'data': xy_list(monthly['month'], monthly['mrr_worst'])},
                'forecast_mrr_best': {'type': 'line', 'title': 'MRR run-off (best)', 'data': xy_list(monthly['month'], monthly['mrr_best'])}})
    meta['available'] = True
    return {'monthly': monthly, 'accounts': acc, 'meta': meta}
