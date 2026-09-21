"""Fetch public reference material only; never executes downloaded code."""
import hashlib
import json
from pathlib import Path
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
REPOS = {
    'mwdmwd/sc26re': 'master',
    'CouchTurtle/sc2-research': 'main',
    'iczero/steam-controller-stuff': 'master',
    'safijari/openpuck': 'main',
    'OpenSteamController/Ibex-Firmware': 'main',
    'libsdl-org/SDL': 'main',
}

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'SteamControllerCalibrationResearch'})
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read()

def main():
    manifest_path = ROOT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))['files'] if manifest_path.exists() else []
    for repo, branch in REPOS.items():
        if any(item['repository'] == repo for item in manifest):
            print(repo, 'already archived', flush=True)
            continue
        tree = json.loads(get(f'https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1'))
        commit = tree['sha']
        for entry in tree['tree']:
            path = entry['path']
            if entry['type'] != 'blob':
                continue
            if repo == 'libsdl-org/SDL':
                selected = path in ['src/joystick/hidapi/steam/controller_constants.h',
                    'src/joystick/hidapi/steam/controller_structs.h',
                    'src/joystick/hidapi/SDL_hidapi_steam_triton.c', 'LICENSE.txt']
            elif repo == 'mwdmwd/sc26re':
                selected = path.endswith(('.md', '.c', '.h')) and not path.startswith('bootstub/')
                selected = selected or path == 'LICENSE'
            else:
                selected = path.endswith('.md') or path in ('LICENSE', 'LICENSE.txt', 'tools/attr_query.py')
            if not selected:
                continue
            url = f'https://raw.githubusercontent.com/{repo}/{commit}/{path}'
            data = get(url)
            target = ROOT / 'sources' / repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            manifest.append(dict(repository=repo, revision=commit, path=path, url=url,
                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))
        print(repo, commit, flush=True)
        (ROOT / 'manifest.json').write_text(json.dumps(dict(
            fetched_at=datetime.now(timezone.utc).isoformat(), files=manifest), indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
