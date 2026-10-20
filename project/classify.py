import os
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from scipy.stats import loguniform
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.model_selection import (train_test_split, RepeatedStratifiedKFold, StratifiedKFold, cross_validate,
                                     cross_val_predict, cross_val_score, RandomizedSearchCV)
from sklearn.metrics import (roc_auc_score, average_precision_score, brier_score_loss, precision_recall_curve,
                             roc_curve, confusion_matrix, precision_score, recall_score)
from sklearn.inspection import permutation_importance
from utils import *  # @module-import

RULE_COLS = ['inactive_flag', 'low_usage_flag', 'detractor_flag', 'late_payer_flag']
LEAK_EXCLUDED = {
    'Status': 'is the target', 'Churn_Date': 'exists only for churned accounts',
    'Churn_Reason': 'exists only for churned accounts', 'Months_Active': 'depends on how long the account lived',
    'Lifetime_Revenue': 'depends on account lifetime', 'Lifetime_Gross_Profit': 'depends on account lifetime',
    'LTV_to_CAC_Realized': 'depends on account lifetime', 'ltv_cac_ok': 'derived from LTV_to_CAC_Realized',
    'tenure_months': 'survival analysis only', 'Signup_Date': 'proxy of tenure/exposure time',
    'Current_MRR': 'exit-time snapshot (used only to size ARR at risk)',
    'ARR_Current': 'exit-time snapshot (used only to size ARR at risk)'}


def make_pre(num_cols, cat_cols):
    try:
        ohe = OneHotEncoder(handle_unknown='ignore', min_frequency=10, sparse_output=False)
    except TypeError:
        try:
            ohe = OneHotEncoder(handle_unknown='ignore', min_frequency=10, sparse=False)
        except TypeError:
            ohe = OneHotEncoder(handle_unknown='ignore', sparse=False)
    return ColumnTransformer([
        ('num', Pipeline([('imp', SimpleImputer(strategy='median')), ('sc', StandardScaler())]), list(num_cols)),
        ('cat', Pipeline([('imp', SimpleImputer(strategy='most_frequent')), ('oh', ohe)]), list(cat_cols))],
        remainder='drop')


def candidate_features(cfg):
    c = cfg
    num = [c['SEATS'], c['LIST_PRICE'], c['DISCOUNT'], c['MRR0'], c['EXPANSION'], c['CAC'], c['GM'], c['PAYBACK'],
           c['USAGE'], c['LOGIN_AGO'], c['TICKETS'], c['NPS'], c['DAYS_PAY'], c['LATE'], c['BALANCE'],
           'mrr_per_seat', 'usage_per_seat', 'tickets_per_seat', 'balance_to_mrr', 'margin_per_seat',
           'engagement_risk_score', 'expansion_flag', 'contraction_flag', 'inactive_flag', 'low_usage_flag',
           'high_ticket_flag', 'detractor_flag', 'promoter_flag', 'late_payer_flag', 'annual_flag', 'payback_ok',
           'usage_missing', 'login_missing', 'nps_missing']
    cat = [c['PLAN'], c['CYCLE'], c['INDUSTRY'], c['REGION'], c['SIZE'], c['CHANNEL'], 'discount_depth_band',
           'login_recency_band', 'plan_x_cycle', 'size_x_channel']
    return num, cat


def single_auc(s, y):
    s = pd.to_numeric(s, errors='coerce')
    if s.notna().sum() < 10 or s.nunique() < 2:
        return 0.5
    a = roc_auc_score(y, s.fillna(s.median()))
    return float(max(a, 1 - a))


def _is_bucket(health, risk):
    g = pd.DataFrame({'h': pd.to_numeric(health, errors='coerce'), 'r': risk}).dropna()
    if g['r'].nunique() < 2:
        return False
    s = g.groupby('r')['h'].agg(['min', 'max', 'mean']).sort_values('mean', ascending=False)
    return all(s['min'].iloc[i] >= s['max'].iloc[i + 1] for i in range(len(s) - 1))


