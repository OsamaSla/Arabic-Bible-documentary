#!/usr/bin/env python3
"""Weekly auto-deploy: if anything changed since last deploy, rebuild + push.

Friday 03:00 via Task Scheduler. Silent when nothing to do.
Logs to logs/weekly-deploy.log. Toasts (best-effort) on skip/failure.
Usage: weekly_deploy.py [--check-only] [--force]
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SOURCE_DIR = Path(r'D:\MegaDrive\ترجمات')
LAST_BUILD = BASE_DIR / '.last_build'
LOG_DIR = BASE_DIR / 'logs'
LOG_FILE = LOG_DIR / 'weekly-deploy.log'
RUN_LOCK = BASE_DIR / '.weekly_deploy.lock'

sys.path.insert(0, str(BASE_DIR / 'scripts'))
from git_ops import git_add_commit_push


def log(msg):
    LOG_DIR.mkdir(exist_ok=True)
    line = f'{datetime.now().isoformat(timespec="seconds")} {msg}'
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def notify(title, message):
    """Best-effort Windows notification (toast, then balloon); never raises."""
    t = str(title).replace("'", "").replace('"', '')[:120]
    m = str(message).replace("'", "").replace('"', '')[:200]
    try:
        ps_toast = (
            "$ErrorActionPreference='SilentlyContinue';"
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
            "$d = New-Object Windows.Data.Xml.Dom.XmlDocument;"
            "$d.LoadXml(\"<toast><visual><binding template='ToastGeneric'><text>" + t + "</text><text>" + m + "</text></binding></visual></toast>\");"
            "$n = [Windows.UI.Notifications.ToastNotification]::new($d);"
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ArabicBibleDeploy').Show($n);"
        )
        subprocess.run(['powershell', '-NoProfile', '-Command', ps_toast],
                       capture_output=True, timeout=30)
    except Exception:
        pass
    try:
        ps_balloon = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$n = New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon = [System.Drawing.SystemIcons]::Information;"
            "$n.Visible = $true;"
            "$n.BalloonTipTitle = \"" + t + "\";"
            "$n.BalloonTipText = \"" + m + "\";"
            "$n.ShowBalloonTip(5000);"
            "Start-Sleep -Seconds 6;"
            "$n.Dispose();"
        )
        subprocess.run(['powershell', '-NoProfile', '-STA', '-Command', ps_balloon],
                       capture_output=True, timeout=30)
    except Exception:
        pass


def last_build_time():
    try:
        return datetime.fromisoformat(LAST_BUILD.read_text(encoding='utf-8').strip())
    except (OSError, ValueError):
        return None


def changed_sources(since):
    """Docx files modified after last build (skip Word temp/lock files)."""
    if not SOURCE_DIR.exists():
        return []
    out = []
    for p in SOURCE_DIR.rglob('*.docx'):
        name = p.name
        if name.startswith('~') or name.startswith('~$'):
            continue
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
        except OSError:
            continue
        if since is None or mtime > since:
            out.append(str(p))
    return out


def word_locks_present():
    """True if Word currently holds files open (user mid-edit)."""
    if not SOURCE_DIR.exists():
        return False
    for _p in SOURCE_DIR.rglob('~$*.docx'):
        return True
    return False


def git_dirty():
    try:
        r = subprocess.run(['git', 'status', '--porcelain'], cwd=str(BASE_DIR),
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=30)
        return bool(r.stdout.strip()) if r.returncode == 0 else False
    except Exception:
        return False


def pending_changes():
    since = last_build_time()
    src = changed_sources(since)
    dirty = git_dirty()
    return src, dirty


def run_build():
    try:
        r = subprocess.run([sys.executable, str(BASE_DIR / 'scripts' / 'build.py')],
                           cwd=str(BASE_DIR), capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=1500)
        for line in (r.stdout or '').splitlines()[-5:]:
            log('  build: ' + line)
        if r.returncode != 0:
            log('  build stderr: ' + (r.stderr or '')[-2000:])
            return False
        return True
    except subprocess.TimeoutExpired:
        log('  build timed out.')
        return False


def main():
    check_only = '--check-only' in sys.argv
    force = '--force' in sys.argv
    log('weekly-deploy run (check_only=%s force=%s).' % (check_only, force))

    if RUN_LOCK.exists() and not force:
        log('another run is active; skipping.')
        return 0
    try:
        RUN_LOCK.write_text(str(datetime.now().isoformat()), encoding='utf-8')
    except OSError:
        pass

    try:
        if word_locks_present() and not force:
            log('Word lock files present (editing in progress); skipping deploy.')
            notify('Arabic Bible deploy skipped',
                   'Word files are open right now; weekly auto-deploy skipped. Deploy manually when done.')
            return 0

        src, dirty = pending_changes()
        if not src and not dirty and not force:
            log('no changes since last deploy; nothing to do.')
            return 0

        if check_only:
            log(f'would deploy: {len(src)} changed source files, git_dirty={dirty}.')
            return 0

        log(f'deploying: {len(src)} changed source files, git_dirty={dirty}.')
        if not run_build():
            notify('Arabic Bible deploy FAILED', 'Weekly build failed. See logs/weekly-deploy.log.')
            return 1
        ok, detail = git_add_commit_push(
            message=f'Auto-deploy: weekly ({datetime.now().strftime("%Y-%m-%d")})')
        log('git: ' + detail)
        if not ok:
            notify('Arabic Bible deploy FAILED', detail[:200])
            return 1
        return 0
    finally:
        try:
            RUN_LOCK.unlink()
        except OSError:
            pass


if __name__ == '__main__':
    sys.exit(main())


TASK_NAME = 'ArabicBibleWeeklyDeploy'
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def get_weekly_status():
    """Task/next-run/last-run info + last successful deploy timestamp."""
    info = {'task': False, 'next_run': None, 'last_run': None,
            'last_result': None, 'last_deploy': None}
    try:
        r = subprocess.run(['schtasks', '/query', '/tn', TASK_NAME, '/fo', 'LIST', '/v'],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=30)
        if r.returncode == 0:
            info['task'] = True
            for line in (r.stdout or '').splitlines():
                t = line.strip()
                for key, field in (('next_run', 'Next Run Time:'),
                                   ('last_run', 'Last Run Time:'),
                                   ('last_result', 'Last Result:')):
                    if t.startswith(field):
                        v = t[len(field):].strip()
                        info[key] = None if v in ('N/A', '') else v
    except Exception:
        pass
    try:
        if LOG_FILE.exists():
            for line in reversed(LOG_FILE.read_text(encoding='utf-8', errors='replace').splitlines()):
                if 'Pushed to' in line:
                    info['last_deploy'] = line[:19]
                    break
    except OSError:
        pass
    return info


def register_weekly_schedule(day='Friday', time_str='03:00'):
    """(Re)create the weekly scheduled task. Returns (ok, detail)."""
    import re as _re
    import tempfile
    day = (day or '').strip().capitalize()
    if day not in WEEKDAYS:
        return False, 'Day must be Monday..Sunday.'
    time_str = (time_str or '').strip()
    if not _re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', time_str):
        return False, 'Time must be HH:MM (24h).'
    from datetime import date, timedelta
    idx = {d.lower(): i for i, d in enumerate(WEEKDAYS)}
    first = date.today() + timedelta(days=(idx[day.lower()] - date.today().weekday()) % 7)
    start = f'{first.isoformat()}T{time_str}:00'
    py = sys.executable
    repo = str(BASE_DIR)
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Weekly auto-deploy for Arabic Bible site: rebuild + push only if changed.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <ScheduleByWeek>
        <DaysOfWeek><{day} /></DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{py}</Command>
      <Arguments>-X utf8 scripts\\weekly_deploy.py</Arguments>
      <WorkingDirectory>{repo}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                         encoding='utf-16') as f:
            f.write(xml)
            tmp = f.name
        r = subprocess.run(['schtasks', '/create', '/tn', TASK_NAME, '/xml', tmp, '/f'],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=60)
    except Exception as e:
        return False, f'schedule failed: {e}'
    if r.returncode != 0:
        return False, ((r.stderr or r.stdout) or 'schtasks failed').strip()[:300]
    info = get_weekly_status()
    return True, 'Schedule saved: %s %s (next: %s).' % (day, time_str, info.get('next_run') or '?')
