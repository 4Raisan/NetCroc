"""Release checks show information only and never install updates."""
import json
import re
import urllib.request

VERSION='0.4.0-beta.3+dev'
REPO='https://github.com/4Raisan/NetCroc'
API='https://api.github.com/repos/4Raisan/NetCroc/releases?per_page=30'

def version_key(text):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.?([0-9]+))?(?:\+[A-Za-z0-9.-]+)?',str(text),re.I)
    if not match:return None
    major,minor,patch,kind,num=match.groups()
    return (int(major),int(minor),int(patch),{'alpha':0,'beta':1,'rc':2,None:3}[kind.lower() if kind else None],int(num or 0))

def check(opener=urllib.request.urlopen):
    request=urllib.request.Request(API,headers={'Accept':'application/vnd.github+json','User-Agent':'NetCroc-update-check'})
    with opener(request,timeout=8) as response:
        data=response.read(512*1024+1)
    if len(data)>512*1024:raise ValueError('Release list too large')
    items=json.loads(data)
    if not isinstance(items,list):raise ValueError('Invalid release list')
    found=[]
    for item in items:
        if not isinstance(item,dict) or item.get('draft'):continue
        tag=item.get('tag_name','');key=version_key(tag)
        if key:found.append((key,tag))
    if not found:return {'status':'unavailable'}
    key,tag=max(found)
    return {'status':'available' if key>version_key(VERSION) else 'current','version':tag,'url':REPO+'/releases'}
