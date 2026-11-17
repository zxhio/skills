#!/usr/bin/env python3
"""Check a local/SSH target or deploy a prepared artifact and verify it."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import zipfile

import ci_artifacts


class DeployError(RuntimeError):
    pass


def execute(argv, timeout, *, script=None, source=None, capture=False, env=None, cwd=None):
    with subprocess.Popen(argv, stdin=subprocess.PIPE if script is not None else source,
                          stdout=subprocess.PIPE if capture else sys.stderr,
                          stderr=sys.stderr, env=env, cwd=cwd, start_new_session=True) as proc:
        try:
            output, _ = proc.communicate(script.encode() if script is not None else None,
                                         timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise DeployError('Command timed out or was interrupted; check target state before retrying') from exc
        if proc.returncode:
            raise DeployError(f'Command failed with exit status {proc.returncode}')
        return output.decode().strip() if capture else ''


def ssh(args, command):
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-p', str(args.port), '--', args.host, command]


def remote(args, script, capture=False):
    return execute(ssh(args, 'sh -s'), args.timeout, script=script, capture=capture)


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def probe(args):
    script = 'set -eu\ncommand -v sh >/dev/null\nid -un\nuname -s\n'
    if args.host == 'local':
        output = execute(['sh', '-s'], args.timeout, script=script, capture=True)
    else:
        script += 'command -v sha256sum >/dev/null || command -v shasum >/dev/null\n'
        output = remote(args, script, capture=True)
    return {'host': args.host, 'port': args.port if args.host != 'local' else None,
            'probe': output.splitlines(), 'reachable': True}


def payload(command, stage, artifact, cwd):
    return ('set -eu\n'
            f'export WORKFLOW_STAGE={shlex.quote(stage)}\n'
            f'export WORKFLOW_ARTIFACT={shlex.quote(artifact)}\n'
            + (f'cd {shlex.quote(cwd)}\n' if cwd else '')
            + command + '\n')


def deploy(args, result):
    source = Path(args.artifact).expanduser().resolve() if args.artifact else None
    if source and not source.is_file():
        raise DeployError('Artifact must be an existing regular file')
    if args.sha256 and (not source or not re.fullmatch(r'[0-9a-fA-F]{64}', args.sha256)):
        raise DeployError('--sha256 requires an artifact and a 64-character SHA-256')
    checksum = digest(source) if source else None
    if args.sha256 and checksum != args.sha256.lower():
        raise DeployError('Source artifact SHA-256 does not match --sha256')
    if not args.install.strip() or not args.verify.strip():
        raise DeployError('Installation and verification commands must be non-empty')
    if args.cwd and args.host != 'local' and not args.cwd.startswith('/'):
        raise DeployError('Remote --cwd must be an absolute path')
    result.update({'artifact': str(source) if source else None, 'sha256': checksum,
                   'ref': args.ref, 'phase': 'check'})
    result['target'] = probe(args)
    if args.host == 'local':
        stage = tempfile.mkdtemp(prefix='workflow-deploy-')
    else:
        stage = remote(args, 'set -eu\nmktemp -d /tmp/workflow-deploy-XXXXXXXXXX\n', capture=True)
        if not re.fullmatch(r'/tmp/workflow-deploy-[A-Za-z0-9]+', stage):
            raise DeployError('Target returned an invalid staging directory')
    result['stage'] = stage
    artifact = stage + '/artifact' if source else ''
    result['phase'] = 'transfer'
    if source:
        if args.host == 'local':
            shutil.copy2(source, artifact)
            actual = digest(Path(artifact))
        else:
            with source.open('rb') as stream:
                execute(ssh(args, f'umask 077; cat > {shlex.quote(artifact)}'),
                        args.timeout, source=stream)
            output = remote(args, f'''set -eu
if command -v sha256sum >/dev/null; then
  sha256sum {shlex.quote(artifact)}
else
  shasum -a 256 {shlex.quote(artifact)}
fi
''', capture=True).split()
            if not output:
                raise DeployError('Target returned no artifact checksum')
            actual = output[0]
        if actual != checksum:
            raise DeployError('Transferred artifact SHA-256 does not match source')
    for phase, command in [('install', args.install), ('verify', args.verify)]:
        result['phase'] = phase
        script = payload(command, stage, artifact, args.cwd)
        if args.host == 'local':
            execute(['sh', '-s'], args.timeout, script=script)
        else:
            remote(args, script)
    result['phase'] = 'cleanup'
    if not args.keep_stage:
        if args.host == 'local':
            shutil.rmtree(stage)
        else:
            remote(args, f'rm -rf -- {shlex.quote(stage)}\n')
    result.update({'phase': 'done', 'verified': True,
                   'stage_retained': args.keep_stage})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'inspect', 'run'))
    parser.add_argument('--host', help='local, SSH alias, or user@host; required for check/run')
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--artifact', help='Prepared local artifact; optional for command-only deployments')
    parser.add_argument('--sha256', help='Expected checksum from the trusted artifact source')
    parser.add_argument('--ref', help='GitLab branch/tag/SHA; with --artifact, a build label only')
    parser.add_argument('--mr', help='GitLab MR number, such as 123 or !123')
    parser.add_argument('--repo', default='.', help='Repository used to identify the GitLab project')
    parser.add_argument('--job', help='Package job name or ID; required when candidates are ambiguous')
    parser.add_argument('--pipeline', type=int, help='Select an exact-SHA pipeline ID')
    parser.add_argument('--gitlab-url', help='GitLab web URL override for self-hosted instances')
    parser.add_argument('--cwd', help='Existing working directory on the target')
    parser.add_argument('--install', help='Project installation command, executed by sh')
    parser.add_argument('--verify', help='Project verification command; nonzero means failure')
    parser.add_argument('--timeout', type=int, default=600, help='Timeout per phase in seconds')
    parser.add_argument('--keep-stage', action='store_true')
    args = parser.parse_args()
    result = {'action': args.action, 'host': args.host, 'verified': False}
    try:
        if (not 1 <= args.port <= 65535 or args.timeout <= 0
                or (args.pipeline is not None and args.pipeline <= 0)):
            raise DeployError('Invalid port, pipeline or timeout')
        if args.action != 'inspect' and (not args.host or args.host.startswith('-')
                                       or any(c.isspace() for c in args.host)):
            raise DeployError('Invalid host, port or timeout')
        if args.mr and (args.ref or args.artifact):
            raise DeployError('--mr cannot be combined with --ref or --artifact')
        if args.action == 'inspect' and args.artifact:
            raise DeployError('inspect resolves CI sources; use --mr or --ref')
        if args.action == 'run' and (not args.install or not args.verify):
            raise DeployError('run requires both --install and --verify')
        ci_source = bool(args.mr or (args.ref and not args.artifact))
        if (args.job or args.pipeline or args.gitlab_url) and not ci_source:
            raise DeployError('CI options require --mr or --ref without --artifact')
        if args.action == 'check':
            if ci_source:
                raise DeployError('Use inspect to check CI artifacts')
            result['target'] = probe(args)
        elif args.action == 'inspect':
            result['ci'] = ci_artifacts.inspect(args)
        else:
            if ci_source:
                result['phase'] = 'resolve'
                result['ci'] = ci_artifacts.inspect(args)
                if not result['ci']['ready']:
                    raise DeployError(result['ci']['reason'])
                result['phase'] = 'download'
                result['download_dir'] = tempfile.mkdtemp(prefix='workflow-artifact-')
                args.artifact = str(Path(result['download_dir']) / 'artifacts.zip')
                ci_artifacts.download(args, result['ci'], args.artifact)
                if not zipfile.is_zipfile(args.artifact):
                    raise DeployError('Downloaded CI artifact is not a valid ZIP archive')
                args.ref = result['ci']['sha']
            deploy(args, result)
            if result.get('download_dir') and not args.keep_stage:
                shutil.rmtree(result['download_dir'])
    except (DeployError, ci_artifacts.ArtifactError, OSError, ValueError, KeyError,
            KeyboardInterrupt) as exc:
        result.update({'error': str(exc) or 'Interrupted',
                       'stage_retained': bool(result.get('stage'))})
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
