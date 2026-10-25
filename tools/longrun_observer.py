"""Bounded process/history observation with explicit gaps and optional awake-time target."""
import argparse
import ctypes
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from netcroc.core import data_folder


def awake_clock():
    """Windows awake uptime excludes suspend; other hosts report unknown."""
    if os.name!='nt':return None
    value=ctypes.c_ulonglong()
    if not ctypes.windll.kernel32.QueryUnbiasedInterruptTime(ctypes.byref(value)):return None
    return value.value/10_000_000


def interval(previous,current,previous_awake=None,current_awake=None):
    gap=max(0,current-previous)
    awake=None if previous_awake is None or current_awake is None else max(0,current_awake-previous_awake)
    observed=min(gap if awake is None else awake,60)
    return dict(wall_seconds=gap,observed_seconds=observed,
        awake_seconds=awake,suspend_estimate_seconds=None if awake is None else max(0,gap-awake),
        sampling_gap=gap>90)


class KeepAwake:
    """Thread-scoped request, not a persistent Windows power-plan change."""
    def __init__(self,enabled):self.enabled=enabled and os.name=='nt'
    def __enter__(self):
        if self.enabled and not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):raise OSError('Could not request awake observation.')
        return self.enabled
    def __exit__(self,*args):
        if self.enabled:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def evaluate(report,target_seconds):
    uninterrupted=(report['sampled_seconds']>=target_seconds*.95 and report['history_read_errors']==0 and report.get('history_coverage_delta_seconds',0)>=target_seconds*.9 and report.get('max_no_progress_samples',0)<3)
    return bool(uninterrupted)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pid',required=True,type=int);parser.add_argument('--hours',type=float,default=24)
    parser.add_argument('--active-hours',type=float);parser.add_argument('--max-wall-hours',type=float,default=72)
    parser.add_argument('--sample-seconds',type=float,default=30);parser.add_argument('--keep-awake',action='store_true')
    parser.add_argument('--exe',type=Path,default=ROOT/'releases/NetCroc.exe')
    parser.add_argument('--report',type=Path,default=ROOT/'test-artifacts/longrun-v2-status.json')
    args=parser.parse_args()
    if not 0<args.hours<=72 or not .5<=args.sample_seconds<=60 or not 0<args.max_wall_hours<=72 or args.active_hours is not None and not 0<args.active_hours<=72:raise ValueError('Invalid bounded observation duration.')
    target=args.exe.resolve()
    if not target.is_relative_to(ROOT.resolve()) or not target.is_file():raise ValueError('Executable must be inside this NetCroc checkout.')
    process=psutil.Process(args.pid)
    if Path(process.exe()).resolve()!=target:raise ValueError('PID does not match the selected NetCroc executable.')
    if args.active_hours and awake_clock() is None:raise ValueError('Awake-time targeting requires an available Windows awake-uptime clock.')
    path=args.report.resolve()
    if not path.is_relative_to((ROOT/'test-artifacts').resolve()):raise ValueError('Report must stay inside local test-artifacts.')
    if path.exists():raise ValueError('Preserve existing evidence; choose a new report filename.')
    path.parent.mkdir(exist_ok=True)
    identity=process.create_time();started=time.time();start_awake=awake_clock();deadline=started+(args.max_wall_hours if args.active_hours else args.hours)*3600
    db=data_folder()/'usage.sqlite3';local=timezone(timedelta(hours=5,minutes=30))
    import hashlib
    report=dict(state='running',pid=args.pid,observer_pid=os.getpid(),planned_hours=args.active_hours or args.hours,
        target='awake uptime' if args.active_hours else 'wall time',started_local=datetime.fromtimestamp(started,local).isoformat(),
        maximum_end_local=datetime.fromtimestamp(deadline,local).isoformat(),exe_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        samples=0,history_read_errors=0,sampling_gaps=0,gaps=[],sampled_seconds=0,suspend_estimate_seconds=0,
        scope='process and aggregate history liveness only; no GUI responsiveness, provider VPN or sleep/resume network certification')
    first=None;previous_coverage=None;last=None;last_awake=None;stalled=0
    def save():
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2),encoding='utf-8');temp.replace(path)
    try:
        with KeepAwake(args.keep_awake) as held:
            report['keep_awake_request']=held
            while True:
                now=time.time();awake=awake_clock()
                if not process.is_running() or process.create_time()!=identity:report['state']='app exited or replaced';break
                rss=process.memory_info().rss
                count=process.num_handles() if os.name=='nt' else process.num_fds()
                report['rss_min']=min(report.get('rss_min',rss),rss);report['rss_max']=max(report.get('rss_max',rss),rss)
                report['handles_or_fds_min']=min(report.get('handles_or_fds_min',count),count);report['handles_or_fds_max']=max(report.get('handles_or_fds_max',count),count)
                if last is not None:
                    value=interval(last,now,last_awake,awake);report['sampled_seconds']+=value['observed_seconds']
                    report['suspend_estimate_seconds']+=value['suspend_estimate_seconds'] or 0
                    if value['sampling_gap']:
                        report['sampling_gaps']+=1;report['gaps'].append(dict(start=datetime.fromtimestamp(last,local).isoformat(),end=datetime.fromtimestamp(now,local).isoformat(),**value))
                last=now;last_awake=awake
                try:
                    with sqlite3.connect('file:'+db.as_posix()+'?mode=ro',uri=True,timeout=2) as connection:coverage=connection.execute('SELECT COALESCE(SUM(seconds),0) FROM coverage_minute').fetchone()[0]
                    if first is None:first=coverage
                    stalled=stalled+1 if previous_coverage is not None and coverage==previous_coverage else 0;previous_coverage=coverage
                    report['history_coverage_delta_seconds']=round(coverage-first,2);report['max_no_progress_samples']=max(stalled,report.get('max_no_progress_samples',0))
                except sqlite3.Error:report['history_read_errors']+=1
                report['samples']+=1;report['elapsed_wall_hours']=(now-started)/3600
                report['elapsed_awake_hours']=None if awake is None or start_awake is None else max(0,awake-start_awake)/3600
                report['last_sample_local']=datetime.fromtimestamp(now,local).isoformat()
                reached=report['elapsed_awake_hours']>=args.active_hours if args.active_hours else now-started>=args.hours*3600
                if reached or now>=deadline:
                    report['state']='completed observation target' if reached else 'maximum wall time reached'
                    report['passed_process_history_observation']=bool(reached and evaluate(report,(args.active_hours or args.hours)*3600));break
                save();time.sleep(min(args.sample_seconds,max(0,deadline-time.time())))
    except psutil.NoSuchProcess:report['state']='app exited'
    except Exception as error:report['state']='observer error';report['error_type']=type(error).__name__
    finally:save()

if __name__=='__main__':main()
