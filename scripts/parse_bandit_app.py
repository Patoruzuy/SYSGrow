import json

with open('bandit_app_only.json','r',encoding='utf-8') as f:
    j = json.load(f)

results = j.get('results', [])
# Filter app/ files
app_results = [r for r in results if r.get('filename','').startswith('app\\') or r.get('filename','').startswith('app/')]
# Sort by severity (HIGH, MEDIUM, LOW)
sev_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2, 'UNDEFINED': 3}
app_results.sort(key=lambda r: (sev_order.get(r.get('severity','UNDEFINED'), 3), -r.get('line_number',0)))

for r in app_results:
    print('FILE:', r.get('filename'))
    print('LINE:', r.get('line_number'))
    print('TEST:', r.get('test_name'))
    print('SEVERITY:', r.get('severity'), 'CONF:', r.get('confidence'))
    print('MSG:', r.get('issue_text'))
    print('-'*60)

print('TOTAL_APP_ISSUES:', len(app_results))