def select_features(d, y, cfg, verbose=True):
    c = cfg
    num, cat = candidate_features(cfg)
    excluded = dict(LEAK_EXCLUDED)
    H, R = c['HEALTH'], c['RISK']
    rr = d[R].astype(str).str.lower().map({'low': 0, 'medium': 1, 'high': 2})
    auc_h = single_auc(d[H], y)
    auc_r = single_auc(rr, y) if rr.notna().sum() > 10 else 0.5
    det = _is_bucket(d[H], d[R])
    info = {'auc_health_score': auc_h, 'auc_churn_risk': auc_r, 'churn_risk_is_bucket_of_health': bool(det)}
    if auc_h > 0.90 or auc_r > 0.90 or det:
        excluded[H] = 'likely derived from outcome'
        excluded[R] = 'likely derived from outcome'
        print('Health_Score / Churn_Risk EXCLUDED: likely derived from outcome (AUC health=%.3f, risk=%.3f, bucket=%s)' % (auc_h, auc_r, det))
    else:
        num = num + [H]
        excluded[R] = 'categorized duplicate of Health_Score (baseline comparison only)'
        print('Health_Score kept (single-feature AUC=%.3f), Churn_Risk dropped (AUC=%.3f).' % (auc_h, auc_r))
    aucs = {}
    keep = []
    for col in num:
        s = pd.to_numeric(d[col], errors='coerce')
        if s.notna().sum() == 0 or s.nunique() < 2:
            excluded[col] = 'constant / empty'
            continue
        a = single_auc(s, y)
        aucs[col] = a
        if a > 0.95:
            excluded[col] = 'single-feature AUC=%.3f > 0.95 (LEAKAGE)' % a
            print('LEAKAGE STOP-LEVEL: %s has single-feature AUC %.3f -> excluded and reported.' % (col, a))
        else:
            keep.append(col)
    cat = [x for x in cat if x in d.columns and d[x].notna().any() and d[x].nunique() > 1]
    info['top_single_feature_auc'] = dict(sorted(aucs.items(), key=lambda kv: -kv[1])[:10])
    if len(keep) + len(cat) < 5:
        raise RuntimeError('Fewer than 5 usable features after leakage exclusions: %s' % excluded)
    print('Snapshot warning: usage/login/tickets/NPS/payment may be measured at churn time for churned accounts; '
          'kept as actionable signals, sensitivity run reported below.')
    return keep, cat, excluded, info


def make_X(d, num, cat):
    X = d[list(num) + list(cat)].copy()
    X[list(num)] = X[list(num)].apply(pd.to_numeric, errors='coerce')
    for k in cat:
        X[k] = X[k].astype(object).where(X[k].notna(), np.nan)
    return X


def gate(X, y, min_rows=150):
    assert len(X) >= min_rows, 'Training rows %d < %d: stop (class/row gate)' % (len(X), min_rows)
    assert min(int(np.sum(y)), int(len(y) - np.sum(y))) >= 10, 'Fewer than 10 rows in a class: stop (class gate)'


def model_zoo(cfg, n_rows):
    rs = cfg['RANDOM_STATE']
    zoo = {'logreg': LogisticRegression(class_weight='balanced', C=0.3, max_iter=3000, random_state=rs),
           'random_forest': RandomForestClassifier(n_estimators=400, min_samples_leaf=5, class_weight='balanced_subsample',
                                                   random_state=rs, n_jobs=1)}
    zoo['hist_gb' if n_rows > 5000 else 'grad_boost'] = (HistGradientBoostingClassifier(random_state=rs) if n_rows > 5000
                                                         else GradientBoostingClassifier(random_state=rs))
    return zoo


def param_space(name):
    if name == 'logreg':
        return {'clf__C': loguniform(1e-2, 1e1)}
    if name == 'random_forest':
        return {'clf__max_depth': [3, 4, 5, 6, 8, None], 'clf__min_samples_leaf': [3, 5, 8, 12],
                'clf__max_features': ['sqrt', 0.3, 0.5]}
    if name == 'grad_boost':
        return {'clf__n_estimators': [100, 200, 300], 'clf__learning_rate': [0.02, 0.05, 0.1],
                'clf__max_depth': [2, 3, 4], 'clf__subsample': [0.7, 0.85, 1.0], 'clf__min_samples_leaf': [3, 5, 10]}
    return {'clf__learning_rate': [0.03, 0.06, 0.1], 'clf__max_depth': [None, 3, 5], 'clf__max_leaf_nodes': [8, 15, 31],
            'clf__min_samples_leaf': [10, 20, 40], 'clf__l2_regularization': [0.0, 0.5, 1.0]}


def topk(y, p, frac=0.2):
    k = max(1, int(np.ceil(len(y) * frac)))
    idx = np.argsort(-p)[:k]
    tp = float(np.sum(y[idx]))
    return tp / max(float(np.sum(y)), 1.0), tp / k


