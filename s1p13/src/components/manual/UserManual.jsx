import { useMemo, useState } from 'react';
import { ManualSection } from './ManualSection';
import { GlossaryTable } from './GlossaryTable';
import { useTerm, useTerms } from '../shared/TerminologyProvider';
import { MODEL, PROJECT } from '../../utils/contract';
import { titleCase } from '../../utils/formatters';

function buildSections(t) {
  const cust = t('customer').toLowerCase();
  const custs = t('customer', { plural: true }).toLowerCase();
  const rev = t('revenue');
  const plan = t('product').toLowerCase();
  return [
    { id: 'how', title: 'How to use this dashboard', blocks: [
      { h: 'Three sections, three questions', p: [
        'UNDERSTAND shows what is happening in your business right now.',
        'DECIDE tells you what to do about it, in plain English, with the numbers behind each suggestion.',
        'MONITOR tells you whether you are on track and warns you when something needs attention.'] },
      { h: 'Where the numbers come from', p: [`Everything is calculated from your ${cust} records each time the analysis is run. The "Last updated" time at the top shows when that was.`, 'The light/dark button at the top switches the colour theme. Your choice is remembered.'] }] },
    { id: 'understand', title: 'UNDERSTAND', blocks: [
      { h: 'Your numbers', p: [`What you see: your ${rev} totals, how many ${custs} you have, how many have left, and how well you keep revenue.`, 'What it means: "Active ARR" is the yearly value of everything currently being billed. "ARR at risk" is the part of it we expect to lose, based on each account\'s churn risk.', 'What to do: if ARR at risk looks large, go straight to the Save list.'] },
      { h: 'Analysis charts', p: ['Bar chart: each bar is a group (for example a plan). Taller means more. Hover to see the exact number.', 'Line chart: shows change over time. Going down means shrinking, going up means growing.', 'Heat grid: darker red squares mean two things move together.', 'Look for the groups that stand out: the plan that loses the most customers, the channel that costs too much to win a customer.'] },
      { h: `${t('customer')} segments`, p: [`${custs[0].toUpperCase() + custs.slice(1)} are grouped by how similar they are. Each group shows its size, share of revenue, average churn risk and three traits that describe it.`, 'Click a group to see its highest-risk accounts.'] },
      { h: 'Unusual accounts', p: ['These accounts behave differently from the rest, for example unusually high unpaid balances or very low usage. They are not necessarily bad, but they deserve a look.'] }] },
    { id: 'decide', title: 'DECIDE', blocks: [
      { h: 'Insights', p: ['HIGH: needs attention this week. MEDIUM: review this month. LOW: good to know.', 'Each insight gives the finding, the evidence from your data, and what to do.'] },
      { h: 'Save list', p: [`This is your call list. Each ${cust} has a priority: P1 urgent, P2 important, P3 watch, P4 fine.`, 'Each row tells you what to do, the churn risk, and the revenue at risk. Click a row to see why the account is flagged.', 'Use "Copy list" to paste it into a spreadsheet or email.'] },
      { h: 'What-if simulator', p: ['Use this to explore "what would happen if I changed X?". Move the slider or choose an option and the projected result updates immediately.', 'The assumptions box lists what the projection relies on. Treat results as estimates, not promises.'] },
      { h: 'Goals & targets', p: ['Type your own targets. They are saved in this browser. Goal progress compares them with today\'s results.'] }] },
    { id: 'monitor', title: 'MONITOR', blocks: [
      { h: 'Forecast', p: [`Our prediction of how much ${rev} today\'s active ${custs} will still bring in over the next months if nothing changes.`, 'The shaded band is the likely range. "Forecast reliability" says whether our test on past months was accurate enough ("backtested") or only a rough guide ("indicative").', 'The "Ask the forecast" box returns the expected figure for a number of months ahead.'] },
      { h: 'Goal progress', p: ['Bars show where you are against each target. Green means on target, red means off target.', 'Retention figures are snapshot estimates over the period covered by your data, not full-year figures.'] },
      { h: 'Alert center', p: ['Alerts are things that need attention now, such as urgent accounts, inactive accounts, unpaid invoices or a sharp drop in expected revenue.'] }] },
    { id: 'explorer', title: 'Interactive explorer', blocks: [
      { h: 'How it works', p: ['Pick what to group by and what to measure. Click any bar and every other chart and the table filter to match; click it again to undo.', 'A side panel shows the details of whatever you clicked. "Copy summary" puts the current numbers on your clipboard.'] }] },
    { id: 'score', title: 'How the churn risk is worked out', blocks: [
      { h: 'In plain words', p: [`Each active ${cust} gets a percentage: our estimate of how likely it is to leave in roughly the next ${MODEL.horizon || '90 days'}.`, 'It looks at things like how recently people log in, product usage, support tickets, satisfaction scores and payment behaviour, plus plan and size.', 'It ranks accounts by relative risk. It is guidance for who to call first, not a guarantee.', `Signals used: ${(MODEL.input_fields || []).slice(0, 14).map((f) => titleCase(f.name)).join(', ') || 'see your analyst'}.`] }] }
  ];
}

