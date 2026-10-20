import os
import json
import math
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
warnings.filterwarnings('ignore')

BAD_CHAR = chr(0xfffd)


def clean_str(x):
    return str(x).replace(BAD_CHAR, '-')


def sdiv(a, b, fill=np.nan):
    """Guarded division: zero / missing denominators give `fill` (never inf)."""
    a = a.astype('float64') if isinstance(a, pd.Series) else pd.Series(a, dtype='float64')
    b = b.astype('float64') if isinstance(b, pd.Series) else pd.Series(b, index=a.index, dtype='float64')
    out = a / b.where(b != 0)
    return out.replace([np.inf, -np.inf], np.nan).fillna(fill)


def num(s):
    """Parse numeric text such as '$1,200' or '12%' safely."""
    if pd.api.types.is_numeric_dtype(s):
        return s.astype('float64')
    t = s.astype(str).str.replace(r'[\$,%\s]', '', regex=True)
    return pd.to_numeric(t.replace({'nan': np.nan, 'None': np.nan, '': np.nan}), errors='coerce')


def jsonable(o):
    if isinstance(o, dict):
        return {clean_str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.ndarray, pd.Series, pd.Index)):
        return [jsonable(v) for v in list(o)]
    if isinstance(o, pd.DataFrame):
        return [jsonable(r) for r in o.to_dict('records')]
    if o is None or o is pd.NaT:
        return None
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        v = float(o)
        return None if (math.isnan(v) or math.isinf(v)) else round(v, 4)
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    if isinstance(o, str):
        return o.replace(BAD_CHAR, '-')
    try:
        if pd.isna(o):
            return None
    except (TypeError, ValueError):
        return clean_str(o)
    return clean_str(o)


def save_json(path, obj):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(jsonable(obj), fh, indent=2, ensure_ascii=False)


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def ensure_dirs(cfg):
    for d in ['data/raw', 'data/processed', cfg['REPORTS_DIR'], cfg['MODELS_DIR'], 'config',
              'output/understand/charts', 'output/decide/simulations', 'output/monitor', 'output/meta']:
        os.makedirs(d, exist_ok=True)


