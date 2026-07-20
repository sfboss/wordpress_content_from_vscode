import json
import re
from pathlib import Path


def _tasks():
    return json.loads(Path('.vscode/tasks.json').read_text(encoding='utf-8'))['tasks']


def test_run_core_stability_suite_task_is_default_test_gate():
    task = next(task for task in _tasks() if task['label'] == 'Tests: Run Core Stability Suite')
    assert task['type'] == 'process'
    assert task['command'] == '${command:python.interpreterPath}'
    assert task['args'] == [
        '-m',
        'pytest',
        '-m',
        'not live',
        '--cov=wp_factory',
        '--cov-branch',
        '--cov-report=term-missing',
        '--cov-fail-under=30',
    ]
    assert task['options']['cwd'] == '${workspaceFolder}'
    assert task['group'] == {'kind': 'test', 'isDefault': True}


def test_functional_factory_tasks_reference_known_cli_commands_and_tools():
    labels_to_commands = {task['label']: task.get('command', '') for task in _tasks()}
    assert 'Factory: Run tests' not in labels_to_commands
    assert 'Factory: Create website folder(s)' in labels_to_commands
    # Setup Python and Open Web UI are bootstrap/launcher helpers, not wp_factory CLI product commands.
    functional = {
        label: command
        for label, command in labels_to_commands.items()
        if label.startswith('Factory')
        and 'Setup Python' not in label
        and 'Open Web UI' not in label
        and not label.startswith('Factory Tools: Featured images then')
    }
    allowed_commands = {'doctor', 'lint', 'plan', 'push', 'pull', 'verify', 'new-site'}
    allowed_tools = {'image-fixer', 'external-linker', 'internal-linker', 'site-dashboard', 'featured-image-fixer', 'seo-audit', 'readability', 'link-health', 'schema-suggest', 'publish-readiness', 'content-overlap'}
    for label, command in functional.items():
        if label == 'Tests: Run Core Stability Suite':
            continue
        match = re.search(r'wp_factory ([\w-]+)', command)
        assert match, label
        cli_command = match.group(1)
        assert cli_command in allowed_commands | {'tools'}, label
        if cli_command == 'tools' and ' run ' in command and '${input:factoryTool}' not in command:
            tool = re.search(r"tools run '?([\w-]+)'?", command).group(1)
            assert tool in allowed_tools, label


def test_open_web_ui_task_points_at_frontend_server():
    task = next(task for task in _tasks() if task['label'] == 'Factory: Open Web UI')
    assert task['type'] == 'shell'
    assert 'frontend/server.py' in task['command']
    assert 'frontend/requirements.txt' in task['command']
