import os
import re
import sys
import json
import urllib.request
import urllib.error
import subprocess

TOKEN = os.environ.get('GITHUB_TOKEN')
if not TOKEN:
    print('NO_TOKEN')
    sys.exit(1)

try:
    origin = subprocess.check_output(['git', 'remote', 'get-url', 'origin']).decode().strip()
except Exception as e:
    print('ERROR_GET_ORIGIN', e)
    sys.exit(1)

origin_clean = re.sub(r"\.git$", "", origin)
m = re.search(r"github.com[:/](.+?)/(.+)$", origin_clean)
if not m:
    print('PARSE_FAIL', origin_clean)
    sys.exit(1)
owner, repo = m.group(1), m.group(2)

repo_url = f"https://api.github.com/repos/{owner}/{repo}"
headers = {
    'Authorization': f'token {TOKEN}',
    'User-Agent': 'sysgrow-ci',
    'Accept': 'application/vnd.github.v3+json'
}

def get_repo_info():
    req = urllib.request.Request(repo_url, headers=headers, method='GET')
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)

try:
    info = get_repo_info()
    base = info.get('default_branch', 'main')
except urllib.error.HTTPError as e:
    print('ERROR_GET_REPO', e.code)
    try:
        print(e.read().decode())
    except Exception:
        pass
    sys.exit(1)

pr_body = (
    "Automated PR: modernize packaging and harden WSGI entrypoint.\n\n"
    "Changes:\n- Updated setup.py to use pathlib and robust requirement parsing\n"
    "- Hardened smart_agriculture_app.py with safer startup and logging\n"
    "- Regenerated .egg-info metadata\n\nPlease review."
)

payload = {
    'title': 'Modernize setup.py and harden WSGI entrypoint',
    'head': 'update',
    'base': base,
    'body': pr_body,
    'maintainer_can_modify': True,
}

create_url = repo_url + '/pulls'
req = urllib.request.Request(create_url, data=json.dumps(payload).encode('utf-8'), headers={**headers, 'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
        print('PR_CREATED:' + data.get('html_url', ''))
except urllib.error.HTTPError as e:
    # print status and body
    print('ERROR_CREATING_PR', e.code)
    try:
        body = e.read().decode()
        print('DETAILS:' + body)
    except Exception:
        pass
    # Try to find an existing PR from this head
    try:
        list_url = repo_url + f"/pulls?state=open&per_page=100"
        req2 = urllib.request.Request(list_url, headers=headers, method='GET')
        with urllib.request.urlopen(req2) as resp2:
            prs = json.load(resp2)
            for p in prs:
                head = p.get('head', {})
                if head.get('ref') == 'update' or (head.get('label') or '').endswith(':update'):
                    print('EXISTING_PR:' + p.get('html_url', ''))
                    break
    except Exception:
        pass
    sys.exit(1)
