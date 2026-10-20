import os
import sys
import matplotlib
matplotlib.use('Agg')
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import pandas as pd
from utils import *
from config import CONFIG
import data_loader, features, classify, segmentation, forecast, business_logic, simulate, reporting
import export_for_frontend


def run():
    cfg = CONFIG
    ensure_dirs(cfg)
    save_json('config/pipeline_config.json', cfg)
    raw = data_loader.load_raw(cfg)
    raw, val, as_of = data_loader.validate(raw, cfg)
    clean_df, _ = data_loader.clean(raw, cfg, as_of)
    feat, meta = features.engineer(clean_df, cfg)
    charts, ch_t = features.run_eda(feat, cfg)
    res = classify.run_classification(feat, cfg, ml_ok=val['ml_ok'])
    scored = classify.attach_scores(feat, res, cfg)
    act = scored[scored[cfg['STATUS']] == cfg['ACTIVE_VALUE']]
    seg = segmentation.run_segmentation(act, cfg)
    fc = forecast.run_forecast(scored, cfg, as_of)
    act2 = act.merge(seg['df'][[cfg['ID'], 'segment', 'is_anomaly', 'anomaly_reason']], on=cfg['ID'], how='left')
    logic = business_logic.run_logic(act2, ch_t, cfg, usage_scale=meta['usage_scale'])
    master = business_logic.assemble_master(feat, scored, seg['df'], logic['act'], fc['accounts'], cfg)
    simulate.run_simulations(master, logic['channel_recs'], cfg)
    goals = business_logic.run_goals_alerts(master, fc, cfg)
    card = load_json(os.path.join(cfg['REPORTS_DIR'], 'model_card.json'))
    business_logic.build_insights(master, cfg, card, fc['meta'], logic['channel_recs'])
    ctx = {'logic': logic, 'seg': seg, 'fc': fc, 'goals': goals, 'model_card': card}
    summary = reporting.final_summary(master, ctx, cfg)
    reporting.build_excel(master, ctx, cfg, summary)
    reporting.build_dashboard(master, ctx, cfg)
    export_for_frontend.main()
    reporting.build_report_deck(master, ctx, cfg, summary)
    reporting.write_readme(summary, cfg)


if __name__ == '__main__':
    run()