function buildGlossary(t, terms) {
  const rows = Object.entries(terms).map(([k, v]) => [v, `Your word for "${k}" throughout this dashboard.`]);
  return [
    ...rows,
    ['Churn', `When a ${t('customer').toLowerCase()} stops paying and leaves.`],
    ['Churn risk', 'Our estimate of how likely an account is to leave soon, shown as a percentage.'],
    ['MRR', 'Monthly recurring revenue: what you bill every month from active accounts.'],
    ['ARR', 'Annual recurring revenue: MRR multiplied by 12.'],
    ['ARR at risk', 'Revenue we expect to lose: each account\'s yearly value multiplied by its churn risk.'],
    ['GRR (gross revenue retention)', 'The share of starting revenue you kept after cancellations and downgrades, ignoring upsells.'],
    ['NRR (net revenue retention)', 'Like GRR but also counts extra revenue from upgrades and added seats. Above 100% means existing accounts grow.'],
    ['LTV : CAC', 'Profit a customer brings over their life compared with what it cost to win them. 3x or more is considered healthy.'],
    ['Payback', 'How many months of profit it takes to earn back the cost of winning a customer. 12 months or less is a common target.'],
    ['Segment', 'A group of accounts that look alike (for example "Champions" or "At-Risk").'],
    ['Anomaly', 'An account whose pattern does not match your normal business behaviour.'],
    ['Forecast', `Our prediction of your future ${t('revenue')} based on how similar accounts behaved in the past.`],
    ['Backtested / indicative', 'Backtested means we tested the forecast on recent months and it was close. Indicative means treat it as a rough guide.'],
    ['P1 - P4', 'Priority levels: P1 act this week, P2 act soon, P3 keep an eye on it, P4 no action.'],
    ['Line chart', 'A chart that shows how something changes over time.'],
    ['Bar chart', 'A chart where bar length shows size, used to compare groups.'],
    ['Heat grid', 'A grid where colour strength shows how strongly two things move together.']
  ];
}

export function UserManual() {
  const t = useTerm();
  const terms = useTerms();
  const [q, setQ] = useState('');
  const sections = useMemo(() => buildSections(t), [t]);
  const glossary = useMemo(() => buildGlossary(t, terms), [t, terms]);
  const ql = q.trim().toLowerCase();
  const shown = ql ? sections.filter((s) => (s.title + s.blocks.map((b) => b.h + b.p.join(' ')).join(' ')).toLowerCase().includes(ql)) : sections;
  const gl = ql ? glossary.filter(([a, b]) => (a + b).toLowerCase().includes(ql)) : glossary;
  return (
    <div className="manual">
      <div className="row no-print">
        <input placeholder="Search the manual" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 260 }} />
        <button className="btn ghost" onClick={() => window.print()}>Print manual</button>
      </div>
      <h1 style={{ marginTop: 16 }}>{PROJECT.name}: your analytics guide</h1>
      {shown.map((s) => <ManualSection key={s.id} section={s} q={ql} />)}
      {shown.length === 0 && <p className="muted">No sections match your search.</p>}
      <h2>Glossary</h2>
      <GlossaryTable rows={gl} q={ql} />
    </div>
  );
}
