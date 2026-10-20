export const NAV = [
  {
    id: 'understand', title: 'UNDERSTAND', blurb: 'What is happening',
    items: [
      { id: 'overview', label: () => 'Your numbers', title: (t) => `Your ${t('revenue')} at a glance`, desc: (t) => `Headline ${t('revenue')} and ${t('customer')} figures from the latest pipeline run.` },
      { id: 'charts', label: () => 'Analysis charts', title: () => 'Analysis charts', desc: () => 'Why customers leave, which plans and channels perform, and how retention is trending.' },
      { id: 'segments', label: (t) => `${t('customer')} segments`, title: (t) => `${t('customer')} segments`, desc: (t) => `Groups of similar ${t('customer', { plural: true }).toLowerCase()} with plain-English traits.` },
      { id: 'anomalies', label: () => 'Unusual accounts', title: () => 'Unusual accounts', desc: () => 'Accounts whose payment, usage or revenue pattern stands out from the rest.' }
    ]
  },
  {
    id: 'decide', title: 'DECIDE', blurb: 'What to do about it',
    items: [
      { id: 'insights', label: () => 'Insights', title: () => 'Insights', desc: () => 'Findings ranked by severity, each with the evidence and a next step.' },
      { id: 'recommendations', label: () => 'Save list', title: (t) => `This week's save list`, desc: (t) => `Which ${t('customer', { plural: true }).toLowerCase()} to contact first and what to do for each.` },
      { id: 'simulator', label: () => 'What-if simulator', title: () => 'What-if simulator', desc: () => 'Try a price, discount, campaign or budget change and see the projected effect.' },
      { id: 'goals', label: () => 'Goals & targets', title: () => 'Goals & targets', desc: () => 'Set your own targets and compare them with where you are today.' }
    ]
  },
  {
    id: 'monitor', title: 'MONITOR', blurb: 'Are we on track',
    items: [
      { id: 'forecast', label: () => 'Forecast', title: (t) => `${t('revenue').split('/')[0].trim()} forecast`, desc: () => 'Expected recurring revenue over the coming months if nothing changes.' },
      { id: 'progress', label: () => 'Goal progress', title: () => 'Goal progress', desc: () => 'Retention and risk against your targets.' },
      { id: 'alerts', label: () => 'Alert center', title: () => 'Alert center', desc: () => 'Things that need attention right now.' }
    ]
  },
  {
    id: 'explore', title: 'EXPLORE', blurb: 'Dig deeper, learn the tool',
    items: [
      { id: 'explorer', label: () => 'Interactive explorer', title: () => 'Interactive explorer', desc: () => 'Click any bar to filter everything else. Pick what to group by and what to measure.' },
      { id: 'manual', label: () => 'User manual', title: () => 'User manual', desc: () => 'A plain-English guide to every screen.' }
    ]
  }
];

export const VIEW_INDEX = Object.fromEntries(
  NAV.flatMap((s) => s.items.map((it) => [it.id, { ...it, section: s.title }]))
);
