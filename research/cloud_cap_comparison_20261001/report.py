"""Package completed cap results without selecting or modifying a model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SELECTORS={
    'volr20_low':'Silence（出来高比率最小）',
    'body_pct_low':'Dive（実体最小）',
    'mean_rank_volr20_body_pct':'Shadow（平均順位）',
    'dual_top1_agreement':'Fusion（両最小一致）',
    'dual_top1_agreement_g3_no_acute_selloff':'Balance（両最小一致・市場急落除外）',
    'all_conditions_unique':'全条件・同日同銘柄を重複除外',
    'all_conditions_stacked':'全条件・条件別取引を積上げ',
}


def cap_name(value):return '上限なし' if int(value)==0 else f'{int(value):,}円'
def pct(value):return '—' if pd.isna(value) else f'{value*100:+.2f}%'
def rate(value):return '—' if pd.isna(value) else f'{value*100:.2f}%'
def yen(value):return '—' if pd.isna(value) else f'{value:,.0f}円'


def table(rows,columns):
    text=['| '+' | '.join(name for name,_,_ in columns)+' |',
        '| '+' | '.join('---' for _ in columns)+' |']
    for row in rows.to_dict('records'):
        text.append('| '+' | '.join(formatter(row[key]) for _,key,formatter in columns)+' |')
    return '\n'.join(text)


def report(output:Path,destination:Path):
    summary=json.loads((output/'summary.json').read_text(encoding='utf-8'))
    audit=json.loads((output/'independent_result_audit.json').read_text(encoding='utf-8'))
    prepared_audit=json.loads((output/'independent_prepared_audit.json').read_text(encoding='utf-8'))
    weights=json.loads((output/'actual_monthly_model_weights_metadata.json').read_text(encoding='utf-8'))
    assert summary['status']=='complete' and audit['status']=='passed' and prepared_audit['status']=='passed'
    assert weights['status']=='passed' and weights['completed_receipts_checked']==270
    metadata=summary['metadata']
    metrics=pd.read_csv(output/'metrics.csv',dtype={'period':str})
    baseline=metrics[metrics.cap.eq(1000)].drop(columns=['cap']).rename(columns={c:f'cap1000_{c}' for c in metrics if c not in ['cap','selector','period']})
    paired=metrics.merge(baseline,on=['selector','period'],validate='many_to_one')
    for column in ['n','win_rate','mean','median','worst','loss10_count','loss10_rate','mean_excluding_top3','one_hundred_share_total_pl_yen','required_capital_yen','capital_return']:
        paired[f'delta_vs_cap1000_{column}']=paired[column]-paired[f'cap1000_{column}']
    destination.mkdir(parents=True,exist_ok=True)
    paired.to_csv(destination/'paired_metrics.csv',index=False,float_format='%.12g')
    for name in ['metrics.csv','prepared.json','summary.json','independent_prepared_audit.json','independent_result_audit.json','independent_monthly_receipt_audit.json','restriction_snapshot.json','actual_monthly_model_weights.csv','actual_monthly_model_weights_metadata.json']:
        shutil.copyfile(output/name,destination/name)
    headline=[('上限','cap',cap_name),('確定件数','n',lambda x:str(int(x))),('勝率','win_rate',rate),('平均','mean',pct),('中央値','median',pct),('最悪','worst',pct),('−10%以下','loss10_count',lambda x:str(int(x))),('最大3勝ち除外平均','mean_excluding_top3',pct)]
    unique=metrics[metrics.selector.eq('all_conditions_unique') & metrics.period.eq('ALL')]
    stacked=metrics[metrics.selector.eq('all_conditions_stacked') & metrics.period.eq('ALL')]
    no_cap=paired[paired.cap.eq(0) & paired.selector.eq('all_conditions_unique') & paired.period.eq('ALL')].iloc[0]
    lines=['# Cloud価格上限比較（分割・併合対策と市場欠損分母を修正したV2）','',
        f"全6群×45か月の270 fitを完了。重複除外集計で、上限を1,000円から撤廃すると平均騰落率の差は {no_cap['delta_vs_cap1000_mean']*100:+.2f}ポイント、勝率の差は {no_cap['delta_vs_cap1000_win_rate']*100:+.2f}ポイントでした。首位同順位の日を全群から共通除外した診断比較で、既存公開ledgerの実績値とは別です。将来の収益性を認証する結果ではありません。",'',
        '## 同日・同銘柄を一取引とする比較','',table(unique,headline),'',
        '## 条件ごとに100株ずつ購入する積上げ比較','',table(stacked,headline),'',
        '## 必要元金と実100株損益（重複除外）','',
        table(unique,[('上限','cap',cap_name),('全期間損益','one_hundred_share_total_pl_yen',yen),('同時保有元金最大値','required_capital_yen',yen),('損益÷元金','capital_return',pct)]),'',
        '元金は、同日始値の購入が終値の売却より先に発生する契約で、同時保有中の購入元金を足した最大値です。損失による現金減少、信用取引の拘束金、税金を含む資金計画ではありません。損益÷元金は全研究期間の比率で、年率ではありません。','',
        '## 年別（重複除外）','']
    for year in ('2023','2024','2025','2026'):
        lines += [f'### {year}'+('（9月30日価格評価まで）' if year=='2026' else ''),'',
            table(metrics[metrics.selector.eq('all_conditions_unique') & metrics.period.eq(year)],headline),'']
    lines += ['## 5条件別・全期間','']
    modes=metrics[(~metrics.selector.str.startswith('all_conditions_')) & metrics.period.eq('ALL')].copy()
    modes['selector_label']=modes.selector.map(lambda x:SELECTORS.get(x,x))
    lines += [table(modes,[('条件','selector_label',str),*headline]),'',
        '## 固定した方法と監査','',
        '- 日足供給元snapshot基準は2026年10月1日。10月1日途中価格を除き、価格評価は9月30日まで。予測期間は2023年1月〜2026年9月の45か月。',
        '- 絶対的な株価・出来高gateは当時の株数単位へ復元した actual_*。前日終値上限だけを6群で変え、各群の訓練母集団と同日上位0.25%教師ラベルも再計算。',
        '- 固定45特徴量、V7 seed42・160 trees・4 threads、月次 target_end_date < 月初、Tail CDF≥0.999、5選定条件を維持。結果から他の条件を調整していない。',
        '- 品質隔離した価格の行・日付を残しOHLCVをNaN化。市場陽線比率と移動平均上方比率の分母は有効な非NaN行だけ。旧V1との全行照合で変更はこの2特徴量だけ。旧104 fitは混ぜていない。',
        '- 翌銀行営業日始値購入、5銀行営業日後終値売却。予定日の価格欠落を後日の価格へ置き換えない。保有中の全分割・併合を順に適用し、途中で端株が生じる取引は現金精算を推測せず計測対象外。',
        '- 読取済みJPX整理銘柄は指定日から因果的に除外。既存の約定困難エントリー除外規則を全群へ共通適用。勝率は0%を含む全確定取引を分母にする。',
        f"- 首位同順位の共通除外日は {summary['common_day_excluded_count']}日。対象日: "+(', '.join(summary['common_day_excluded_calendar']) or 'なし')+'。どの群か一つでも曖昧なら、その日を全6群・全条件から除外し、教師学習は変えない。',
        f"- 独立監査で270個の月次CSV/SHA receipt、全{audit['independent_metric_rows']}成績行、{audit['all_selected_rows_economics_checked_through_identical_identity_inputs']:,}選定行の株数反映損益、別計算の必要元金を照合し一致。重複する経済入力の一致を確認し、{audit['trade_economics_unique_arm_identities_checked']:,}群内同日同銘柄の経済計算を再実行。",'',
        '## 限界','',
        '現在のJPX銘柄一覧から取った生存銘柄を使うため、上場廃止銘柄を含む全歴史母集団ではありません。供給元の過去価格・企業行動情報は現在snapshotから復元したもので、当時公開されていた全情報を完全に再現したデータとは言い切れません。手数料・スプレッド・滑りは0。ストップ高や流動性不足を含む実際の約定は保証しません。現行公開ledgerを研究結果で上書きしていません。','',
        '## 再現証跡','',
        f"- source CSV SHA256: `{metadata['source_sha256']}`",
        f"- action journal SHA256: `{metadata['actions_sha256']}`",
        f"- runner SHA256: `{metadata['source_hashes'][str((HERE/'compare.py').relative_to(ROOT))]}`",
        '- [prepared.json](prepared.json) の model_parameters は教師 [0,1] を渡した共通テンプレートです。scale_pos_weight は実学習のクラス比率で動的に決まり、各cap/月の教師クラス数と実重みを [actual_monthly_model_weights.csv](actual_monthly_model_weights.csv)、[補足metadata](actual_monthly_model_weights_metadata.json) に保存しました。その他params、凍結コード/規則hash、version、入力期間は prepared.json に記載。',
        '- 全指標と差分は [metrics.csv](metrics.csv)、[paired_metrics.csv](paired_metrics.csv)。集計件数・除外理由数とcalendarは [summary.json](summary.json)。',
        '- 旧調整基準だけの比較は [LEGACY_REFERENCE.md](LEGACY_REFERENCE.md) を参照。']
    (destination/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':'packaged','metrics':len(metrics),'output':str(destination)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'.cache/cloud_cap_corrected_v2_20261001')
    parser.add_argument('--destination',type=Path,default=HERE)
    args=parser.parse_args()
    report(args.output,args.destination)
