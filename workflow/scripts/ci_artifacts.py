"""Resolve GitLab refs/MRs to exact-SHA CI artifacts using read-only API calls."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request


class ArtifactError(RuntimeError):
    pass


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        before, after = urlsplit(req.full_url), urlsplit(newurl)
        if before.scheme == 'https' and after.scheme != 'https':
            raise ArtifactError('Refusing an HTTPS artifact redirect to an insecure URL')
        if redirected and (before.scheme, before.netloc) != (after.scheme, after.netloc):
            for header in list(redirected.headers):
                if header.lower() in ('private-token', 'authorization'):
                    del redirected.headers[header]
        return redirected


def repository(path):
    proc = subprocess.run(['git', '-C', str(Path(path).expanduser()),
                           'remote', 'get-url', 'origin'], capture_output=True, text=True)
    if proc.returncode:
        raise ArtifactError('Cannot read repository origin; use --repo')
    origin = proc.stdout.strip()
    if '://' not in origin:
        match = re.fullmatch(r'(?:[^@/]+@)?([^:/]+):(.+)', origin)
        if not match:
            raise ArtifactError('Origin must be a GitLab HTTP(S) or SSH URL')
        host, project = match.groups()
    else:
        parsed = urlsplit(origin)
        host = parsed.hostname
        if parsed.scheme in ('http', 'https') and parsed.port:
            host += ':' + str(parsed.port)
        project = parsed.path.lstrip('/')
    if not host or not project:
        raise ArtifactError('Origin does not identify a GitLab project')
    return host, project.removesuffix('.git')


def token_for(host):
    for name in ('GITLAB_TOKEN', 'GL_TOKEN', 'GLAB_TOKEN'):
        if os.environ.get(name):
            return os.environ[name]
    if shutil.which('glab'):
        try:
            proc = subprocess.run(['glab', 'config', 'get', 'token', '--host', host],
                                  capture_output=True, text=True, timeout=15)
        except subprocess.TimeoutExpired as exc:
            raise ArtifactError('GitLab credential lookup timed out') from exc
        if proc.returncode == 0:
            return proc.stdout.strip()
    return None


class GitLab:
    def __init__(self, url, token=None, timeout=60):
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username:
            raise ArtifactError('Invalid --gitlab-url')
        self.base = url.rstrip('/') + '/api/v4/'
        self.headers = {'PRIVATE-TOKEN': token} if token else {}
        self.timeout = timeout
        self.opener = build_opener(Redirects())

    def open(self, path):
        try:
            return self.opener.open(Request(self.base + path, headers=self.headers),
                                    timeout=self.timeout)
        except HTTPError as exc:
            raise ArtifactError(f'GitLab HTTP {exc.code}; check access and artifact availability') from exc
        except (URLError, TimeoutError) as exc:
            raise ArtifactError('GitLab request failed; check connectivity') from exc

    def get(self, path):
        with self.open(path) as response:
            try:
                return json.load(response)
            except (ValueError, UnicodeError) as exc:
                raise ArtifactError('GitLab returned invalid JSON') from exc

    def listing(self, path, **params):
        page = '1'
        while page:
            query = urlencode({**params, 'per_page': 100, 'page': page})
            with self.open(path + '?' + query) as response:
                items = json.load(response)
                if not isinstance(items, list):
                    raise ArtifactError('GitLab returned an invalid list')
                yield from items
                page = response.headers.get('X-Next-Page', '')

    def download(self, path, destination):
        with self.open(path) as response, Path(destination).open('xb') as stream:
            shutil.copyfileobj(response, stream, 1024 * 1024)


def inspect(args):
    host, project = repository(args.repo)
    client = GitLab(args.gitlab_url or 'https://' + host, token_for(host), args.timeout)
    project_info = client.get('projects/' + quote(project, safe=''))
    project_id = project_info['id']
    result = {'provider': 'gitlab', 'project': project, 'project_id': project_id,
              'gitlab_url': client.base.removesuffix('/api/v4/'), 'ready': False}
    if args.mr:
        number = str(args.mr).lstrip('!')
        if not number.isdigit() or int(number) < 1:
            raise ArtifactError('--mr must be a positive MR number, such as 123 or !123')
        mr = client.get(f'projects/{project_id}/merge_requests/{number}')
        if not mr.get('source_project_id') or not mr.get('sha'):
            raise ArtifactError('MR has no available source project or source SHA')
        sha = mr['sha']
        source_id = mr['source_project_id']
        result.update({'mr': int(number), 'ref': mr['source_branch'], 'sha': sha,
                       'source_project_id': source_id})
        pipelines = list(client.listing(f'projects/{project_id}/merge_requests/{number}/pipelines'))
        for pipeline in pipelines:
            pipeline.setdefault('project_id', project_id)
        source_pipelines = list(client.listing(f'projects/{source_id}/pipelines', sha=sha,
                                               order_by='id', sort='desc'))
        for pipeline in source_pipelines:
            pipeline.setdefault('project_id', source_id)
        pipelines += source_pipelines
    else:
        if not args.ref:
            raise ArtifactError('Provide --mr or --ref to resolve CI artifacts')
        commit = client.get(f'projects/{project_id}/repository/commits/' + quote(args.ref, safe=''))
        sha = commit['id']
        result.update({'ref': args.ref, 'sha': sha})
        pipelines = list(client.listing(f'projects/{project_id}/pipelines', sha=sha,
                                       order_by='id', sort='desc'))
    pipelines = [p for p in pipelines if p.get('sha') == sha]
    if args.pipeline:
        pipelines = [p for p in pipelines if p['id'] == args.pipeline]
    if not pipelines:
        result['reason'] = 'No pipeline matches the exact source SHA'
        return result
    pipeline = max(pipelines, key=lambda p: p['id'])
    pipeline_project = pipeline.get('project_id', result.get('source_project_id', project_id))
    result['pipeline'] = {k: pipeline.get(k) for k in ('id', 'sha', 'status', 'web_url')}
    result['pipeline']['project_id'] = pipeline_project
    jobs = list(client.listing(f'projects/{pipeline_project}/pipelines/{pipeline["id"]}/jobs',
                               include_retried='false'))
    for job in jobs:
        if job.get('commit', {}).get('id', sha) != sha:
            raise ArtifactError('Pipeline job SHA does not match the pinned source SHA')
    result['jobs'] = [{k: j.get(k) for k in ('id', 'name', 'stage', 'status', 'web_url')}
                      for j in jobs]
    if args.job:
        candidates = [j for j in jobs if j['name'] == args.job or str(j['id']) == args.job]
    else:
        candidates = [j for j in jobs if j['name'].startswith('package:')
                      or j.get('stage') in ('package', 'packaging')]
        if not candidates:
            candidates = [j for j in jobs if j.get('artifacts_file', {}).get('filename')]
    # A retried job name has one latest attempt, even on older GitLab versions.
    newest = {}
    for job in sorted(candidates, key=lambda j: j['id']):
        newest[job['name']] = job
    candidates = list(newest.values())
    result['candidates'] = [{k: j.get(k) for k in ('id', 'name', 'status', 'web_url')}
                            for j in candidates]
    if len(candidates) != 1:
        result['reason'] = ('Multiple package jobs; select --job from candidates' if candidates
                            else 'No package job matches; select --job from jobs')
        return result
    job = candidates[0]
    result['job'] = {k: job.get(k) for k in ('id', 'name', 'status', 'web_url')}
    result['artifact_name'] = job.get('artifacts_file', {}).get('filename')
    if job['status'] != 'success' or not result['artifact_name']:
        result['reason'] = 'Selected package job is not successful or has no artifacts'
        return result
    expiry = job.get('artifacts_expire_at')
    if expiry and datetime.fromisoformat(expiry.replace('Z', '+00:00')) <= datetime.now(timezone.utc):
        result['reason'] = 'Selected package artifacts have expired'
        return result
    result['ready'] = True
    return result


def download(args, resolved, destination):
    host, _ = repository(args.repo)
    client = GitLab(resolved['gitlab_url'], token_for(host), args.timeout)
    project_id = resolved['pipeline']['project_id']
    # Recheck the selected job ID immediately before downloading, without resolving the ref again.
    job = client.get(f'projects/{project_id}/jobs/{resolved["job"]["id"]}')
    if job.get('status') != 'success' or job.get('commit', {}).get('id') != resolved['sha']:
        raise ArtifactError('Selected artifact job is no longer valid for the pinned SHA')
    if job.get('pipeline', {}).get('id') != resolved['pipeline']['id']:
        raise ArtifactError('Selected artifact job belongs to a different pipeline')
    client.download(f'projects/{project_id}/jobs/{job["id"]}/artifacts', destination)
