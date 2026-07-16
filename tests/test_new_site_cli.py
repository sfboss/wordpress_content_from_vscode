import os
import subprocess
import sys
from pathlib import Path

import yaml


def run_cli(*args):
    env = os.environ.copy()
    env.pop('WP_USERNAME', None)
    env.pop('WP_APP_PASSWORD', None)
    return subprocess.run(
        [sys.executable, '-m', 'wp_factory', *args],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_new_site_creates_multiple_real_website_folders_and_is_idempotent():
    domains = ['salesforcetogithub.shop', 'praytoday.shop', '7ohwrecked.me']
    result = run_cli('new-site', *domains)
    assert result.returncode == 0, result.stderr
    for domain in domains:
        root = Path('websites') / domain
        assert root.is_dir()
        assert (root / 'content' / 'posts').is_dir()
        assert (root / 'content' / 'pages').is_dir()
        assert not (root / '.env').exists()
        config = yaml.safe_load((root / 'site.yaml').read_text(encoding='utf-8'))
        assert config['site']['url'] == f'https://{domain}'
        assert config['site']['name'] == domain
        env_example = (root / '.env.example').read_text(encoding='utf-8')
        assert f'WP_SITE_URL=https://{domain}' in env_example
        assert 'WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx' in env_example

    second = run_cli('new-site', *domains)
    assert second.returncode == 0, second.stderr
    assert 'leaving it unchanged' in second.stdout


def test_new_site_rejects_path_like_input():
    result = run_cli('new-site', '../outside.example')
    assert result.returncode == 1
    assert 'Use only domain folder names' in result.stderr
