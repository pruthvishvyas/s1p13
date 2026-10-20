import os
import re
import numpy as np
import pandas as pd
from utils import *  # @module-import

NULL_TOKENS = ['', 'nan', 'NaN', 'None', 'NULL', 'null', 'N/A', 'n/a', 'NA']
COLKEYS = ['ID', 'COMPANY', 'INDUSTRY', 'REGION', 'SIZE', 'CHANNEL', 'SIGNUP', 'PLAN', 'CYCLE', 'SEATS',
           'LIST_PRICE', 'DISCOUNT', 'MRR0', 'MRR', 'EXPANSION', 'STATUS', 'CHURN_DATE', 'MONTHS', 'REASON',
           'CAC', 'GM', 'LIFE_REV', 'LIFE_GP', 'LTV_CAC', 'PAYBACK', 'USAGE', 'LOGIN_AGO', 'TICKETS', 'NPS',
           'DAYS_PAY', 'LATE', 'BALANCE', 'HEALTH', 'RISK', 'ARR']
NUMKEYS = ['SEATS', 'LIST_PRICE', 'DISCOUNT', 'MRR0', 'MRR', 'EXPANSION', 'MONTHS', 'CAC', 'GM', 'LIFE_REV',
           'LIFE_GP', 'LTV_CAC', 'PAYBACK', 'USAGE', 'LOGIN_AGO', 'TICKETS', 'NPS', 'DAYS_PAY', 'LATE',
           'BALANCE', 'HEALTH', 'ARR']