def savefig(fig, path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.show()
    plt.close(fig)


def add_charts(new_charts, path='reports/chart_data.json'):
    cur = load_json(path, {}) or {}
    cur.update(jsonable(new_charts))
    save_json(path, cur)


def xy_list(x, y):
    return [{'label': clean_str(a), 'value': (None if pd.isna(b) else round(float(b), 4))} for a, b in zip(x, y)]


def pretty(name):
    n = str(name)
    for p in ('num__', 'cat__'):
        if n.startswith(p):
            n = n[len(p):]
    return n.replace('_', ' ')


def km_curve(durations, events):
    """Kaplan-Meier (numpy only). Returns (times, survival) with times[0]=0, S[0]=1."""
    d = np.asarray(durations, dtype=float)
    e = np.asarray(events, dtype=float)
    m = ~np.isnan(d) & ~np.isnan(e)
    d, e = d[m], e[m]
    if len(d) == 0 or (e > 0).sum() == 0:
        return np.array([0.0]), np.array([1.0])
    ds = np.sort(d)
    ev = np.sort(d[e > 0])
    ut = np.unique(ev)
    at_risk = len(ds) - np.searchsorted(ds, ut, side='left')
    deaths = np.searchsorted(ev, ut, side='right') - np.searchsorted(ev, ut, side='left')
    surv = np.cumprod(1.0 - deaths / at_risk)
    return np.concatenate([[0.0], ut]), np.concatenate([[1.0], surv])


def km_at(times, surv, t):
    idx = np.searchsorted(times, np.maximum(np.asarray(t, dtype=float), 0.0), side='right') - 1
    return surv[np.clip(idx, 0, len(surv) - 1)]

import os
import sys
import datetime
import numpy as np
import pandas as pd
import joblib

ALLOWED_CHART_TYPES = ['bar', 'line', 'scatter', 'histogram', 'heatmap']


def load_cfg():
    cfg = load_json('config/pipeline_config.json')
    if cfg is None:
        raise FileNotFoundError('config/pipeline_config.json missing: run the pipeline first.')
    return cfg


def load_master(cfg):
    bq = cfg.get('BIGQUERY', {}) or {}
    df, source = None, 'csv'
    if bq.get('project_id') and bq.get('dataset'):
        try:
            from google.cloud import bigquery
            cred = bq.get('credentials_file')
            if cred and os.path.exists(cred):
                os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', cred)
            client = bigquery.Client(project=bq['project_id'])
            df = client.query('SELECT * FROM `%s.%s.%s`' % (bq['project_id'], bq['dataset'], bq.get('table', 'feat'))).to_dataframe()
            if cfg['ID'] not in df.columns or 'churn_prob' not in df.columns:
                raise ValueError('BigQuery table lacks account-master columns (needs churn_prob etc.)')
            source = 'bigquery'
        except Exception as e:
            print('BigQuery unavailable -> CSV fallback (%s)' % clean_str(e)[:150])
            df, source = None, 'csv'
    if df is None:
        path = 'data/processed/account_master.csv'
        if not os.path.exists(path):
            raise FileNotFoundError('account_master.csv missing: run the pipeline first.')
        df = pd.read_csv(path, encoding='utf-8')
    return df, source


def _safe(errors, name, fn):
    try:
        fn()
    except Exception as e:
        errors.append('%s: %s' % (name, clean_str(e)[:200]))
        print('WARNING (continuing):', name, '->', clean_str(e)[:200])


def main():
    errors = []
    cfg = load_cfg()
    m, source = load_master(cfg)
    c = cfg
    O = 'output/'
    act = m[m[c['STATUS']] == c['ACTIVE_VALUE']]
    lab = m[m['is_churned'].notna()]
    card = load_json(os.path.join(c['REPORTS_DIR'], 'model_card.json'), {}) or {}
    prog = load_json(os.path.join(c['REPORTS_DIR'], 'goal_progress.json'), {}) or {}
    ret = prog.get('retention_detail', {})
    mt = card.get('metrics_holdout', {})
    pair = m.dropna(subset=[c['LIFE_GP'], c['CAC']])
    kpis = {'total_accounts': int(len(m)), 'active_accounts': int(len(act)), 'ARR': float(act[c['ARR']].sum()), 'MRR': float(act[c['MRR']].sum()),
            'logo_churn_pct': float((lab['is_churned'] == 1).mean() * 100) if len(lab) else None,
            'revenue_churn_pct': float(lab.loc[lab['is_churned'] == 1, c['MRR0']].sum() / max(lab[c['MRR0']].sum(), 1e-9) * 100) if len(lab) else None,
            'GRR_pct': ret.get('grr_pct'), 'NRR_pct': ret.get('nrr_pct'), 'ARPA': float(act[c['MRR']].sum() / max(len(act), 1)),
            'avg_ltv_cac_pooled': float(pair[c['LIFE_GP']].sum() / max(pair[c['CAC']].sum(), 1e-9)),
            'avg_payback_months': float(m[c['PAYBACK']].mean()), 'ARR_at_risk': float(act['arr_at_risk'].sum()) if 'arr_at_risk' in act else None,
            'P1_count': int((act['priority'] == 'P1').sum()) if 'priority' in act else 0,
            'model_pr_auc': mt.get('pr_auc'), 'model_roc_auc': mt.get('roc_auc'), 'scoring_source': card.get('primary_scoring', 'rule'),
            'snapshot_note': 'GRR/NRR are snapshot approximations'}
    save_json(O + 'understand/kpis.json', kpis)

    def seg():
        s = load_json(os.path.join(c['REPORTS_DIR'], 'segments_summary.json'))
        if s is None and 'segment' in m:
            s = {'segments': m[m[c['STATUS']] == c['ACTIVE_VALUE']].groupby('segment').agg(n=(c['ID'], 'size'), arr=(c['ARR'], 'sum')).reset_index()}
        save_json(O + 'understand/segments.json', s)
    _safe(errors, 'segments', seg)

    def anom():
        a = act[act['is_anomaly'] == 1][[c['ID'], c['COMPANY'], c['ARR'], 'anomaly_reason']] if 'is_anomaly' in act else pd.DataFrame()
        save_json(O + 'understand/anomalies.json', {'count': int(len(a)), 'items': a})
    _safe(errors, 'anomalies', anom)

    def charts():
        ch = load_json(os.path.join(c['REPORTS_DIR'], 'chart_data.json'), {}) or {}
        n = 0
        for name, v in ch.items():
            if v.get('type') not in ALLOWED_CHART_TYPES:
                v['type'] = 'bar'
            save_json(O + 'understand/charts/%s.json' % name, v)
            n += 1
        print('Charts exported:', n)
    _safe(errors, 'charts', charts)

    def decide():
        save_json(O + 'decide/insights.json', load_json(os.path.join(c['REPORTS_DIR'], 'insights.json'), []))
        cols = [k for k in [c['ID'], c['COMPANY'], c['PLAN'], 'priority', 'churn_prob', 'churn_band', c['ARR'], 'arr_at_risk', 'alerts', 'recommendation', 'drivers', 'segment'] if k in act.columns]
        rec = act.sort_values(['priority', 'arr_at_risk'], ascending=[True, False])[cols].head(200)
        save_json(O + 'decide/recommendations.json', {'accounts': rec})
        save_json(O + 'decide/goals.json', load_json('config/goals.json', {}))
        if not os.path.exists(O + 'decide/simulations'):
            os.makedirs(O + 'decide/simulations')
    _safe(errors, 'decide', decide)

    def monitor():
        fm = load_json(os.path.join(c['REPORTS_DIR'], 'forecast_meta.json'), {})
        mf = pd.read_csv('data/processed/forecast_output.csv') if os.path.exists('data/processed/forecast_output.csv') else pd.DataFrame()
        save_json(O + 'monitor/forecast.json', {'monthly': mf, 'meta': fm})
        save_json(O + 'monitor/goal_progress.json', prog)
        save_json(O + 'monitor/alerts.json', load_json(os.path.join(c['REPORTS_DIR'], 'alerts.json'), []))
    _safe(errors, 'monitor', monitor)

    def meta():
        summ = dict(kpis)
        if 'priority' in act:
            summ['P1_P2_arr_at_risk'] = float(act.loc[act['priority'].isin(['P1', 'P2']), 'arr_at_risk'].sum())
        save_json(O + 'meta/summary.json', summ)
        save_json(O + 'meta/terminology.json', c['TERMINOLOGY'])
    _safe(errors, 'meta', meta)

    def contract():
        fields = []
        fc_path = os.path.join(c['MODELS_DIR'], 'feature_cols.pkl')
        if os.path.exists(fc_path):
            fcx = joblib.load(fc_path)
            for k in fcx['all']:
                fields.append({'name': k, 'type': fcx['types'][k], 'range': fcx['ranges'][k]})
        save_json('frontend_contract.json', {
            'project': {'name': 'SaaS Revenue Retention', 'domain': 'b2b_saas_subscription', 'client_id': c['CLIENT_ID'], 'description': 'Churn risk, unit economics and MRR forecast'},
            'terminology': c['TERMINOLOGY'],
            'outcomes': {'understand': {'kpis': 'understand/kpis.json', 'charts': 'understand/charts/', 'segments': 'understand/segments.json', 'anomalies': 'understand/anomalies.json'},
                         'decide': {'insights': 'decide/insights.json', 'recommendations': 'decide/recommendations.json', 'simulations': 'decide/simulations/', 'goals': 'decide/goals.json'},
                         'monitor': {'forecast': 'monitor/forecast.json', 'goal_progress': 'monitor/goal_progress.json', 'alerts': 'monitor/alerts.json'}},
            'model': {'type': 'calibrated_classifier', 'pkl_file': 'models/best_classifier.pkl', 'input_fields': fields, 'output_label': 'churn_probability', 'horizon': '90 days'},
            'source': {'type': source}, 'frontend': {'framework': 'vanilla HTML/JS', 'deploy_target': 'cloudflare_pages'}, 'saas_ready': True})
    _safe(errors, 'frontend_contract', contract)
    save_json(O + 'meta/run_log.json', {'timestamp': datetime.datetime.now().isoformat(timespec='seconds'), 'rows': int(len(m)), 'source_type': source,
                                       'model_metrics': mt, 'scoring_source': kpis['scoring_source'], 'errors': errors})
    print('export_for_frontend: done (source=%s, %d warnings)' % (source, len(errors)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('export_for_frontend failed gracefully:', clean_str(exc))
        save_json('output/meta/run_log.json', {'timestamp': datetime.datetime.now().isoformat(timespec='seconds'), 'errors': [clean_str(exc)]})