def metrics(y, p, p_train_rate):
    rec, prec = topk(y, p)
    return {'pr_auc': float(average_precision_score(y, p)), 'roc_auc': float(roc_auc_score(y, p)),
            'recall_at_top20': rec, 'precision_at_top20': prec, 'brier': float(brier_score_loss(y, p)),
            'brier_base_rate': float(np.mean((p_train_rate - y) ** 2)), 'base_rate_test': float(np.mean(y))}


def band(p, cfg):
    e = cfg['BAND_EDGES']
    p = np.asarray(p, dtype=float)
    return np.where(p >= e['high'], 'High', np.where(p >= e['medium'], 'Medium', 'Low'))


def run_classification(df, cfg, ml_ok=True, verbose=True):
    c = cfg
    rs = c['RANDOM_STATE']
    d = df[df['is_churned'].notna()].reset_index(drop=True)
    y = d['is_churned'].astype(int).values
    base_rate = float(y.mean())
    nflag = d[RULE_COLS].sum(axis=1)
    rule_hit = (nflag > 0).astype(int).values
    rb = {'precision': float(precision_score(y, rule_hit, zero_division=0)),
          'recall': float(recall_score(y, rule_hit, zero_division=0)), 'flagged_share': float(rule_hit.mean())}
    print('Baseline A (rule: inactive OR low usage OR detractor OR late payer): precision=%.3f recall=%.3f' % (rb['precision'], rb['recall']))
    print('Baseline B (base rate / DummyClassifier prior): PR-AUC=%.3f ROC-AUC=0.500' % base_rate)
    tab = pd.DataFrame({'n': nflag, 'y': y}).groupby('n')['y'].agg(['sum', 'count'])
    rate_map = ((tab['sum'] + 2 * base_rate) / (tab['count'] + 2)).to_dict()
    rule_prob_all = df[RULE_COLS].sum(axis=1).map(rate_map).fillna(base_rate)
    res = {'ml_ok': bool(ml_ok), 'primary': 'rule', 'base_rate': base_rate, 'rule_baseline': rb,
           'rule_prob': pd.Series(rule_prob_all.values, index=df[c['ID']].values),
           'oof_prob': None, 'drivers': None, 'metrics': {}, 'cv': {}, 'excluded': {}, 'churn_threshold': 0.5,
           'acceptance': {}, 'model_name': None}
    if not ml_ok:
        print('FALLBACK: ML gate failed; rule-based risk is primary.')
        return res
    num, cat, excluded, info = select_features(d, y, c)
    X = make_X(d, num, cat)
    idx_tr, idx_te = train_test_split(np.arange(len(d)), test_size=c['TEST_SIZE'], stratify=y, random_state=rs)
    X_tr, X_te, y_tr, y_te = X.iloc[idx_tr], X.iloc[idx_te], y[idx_tr], y[idx_te]
    gate(X_tr, y_tr)
    skf = StratifiedKFold(5, shuffle=True, random_state=rs)
    ys = np.random.RandomState(rs).permutation(y_tr)
    probe = Pipeline([('pre', make_pre(num, cat)), ('clf', LogisticRegression(class_weight='balanced', C=0.3, max_iter=3000))])
    shuf_auc = float(cross_val_score(probe, X_tr, ys, cv=skf, scoring='roc_auc').mean())
    print('Leakage test (shuffled target) CV ROC-AUC = %.3f (expected ~0.5)%s' % (shuf_auc, '' if abs(shuf_auc - 0.5) < 0.1 else '  <-- WARNING'))
    rcv = RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=rs)
    scoring = {'ap': 'average_precision', 'auc': 'roc_auc'}
    zoo = model_zoo(c, len(X_tr))
    zoo_all = dict(zoo)
    zoo_all['dummy_prior'] = DummyClassifier(strategy='prior')
    cv = {}
    for name, clf in zoo_all.items():
        gate(X_tr, y_tr)
        r = cross_validate(Pipeline([('pre', make_pre(num, cat)), ('clf', clone(clf))]), X_tr, y_tr, cv=rcv, scoring=scoring, n_jobs=-1)
        cv[name] = {'ap_mean': float(r['test_ap'].mean()), 'ap_std': float(r['test_ap'].std()),
                    'auc_mean': float(r['test_auc'].mean()), 'auc_std': float(r['test_auc'].std())}
        print('CV 5x2  %-14s PR-AUC %.3f +/- %.3f | ROC-AUC %.3f +/- %.3f' % (name, cv[name]['ap_mean'], cv[name]['ap_std'], cv[name]['auc_mean'], cv[name]['auc_std']))
    best = max(zoo.keys(), key=lambda k: cv[k]['ap_mean'])
    base_pipe = Pipeline([('pre', make_pre(num, cat)), ('clf', clone(zoo[best]))])
    gate(X_tr, y_tr)
    search = RandomizedSearchCV(base_pipe, param_space(best), n_iter=15, scoring='average_precision', cv=skf,
                                random_state=rs, n_jobs=-1, refit=True)
    search.fit(X_tr, y_tr)
    tuned_cv = cross_validate(clone(search.best_estimator_), X_tr, y_tr, cv=rcv, scoring=scoring, n_jobs=-1)
    use_tuned = float(tuned_cv['test_ap'].mean()) >= cv[best]['ap_mean']
    final_est = clone(search.best_estimator_) if use_tuned else clone(base_pipe)
    print('Best family: %s | tuned CV PR-AUC %.3f vs default %.3f -> using %s | params: %s' % (
        best, tuned_cv['test_ap'].mean(), cv[best]['ap_mean'], 'tuned' if use_tuned else 'default', search.best_params_ if use_tuned else {}))
    cal_method = 'isotonic' if len(X_tr) >= 1000 else 'sigmoid'
    gate(X_tr, y_tr)
    cal = CalibratedClassifierCV(clone(final_est), method=cal_method, cv=5)
    cal.fit(X_tr, y_tr)
    p_te = cal.predict_proba(X_te)[:, 1]
    mt = metrics(y_te, p_te, float(y_tr.mean()))
    lg = np.log(np.clip(p_te, 1e-4, 1 - 1e-4) / (1 - np.clip(p_te, 1e-4, 1 - 1e-4)))
    slope = float(LogisticRegression(C=1e6, max_iter=1000).fit(lg.reshape(-1, 1), y_te).coef_[0][0])
    mt['calibration_slope'] = slope
    mt['calibration_method'] = cal_method
    print('HOLD-OUT (n=%d): PR-AUC %.3f (base %.3f) | ROC-AUC %.3f | recall@top20%% %.3f | precision@top20%% %.3f | Brier %.4f (base-rate %.4f) | cal.slope %.2f' % (
        len(y_te), mt['pr_auc'], mt['base_rate_test'], mt['roc_auc'], mt['recall_at_top20'], mt['precision_at_top20'], mt['brier'], mt['brier_base_rate'], slope))
    # OOF calibrated probabilities for EVERY labeled row (so active accounts are scored by models that never saw them)
    oof = cross_val_predict(CalibratedClassifierCV(clone(final_est), method=cal_method, cv=3), X, y,
                            cv=StratifiedKFold(5, shuffle=True, random_state=rs + 1), method='predict_proba')[:, 1]
    # threshold: F2-optimal on training-row OOF probabilities
    pr, rc, th = precision_recall_curve(y[idx_tr], oof[idx_tr])
    f2 = 5 * pr[:-1] * rc[:-1] / np.maximum(4 * pr[:-1] + rc[:-1], 1e-12)
    thr = float(th[int(np.argmax(f2))]) if len(th) else 0.5
    avg_loss = float(d.loc[d['is_churned'] == 1, 'mrr_lost'].mean() * 12)
    ratio = avg_loss / max(c['CSM_HOUR_COST'], 1e-9)
    print('Threshold (F2-optimal) = %.3f. Business-cost note: one missed churner ~ $%.0f ARR vs ~$%.0f per false alarm (%.0f:1), so recall is favored.' % (thr, avg_loss, c['CSM_HOUR_COST'], ratio))
    pred = (p_te >= thr).astype(int)
    cm = confusion_matrix(y_te, pred, labels=[0, 1])
    # sensitivity: static account attributes only (no usage / login / tickets / NPS / payment signals)
    static_num = [x for x in [c['SEATS'], c['LIST_PRICE'], c['DISCOUNT'], c['MRR0'], c['CAC'], c['GM'], c['PAYBACK'],
                              'mrr_per_seat', 'margin_per_seat', 'annual_flag', 'payback_ok'] if x in num]
    static_cat = [x for x in [c['PLAN'], c['CYCLE'], c['INDUSTRY'], c['REGION'], c['SIZE'], c['CHANNEL'],
                              'discount_depth_band', 'plan_x_cycle', 'size_x_channel'] if x in cat]
    sens = {}
    if len(static_num) + len(static_cat) >= 3:
        sp = Pipeline([('pre', make_pre(static_num, static_cat)), ('clf', clone(zoo[best]))])
        sp.fit(X_tr[static_num + static_cat], y_tr)
        ps = sp.predict_proba(X_te[static_num + static_cat])[:, 1]
        sens = {'roc_auc': float(roc_auc_score(y_te, ps)), 'pr_auc': float(average_precision_score(y_te, ps))}
        print('SENSITIVITY (static attributes only, no snapshot signals): ROC-AUC %.3f vs %.3f with behavioural signals -> %.0f%% of the lift above chance comes from snapshot/behavioural signals.' % (
            sens['roc_auc'], mt['roc_auc'], 100 * min(1.0, max(0.0, (mt['roc_auc'] - sens['roc_auc']) / max(mt['roc_auc'] - 0.5, 1e-9)))))
    # explainability
    pi = permutation_importance(cal, X_te, y_te, scoring='average_precision', n_repeats=10, random_state=rs, n_jobs=1)
    imp = pd.Series(pi.importances_mean, index=X_te.columns).sort_values(ascending=False).head(15)
    fig, axs = plt.subplots(2, 3, figsize=(18, 9))
    ax = axs[0, 0]
    im = ax.imshow(cm, cmap='Blues')
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, int(v), ha='center', va='center', fontsize=13)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['Pred active', 'Pred churn'])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Active', 'Churned'])
    ax.set_title('Confusion matrix @ threshold %.2f' % thr)
    p_, r_, _ = precision_recall_curve(y_te, p_te)
    axs[0, 1].plot(r_, p_)
    axs[0, 1].axhline(mt['base_rate_test'], color='grey', ls='--', label='base rate')
    axs[0, 1].set_title('Precision-Recall (AP=%.3f)' % mt['pr_auc'])
    axs[0, 1].legend()
    fpr, tpr, _ = roc_curve(y_te, p_te)
    axs[0, 2].plot(fpr, tpr)
    axs[0, 2].plot([0, 1], [0, 1], color='grey', ls='--')
    axs[0, 2].set_title('ROC (AUC=%.3f)' % mt['roc_auc'])
    fp_, mp_ = calibration_curve(y_te, p_te, n_bins=6, strategy='quantile')
    axs[1, 0].plot(mp_, fp_, marker='o')
    axs[1, 0].plot([0, 1], [0, 1], color='grey', ls='--')
    axs[1, 0].set_title('Reliability (%s, slope %.2f)' % (cal_method, slope))
    axs[1, 1].barh([pretty(i) for i in imp.index][::-1], imp.values[::-1], color='#2b6cb0')
    axs[1, 1].set_title('Permutation importance (top 15, PR-AUC drop)')
    axs[1, 2].hist(p_te[y_te == 0], bins=15, alpha=0.5, label='Active')
    axs[1, 2].hist(p_te[y_te == 1], bins=15, alpha=0.5, label='Churned')
    axs[1, 2].legend()
    axs[1, 2].set_title('Calibrated probability on hold-out')
    savefig(fig, 'reports/05_churn_model_diagnostics.png')
    # per-account drivers (logistic contributions on standardized features)
    lr_all = Pipeline([('pre', make_pre(num, cat)), ('clf', LogisticRegression(class_weight='balanced', C=0.3, max_iter=3000))]).fit(X, y)
    am = (d['is_churned'] == 0).values
    Z = lr_all.named_steps['pre'].transform(X[am])
    coef = lr_all.named_steps['clf'].coef_[0]
    names = lr_all.named_steps['pre'].get_feature_names_out()
    contrib = Z * coef
    Xa = X[am].reset_index(drop=True)
    drivers = []
    for i in range(contrib.shape[0]):
        parts = []
        for j in np.argsort(-contrib[i])[:3]:
            if contrib[i][j] <= 0:
                continue
            raw = str(names[j]).replace('num__', '', 1)
            lab = pretty(names[j])
            if raw in Xa.columns and pd.notna(Xa.loc[i, raw]):
                lab = '%s=%s' % (lab, round(float(Xa.loc[i, raw]), 2))
            parts.append('%s (+%.2f)' % (lab, contrib[i][j]))
        drivers.append('; '.join(parts) if parts else 'no strong risk driver')
    res['drivers'] = pd.Series(drivers, index=d.loc[am, c['ID']].values)
    # acceptance
    acc = {'pr_auc_ge_2x_base': bool(mt['pr_auc'] >= 2 * mt['base_rate_test']), 'roc_auc_ge_0_80': bool(mt['roc_auc'] >= 0.80),
           'brier_below_base': bool(mt['brier'] < mt['brier_base_rate']), 'recall_top20_ge_50pct': bool(mt['recall_at_top20'] >= 0.5),
           'calibration_slope_0_8_1_2': bool(0.8 <= slope <= 1.2)}
    core_ok = acc['pr_auc_ge_2x_base'] and acc['roc_auc_ge_0_80'] and acc['brier_below_base']
    print('Acceptance:', acc)
    if not core_ok:
        print('SIGNAL INSUFFICIENT: acceptance targets not met -> rule-based scoring stays primary; model probabilities are shown for reference only.')
    # persist
    os.makedirs(c['MODELS_DIR'], exist_ok=True)
    joblib.dump(cal, os.path.join(c['MODELS_DIR'], 'best_classifier.pkl'))
    types = {k: 'numeric' for k in num}
    types.update({k: 'categorical' for k in cat})
    ranges = {k: {'min': float(X[k].min()), 'max': float(X[k].max())} for k in num}
    ranges.update({k: {'values': sorted(X[k].dropna().astype(str).unique().tolist())[:50]} for k in cat})
    joblib.dump({'num': num, 'cat': cat, 'all': num + cat, 'types': types, 'ranges': ranges},
                os.path.join(c['MODELS_DIR'], 'feature_cols.pkl'))
    card = {'model_family': best, 'tuned': bool(use_tuned), 'calibration': cal_method, 'metrics_holdout': mt, 'cv_5x2': cv,
            'shuffled_target_auc': shuf_auc, 'single_feature_checks': info, 'excluded_features': excluded,
            'sensitivity_static_only': sens, 'acceptance': acc, 'primary_scoring': 'model' if core_ok else 'rule',
            'churn_threshold': thr, 'threshold_rule': 'F2-optimal on out-of-fold training probabilities',
            'horizon': '90 days (assumption; data is a snapshot so scores rank relative risk)',
            'n_train': int(len(y_tr)), 'n_test': int(len(y_te)), 'features_num': num, 'features_cat': cat,
            'rule_baseline': rb, 'base_rate': base_rate}
    save_json(os.path.join(c['REPORTS_DIR'], 'model_card.json'), card)
    save_json('config/model_config.json', {'churn_threshold': thr, 'band_edges': c['BAND_EDGES']})
    pr_pts = list(zip(r_[::max(1, len(r_) // 25)], p_[::max(1, len(p_) // 25)]))
    add_charts({'pr_curve': {'type': 'line', 'title': 'Precision vs recall', 'data': xy_list([round(a, 3) for a, _ in pr_pts], [b for _, b in pr_pts])},
                'calibration_curve': {'type': 'line', 'title': 'Observed vs predicted churn', 'data': xy_list([round(a, 3) for a in mp_], fp_)},
                'permutation_importance': {'type': 'bar', 'title': 'Top drivers (permutation importance)', 'data': xy_list([pretty(i) for i in imp.index], imp.values)}})
    res.update({'primary': 'model' if core_ok else 'rule', 'oof_prob': pd.Series(oof, index=d[c['ID']].values), 'metrics': mt,
                'cv': cv, 'excluded': excluded, 'churn_threshold': thr, 'acceptance': acc, 'model_name': best, 'sens': sens,
                'card': card, 'importance': imp, 'confusion': cm})
    return res


def attach_scores(df, res, cfg):
    c = cfg
    out = df.copy()
    ids = out[c['ID']]
    out['rule_prob'] = ids.map(res['rule_prob'])
    out['model_prob'] = ids.map(res['oof_prob']) if res['oof_prob'] is not None else np.nan
    out['churn_prob'] = out['model_prob'] if (res['primary'] == 'model') else out['rule_prob']
    out['churn_prob'] = out['churn_prob'].fillna(out['rule_prob'])
    out['churn_band'] = band(out['churn_prob'], c)
    out['drivers'] = ids.map(res['drivers']) if res['drivers'] is not None else np.nan
    active = out[c['STATUS']] == c['ACTIVE_VALUE']
    out['arr_at_risk'] = np.where(active, out[c['ARR']].fillna(out[c['MRR']] * 12) * out['churn_prob'], 0.0)
    out['scoring_source'] = res['primary']
    cols = [c['ID'], c['COMPANY'], 'churn_prob', 'churn_band', 'arr_at_risk', 'rule_prob', 'model_prob', 'drivers', c['ARR']]
    out.loc[active, cols].sort_values('arr_at_risk', ascending=False).to_csv('data/processed/ml_task1_output.csv', index=False, encoding='utf-8')
    return out