def load_raw(cfg):
    path = cfg['RAW_CSV']
    if not os.path.exists(path):
        found = []
        if os.path.isdir('data/raw'):
            found = [os.path.join('data/raw', f) for f in os.listdir('data/raw') if f.lower().endswith('.csv')]
        if len(found) == 1:
            path = found[0]
            print('RAW_CSV not found; using the only CSV in data/raw:', path)
        else:
            raise FileNotFoundError('Raw data not found at %s. Put your CSV there (or fix CONFIG["RAW_CSV"]). '
                                    'CSV files seen in data/raw: %s' % (cfg['RAW_CSV'], found))
    df = pd.read_csv(path, encoding='utf-8-sig')
    df.columns = [str(x).strip() for x in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace({t: np.nan for t in NULL_TOKENS})
    print('Loaded %s rows x %s columns from %s' % (len(df), df.shape[1], path))
    return df


def _check(df, idcol, a, e, abs_tol, rel_tol=0.01):
    a = pd.to_numeric(a, errors='coerce')
    e = pd.to_numeric(e, errors='coerce')
    m = a.notna() & e.notna()
    if not m.any():
        return {'pass_rate': None, 'n_checked': 0, 'failed_ids': []}
    ok = (a - e).abs() <= np.maximum(abs_tol, rel_tol * e.abs())
    bad = m & ~ok
    return {'pass_rate': round(float(ok[m].mean()), 4), 'n_checked': int(m.sum()),
            'failed_ids': df.loc[bad, idcol].astype(str).head(25).tolist()}


def validate(df, cfg, verbose=True):
    c = cfg
    T = c['THRESHOLDS']
    exp_cols = [c[k] for k in COLKEYS]
    missing = [x for x in exp_cols if x not in df.columns]
    extra = [x for x in df.columns if x not in exp_cols]
    print('Schema: %d columns in file, %d mapped in CONFIG (brief says 36; the header lists %d).'
          % (df.shape[1], len(exp_cols), df.shape[1]))
    print('Missing columns:', missing or 'none', '| Extra columns:', extra or 'none')
    if missing:
        raise ValueError('Missing required columns %s. Fix the CSV or CONFIG.' % missing)
    df = df.copy()
    if verbose:
        for k in ['STATUS', 'PLAN', 'CYCLE', 'REGION', 'INDUSTRY', 'SIZE', 'CHANNEL', 'RISK', 'REASON', 'NPS']:
            print('\n--- value_counts: %s ---' % c[k])
            print(df[c[k]].value_counts(dropna=False).head(15).to_string())
    st = df[c['STATUS']].astype(str).str.strip().str.lower()
    ch_v, ac_v = c['CHURNED_VALUE'].lower(), c['ACTIVE_VALUE'].lower()
    if not ({ch_v, ac_v} <= set(st.unique())):
        raise ValueError('Status values %s do not contain CONFIG CHURNED_VALUE=%r and ACTIVE_VALUE=%r. '
                         'Fix CONFIG in Phase 0.' % (sorted(st.unique()), c['CHURNED_VALUE'], c['ACTIVE_VALUE']))
    is_ch, is_ac = st == ch_v, st == ac_v
    unparse = {}
    for k in ['SIGNUP', 'CHURN_DATE']:
        raw = df[c[k]]
        parsed = pd.to_datetime(raw, errors='coerce')
        unparse[c[k]] = int((raw.notna() & parsed.isna()).sum())
        df[c[k]] = parsed
    print('Unparseable dates:', unparse)

    def N(k):
        return num(df[c[k]])

    if c['AS_OF_DATE']:
        as_of = pd.Timestamp(c['AS_OF_DATE'])
    else:
        as_of = (df[c['SIGNUP']] + pd.to_timedelta(N('MONTHS') * 30.4375, unit='D')).max()
    if pd.isna(as_of):
        raise ValueError('Cannot infer as-of date; set CONFIG["AS_OF_DATE"].')
    as_of = pd.Timestamp(as_of).normalize()
    print('As-of date used:', as_of.date(), '(CONFIG AS_OF_DATE override available)')

    idc = c['ID']
    seats, lp, disc = N('SEATS'), N('LIST_PRICE'), N('DISCOUNT')
    m0, m1, gm, cac = N('MRR0'), N('MRR'), N('GM'), N('CAC')
    exp_m0 = seats * lp * (1 - disc / 100.0)
    annual = df[c['CYCLE']].astype(str).str.lower().str.contains('annual|year')
    use_12 = annual & ((m0 - exp_m0 / 12.0).abs() < (m0 - exp_m0).abs())
    exp_m0 = exp_m0.where(~use_12, exp_m0 / 12.0)
    integ = {}
    integ['initial_mrr_formula'] = _check(df, idc, m0, exp_m0, 0.06)
    integ['initial_mrr_formula']['annual_rows_normalized_by_12'] = int(use_12.sum())
    integ['current_mrr_formula'] = _check(df, idc, m1, m0 * (1 + N('EXPANSION') / 100.0), 0.06)
    arr = N('ARR')
    integ['arr_formula_active'] = _check(df[is_ac], idc, arr[is_ac], (m1 * 12)[is_ac], 0.6)
    arr_zero = float((arr[is_ch] == 0).mean()) if is_ch.any() else None
    integ['arr_churned_zero_share'] = arr_zero
    integ['lifetime_gp_formula'] = _check(df, idc, N('LIFE_GP'), N('LIFE_REV') * gm / 100.0, 0.02)
    integ['ltv_cac_formula'] = _check(df, idc, N('LTV_CAC'), sdiv(N('LIFE_GP'), cac), 0.011)
    integ['payback_formula'] = _check(df, idc, N('PAYBACK'), sdiv(cac, m0 * gm / 100.0), 0.06)
    ok_ch = df.loc[is_ch, c['CHURN_DATE']].notna() & df.loc[is_ch, c['REASON']].notna()
    ok_ac = df.loc[is_ac, c['CHURN_DATE']].isna() & df.loc[is_ac, c['REASON']].isna()
    tot = int(is_ch.sum() + is_ac.sum())
    integ['status_vs_churn_fields'] = {'pass_rate': round(float((ok_ch.sum() + ok_ac.sum()) / max(tot, 1)), 4),
                                       'n_checked': tot,
                                       'failed_ids': pd.concat([df.loc[ok_ch[~ok_ch].index, idc],
                                                                df.loc[ok_ac[~ok_ac].index, idc]]).astype(str).head(25).tolist()}
    end = pd.Series(as_of, index=df.index).where(~(is_ch & df[c['CHURN_DATE']].notna()), df[c['CHURN_DATE']])
    mths = (end - df[c['SIGNUP']]).dt.days / 30.4375
    integ['months_active_vs_dates'] = _check(df, idc, N('MONTHS'), mths, 1.0, rel_tol=0.0)
    tol_ok = {}
    for k, v in integ.items():
        if isinstance(v, dict) and v.get('pass_rate') is not None:
            tol_ok[k] = bool(v['pass_rate'] >= 0.99)
    print('\nIntegrity pass rates (tolerance: >= 99% of rows):')
    for k, v in integ.items():
        if isinstance(v, dict):
            print('  %-28s pass=%s  n=%s  %s' % (k, v.get('pass_rate'), v.get('n_checked'),
                                               'OK' if tol_ok.get(k, True) else '<-- REVIEW'))
    print('  ARR share equal to 0 on churned rows:', arr_zero)

    rv = {}
    for key, lo, hi in [('DISCOUNT', 0, 100), ('GM', 0, 100), ('USAGE', 0, None), ('NPS', 0, 10),
                        ('HEALTH', 0, 100), ('SEATS', 1, None), ('MRR', 0, None), ('MRR0', 0, None), ('CAC', 0, None)]:
        v = N(key)
        bad = pd.Series(False, index=v.index)
        if lo is not None:
            bad |= v < lo
        if hi is not None:
            bad |= v > hi
        rv[c[key]] = int(bad.sum())
    umax = N('USAGE').max()
    usage_scale = 100.0 if (pd.notna(umax) and umax > 1.5) else 1.0
    if usage_scale == 1.0:
        print('NOTE: usage score looks like a 0-1 scale; thresholds are rescaled automatically.')
    elif umax > 100:
        rv[c['USAGE']] = int((N('USAGE') > 100).sum())
    print('Range violations:', rv)

    n_ch, n_ac = int(is_ch.sum()), int(is_ac.sum())
    ml_ok = bool(len(df) >= 200 and n_ch >= 30 and n_ac >= 30)
    if not ml_ok:
        print('MINIMUM-DATA GATE FAILED (need >=200 rows and >=30 per class): ML phases fall back to rules.')
    rep = {'rows': int(len(df)), 'cols': int(df.shape[1]),
           'null_counts': {k: int(v) for k, v in df.isna().sum().items()},
           'integrity': integ, 'integrity_ok': tol_ok,
           'target_balance': {'churned': n_ch, 'active': n_ac, 'other': int(len(df) - n_ch - n_ac),
                              'churn_rate': float(n_ch / max(n_ch + n_ac, 1))},
           'schema_ok': True, 'min_rows_ok': bool(len(df) >= 200), 'ml_ok': ml_ok,
           'unparseable_dates': unparse, 'range_violations': rv, 'usage_scale': usage_scale,
           'as_of_date': str(as_of.date()), 'extra_columns': extra, 'thresholds_assumed': c['THRESHOLDS']}
    save_json('data/processed/validation_report.json', rep)
    return df, rep, as_of


def _canon(s):
    t = s.astype('string').str.strip().str.replace(r'\s+', ' ', regex=True)
    key = t.str.lower()
    top = t.groupby(key).agg(lambda x: x.value_counts().index[0])
    out = key.map(top).astype(object)
    return out.where(out.notna(), np.nan)


def clean(df, cfg, as_of, verbose=True):
    c = cfg
    df = df.copy()
    rep = {}
    for k in ['ID', 'COMPANY', 'INDUSTRY', 'REGION', 'SIZE', 'CHANNEL', 'PLAN', 'CYCLE', 'STATUS', 'REASON', 'RISK']:
        df[c[k]] = _canon(df[c[k]])
    lowmap = {c['CHURNED_VALUE'].lower(): c['CHURNED_VALUE'], c['ACTIVE_VALUE'].lower(): c['ACTIVE_VALUE']}
    df[c['STATUS']] = df[c['STATUS']].astype(str).str.lower().map(lowmap)
    for k in NUMKEYS:
        df[c[k]] = num(df[c[k]])
    n0 = len(df)
    df = df[df[c['ID']].notna()].drop_duplicates(subset=[c['ID']], keep='last').reset_index(drop=True)
    rep['duplicates_removed'] = int(n0 - len(df))
    print('Duplicate/blank IDs removed:', rep['duplicates_removed'])
    df['company_dup_flag'] = (df[c['COMPANY']].duplicated(keep=False) & df[c['COMPANY']].notna()).astype(int)
    print('Rows sharing a Company name (flagged, not dropped):', int(df['company_dup_flag'].sum()))
    neg = {}
    for k in ['LIST_PRICE', 'MRR0', 'MRR', 'ARR', 'CAC', 'LIFE_REV', 'LIFE_GP', 'BALANCE']:
        m = df[c[k]] < 0
        neg[c[k]] = int(m.sum())
        df.loc[m, c[k]] = np.nan
    rep['negative_money_set_nan'] = neg
    print('Negative money values set to NaN:', neg)
    caps = {}
    for k in ['SEATS', 'DAYS_PAY', 'TICKETS', 'BALANCE', 'CAC']:
        s = df[c[k]]
        if s.notna().sum() < 20:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        zero_infl = False
        if q3 == q1:
            base = s[s > 0]
            if len(base) < 10:
                continue
            q1, q3 = base.quantile(0.25), base.quantile(0.75)
            zero_infl = True
        iqr = q3 - q1
        lo = -np.inf if zero_infl else q1 - 1.5 * iqr
        hi = q3 + 1.5 * iqr
        if k == 'SEATS':
            lo = max(lo, 1.0)
        n_cap = int(((s < lo) | (s > hi)).sum())
        before = (float(s.min()), float(s.max()))
        df[c[k]] = s.clip(lower=lo, upper=hi)
        caps[c[k]] = {'capped': n_cap, 'before_min_max': before,
                      'after_min_max': (float(df[c[k]].min()), float(df[c[k]].max()))}
        print('IQR cap %-22s capped=%4d  before=%s  after=%s' % (c[k], n_cap, before, caps[c[k]]['after_min_max']))
    rep['iqr_caps'] = caps
    churned = df[c['STATUS']] == c['CHURNED_VALUE']
    active = df[c['STATUS']] == c['ACTIVE_VALUE']
    df['is_churned'] = np.where(churned, 1.0, np.where(active, 0.0, np.nan))
    df['status_label'] = np.where(churned, 'Churned', np.where(active, 'Active', 'Other'))
    est_end = df[c['SIGNUP']] + pd.to_timedelta(df[c['MONTHS']].fillna(0) * 30.4375, unit='D')
    end = pd.Series(pd.Timestamp(as_of), index=df.index)
    end = end.where(~churned, df[c['CHURN_DATE']].fillna(est_end))
    df['end_date'] = end
    df['tenure_months'] = ((end - df[c['SIGNUP']]).dt.days / 30.4375).clip(lower=0.0)
    df['as_of_date'] = pd.Timestamp(as_of)
    df['mrr_lost'] = np.where(churned, np.where(df[c['MRR']] > 0, df[c['MRR']], df[c['MRR0']]), 0.0)
    os.makedirs(os.path.dirname(c['PROCESSED_CSV']), exist_ok=True)
    df.to_csv(c['PROCESSED_CSV'], index=False, encoding='utf-8')
    print('Clean data saved:', c['PROCESSED_CSV'], df.shape)
    return df, rep
