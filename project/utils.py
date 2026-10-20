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
