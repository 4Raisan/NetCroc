"""Repeatable, low-volume endpoint study. Results describe this connection only."""
import json
from pathlib import Path
import statistics
import time
import urllib.error
import urllib.request

CANDIDATES={
    'Dialog':('https://www.dialog.lk/','https://www.dialog.lk/robots.txt'),
    'SLT':('https://www.slt.lk/','https://www.slt.lk/robots.txt'),
    'Mobitel':('https://www.mobitel.lk/','https://www.mobitel.lk/robots.txt'),
    'Airtel':('https://www.airtel.lk/','https://www.airtel.lk/robots.txt'),
    'Hutch':('https://hutch.lk/','https://hutch.lk/robots.txt'),
}

def head(url):
    start=time.perf_counter()
    request=urllib.request.Request(url,method='HEAD',headers={'User-Agent':'NetCroc/0.2 (connection check)'})
    try:
        try:
            response=urllib.request.urlopen(request,timeout=4)
        except urllib.error.HTTPError as error:
            response=error
        with response:
            return {'url':url,'final_url':response.url,'status':response.code,
                    'ms':round((time.perf_counter()-start)*1000,2),'error':None}
    except (OSError,ValueError) as error:
        return {'url':url,'final_url':None,'status':None,'ms':round((time.perf_counter()-start)*1000,2),
                'error':type(error).__name__}

def study(rounds=3):
    results=[]
    for isp,urls in CANDIDATES.items():
        for url in urls:
            samples=[]
            for _ in range(rounds):
                result=head(url); samples.append(result)
                if result['status'] in (403,405,429) or result['status'] and result['status']>=500:
                    break  # Do not hammer endpoints refusing checks.
                time.sleep(1)
            good=[s for s in samples if s['status'] and 200<=s['status']<400]
            results.append({'isp':isp,'url':url,'success':len(good),'attempts':len(samples),
                            'median_ms':statistics.median(s['ms'] for s in good) if good else None,'samples':samples})
    return results

def recommendations(results):
    chosen={}
    for isp in CANDIDATES:
        options=[r for r in results if r['isp']==isp and r['success']==r['attempts'] and r['success']>=2]
        if options:
            chosen[isp]=min(options,key=lambda r:r['median_ms'])['url']
    return chosen

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--output',required=True); parser.add_argument('--rounds',type=int,default=3)
    args=parser.parse_args()
    result=study(args.rounds)
    Path(args.output).write_text(json.dumps({'tested_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'scope':'One current connection, no ISP-specific speed improvement proven',
        'results':result,'recommended_for_retest':recommendations(result)},indent=2),encoding='utf-8')
    print('Endpoint study saved. Recommendations are local HEAD response results, not speed-up claims.')
