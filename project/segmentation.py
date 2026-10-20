import os
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from utils import *  # @module-import

SEG_NAMES = {3: ['Champions', 'Stable', 'At-Risk'],
             4: ['Champions', 'Growing', 'Stable', 'At-Risk'],
             5: ['Champions', 'Growing', 'Stable', 'At-Risk', 'Dormant'],
             6: ['Champions', 'Growing', 'Stable', 'Stable (Low Value)', 'At-Risk', 'Dormant']}


def run_segmentation(act, cfg, verbose=True):
    c = cfg
    a = act.reset_index(drop=True)
    cols = ['usage_per_seat', c['LOGIN_AGO'], 'mrr_per_seat', 'tickets_per_seat', c['SEATS'], 'engagement_risk_score']
    res = {'k': None, 'silhouette': None, 'fallback': False, 'summary': pd.DataFrame(), 'traits': {}}
    out = pd.DataFrame({c['ID']: a[c['ID']], 'segment': 'Unsegmented', 'is_anomaly': 0, 'anomaly_reason': ''})
    if len(a) < 30:
        print('Segmentation skipped: fewer than 30 active accounts.')
        res['df'] = out
        return res
    X = a[cols].apply(pd.to_numeric, errors='coerce')
    for k in ['usage_per_seat', 'mrr_per_seat', 'tickets_per_seat', c['SEATS']]:
        X[k] = np.log1p(X[k].clip(lower=0))
    Z = StandardScaler().fit_transform(SimpleImputer(strategy='median').fit_transform(X))
    best_k, best_s = 3, -1.0
    scores = {}
    for k in range(3, 7):
        if len(a) <= k * 5:
            continue
        lab = KMeans(n_clusters=k, n_init=10, random_state=c['RANDOM_STATE']).fit_predict(Z)
        s = float(silhouette_score(Z, lab))
        scores[k] = s
        if s > best_s:
            best_k, best_s = k, s
    print('Silhouette by k:', {k: round(v, 3) for k, v in scores.items()})
    if best_s < 0.25:
        print('Best silhouette %.3f < 0.25 -> documented fallback to k=3.' % best_s)
        best_k, res['fallback'] = 3, True
    km = KMeans(n_clusters=best_k, n_init=10, random_state=c['RANDOM_STATE']).fit(Z)
    lab = km.labels_
    a['_cl'] = lab
    risk_med = a.groupby('_cl')['engagement_risk_score'].median().sort_values()
    names = list(SEG_NAMES[best_k])
    order = list(risk_med.index)
    if best_k >= 5:
        w1, w2 = order[-2], order[-1]
        if a.loc[a['_cl'] == w1, c['LOGIN_AGO']].median() > a.loc[a['_cl'] == w2, c['LOGIN_AGO']].median():
            order[-2], order[-1] = w2, w1
    cmap = {cl: names[i] for i, cl in enumerate(order)}
    a['segment'] = a['_cl'].map(cmap)
    om = a[cols].median()
    for cl, nm in cmap.items():
        sub = a[a['_cl'] == cl]
        dev = {}
        for col in cols:
            cm_, o_ = float(sub[col].median()), float(om[col])
            dev[col] = abs(np.log((abs(cm_) + 0.5) / (abs(o_) + 0.5)))
        top = sorted(dev, key=lambda k: -dev[k])[:3]
        res['traits'][nm] = ['%s: %.1f vs typical %.1f' % (pretty(col), float(sub[col].median()), float(om[col])) for col in top]
    out['segment'] = a['segment'].values
    # anomalies
    acols = [k for k in [c['DAYS_PAY'], c['LATE'], c['BALANCE'], 'balance_to_mrr', c['USAGE'], c['LOGIN_AGO'], c['MRR'], c['SEATS']] if k in a.columns]
    imp2 = SimpleImputer(strategy='median')
    sc2 = StandardScaler()
    Za = sc2.fit_transform(imp2.fit_transform(a[acols].apply(pd.to_numeric, errors='coerce')))
    iso = IsolationForest(n_estimators=300, contamination=c['ANOMALY_CONT'], random_state=c['RANDOM_STATE']).fit(Za)
    flag = (iso.predict(Za) == -1).astype(int)
    j = np.abs(Za).argmax(axis=1)
    reasons = ['%s %s (z=%.1f)' % ('High' if Za[i, j[i]] > 0 else 'Low', pretty(acols[j[i]]), Za[i, j[i]]) for i in range(len(a))]
    out['is_anomaly'] = flag
    out['anomaly_reason'] = [r if f else '' for r, f in zip(reasons, flag)]
    os.makedirs(c['MODELS_DIR'], exist_ok=True)
    joblib.dump({'imputer': imp2, 'scaler': sc2, 'model': iso, 'cols': acols}, os.path.join(c['MODELS_DIR'], 'isolation_forest.pkl'))
    # plot
    pc = PCA(n_components=2, random_state=c['RANDOM_STATE']).fit_transform(Z)
    fig, ax = plt.subplots(figsize=(9, 6))
    for nm in names:
        m = (a['segment'] == nm).values
        if m.any():
            ax.scatter(pc[m, 0], pc[m, 1], s=22, alpha=0.7, label='%s (n=%d)' % (nm, int(m.sum())))
    ax.scatter(pc[flag == 1, 0], pc[flag == 1, 1], s=90, facecolors='none', edgecolors='black', label='Anomaly')
    ax.set_title('Account segments (PCA 2D) and anomalies, k=%d, silhouette=%.2f' % (best_k, best_s))
    ax.legend(fontsize=8)
    savefig(fig, 'reports/06_segments_pca.png')
    arr_col = c['ARR']
    sm = a.groupby('segment').agg(n=(c['ID'], 'size'), arr=(arr_col, 'sum'), avg_churn_prob=('churn_prob', 'mean'),
                                  avg_engagement_risk=('engagement_risk_score', 'mean')).reset_index()
    sm['arr_share_pct'] = sm['arr'] / max(sm['arr'].sum(), 1e-9) * 100
    sm['traits'] = sm['segment'].map(lambda s: ' | '.join(res['traits'].get(s, [])))
    res.update({'k': int(best_k), 'silhouette': best_s, 'summary': sm})
    res['df'] = out
    res['anomalies'] = a.loc[flag == 1, [c['ID'], c['COMPANY'], arr_col]].assign(reason=[r for r, f in zip(reasons, flag) if f])
    pd.DataFrame({c['ID']: a[c['ID']], c['COMPANY']: a[c['COMPANY']], 'segment': a['segment'], 'is_anomaly': flag,
                  'anomaly_reason': out['anomaly_reason'], 'ARR': a[arr_col]}).to_csv(
        'data/processed/ml_task2_output.csv', index=False, encoding='utf-8')
    save_json(os.path.join(c['REPORTS_DIR'], 'segments_summary.json'), {'k': best_k, 'silhouette': best_s, 'fallback_k3': res['fallback'],
                                                                         'segments': sm})
    return res
