"""Observe an existing NetCroc process and aggregate history progress locally.

No network requests, credentials, interface changes, service or startup entry.
This observes process/history liveness, not GUI responsiveness or a full leak audit.
"""
import argparse
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sqlite3
import sys
import time
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from netcroc.core import data_folder

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pid',required=True,type=int);parser.add_argument('--hours',type=float,default=24)
    args=parser.parse_args()
    if not 0<args.hours<=72:raise ValueError('Use a duration up to 72 hours.')
    process=psutil.Process(args.pid)
    if Path(process.exe()).resolve()!= (ROOT/'releases'/'NetCroc.exe').resolve():raise ValueError('Observe only this NetCroc executable.')
    identity=process.create_time();started=time.time();deadline=started+args.hours*3600
    path=ROOT/'test-artifacts'/'longrun-status.json'
    db=data_folder()/'usage.sqlite3'
    local=timezone(timedelta(hours=5,minutes=30))
    report={'state':'running','pid':args.pid,'observer_pid':psutil.Process().pid,'planned_hours':args.hours,
        'started_local':datetime.fromtimestamp(started,local).isoformat(),
        'due_local':datetime.fromtimestamp(deadline,local).isoformat(),
        'samples':0,'history_read_errors':0,'sampling_gaps':0,'sampled_seconds':0,
        'scope':'process and aggregate history liveness; not GUI responsiveness or sleep/resume certification'}
    first_coverage=None;previous_coverage=None;last=None;stalled=0
    def save():
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2),encoding='utf-8');temporary.replace(path)
    try:
        while True:
            now=time.time()
            if not process.is_running() or process.create_time()!=identity:
                report['state']='app exited or replaced';break
            rss=process.memory_info().rss;handles=process.num_handles()
            report['rss_min']=min(report.get('rss_min',rss),rss);report['rss_max']=max(report.get('rss_max',rss),rss)
            report['handles_min']=min(report.get('handles_min',handles),handles);report['handles_max']=max(report.get('handles_max',handles),handles)
            if last is not None:
                gap=max(0,now-last);report['sampled_seconds']+=min(gap,60)
                if gap>90:report['sampling_gaps']+=1
            last=now
            try:
                with sqlite3.connect('file:'+db.as_posix()+'?mode=ro',uri=True,timeout=2) as connection:
                    coverage=connection.execute('SELECT COALESCE(SUM(seconds),0) FROM coverage_minute').fetchone()[0]
                if first_coverage is None:first_coverage=coverage
                stalled=stalled+1 if previous_coverage is not None and coverage==previous_coverage else 0
                previous_coverage=coverage
                report['history_coverage_delta_seconds']=round(coverage-first_coverage,2)
                report['consecutive_no_progress_samples']=stalled
                report['max_no_progress_samples']=max(stalled,report.get('max_no_progress_samples',0))
            except sqlite3.Error:report['history_read_errors']+=1
            report['samples']+=1;report['elapsed_hours']=round((now-started)/3600,4)
            report['last_sample_local']=datetime.fromtimestamp(now,local).isoformat()
            if now>=deadline:
                report['state']='completed observation period'
                report['passed_process_history_observation']=(report['sampled_seconds']>=args.hours*3600*.95 and report['history_read_errors']==0 and report.get('history_coverage_delta_seconds',0)>0 and report.get('max_no_progress_samples',0)<3)
                break
            save();time.sleep(min(30,max(0,deadline-time.time())))
    except psutil.NoSuchProcess:report['state']='app exited'
    except Exception as error:report['state']='observer error';report['error_type']=type(error).__name__
    finally:save()

if __name__=='__main__':main()
