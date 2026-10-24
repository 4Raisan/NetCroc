"""Local byte accounting with rolling/calendar periods and 62-day retention."""
import csv
import sqlite3
import threading
from datetime import date, datetime, timedelta

K = 1024
RETENTION_DAYS = 62
PERIODS = ('Last 30 days', 'Last month', 'This month')

def period_bounds(period, now=None):
    now = now or datetime.now()
    month = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    if period == 'Last 30 days':
        return now-timedelta(days=30),now
    if period == 'Last month':
        return (month-timedelta(days=1)).replace(day=1),month
    if period == 'This month':
        return month,now
    raise ValueError('Choose Last 30 days, Last month or This month.')

def speed(value):
    value = max(0, value)
    if value >= K ** 3:
        return f'{value / K ** 3:.2f} GB/s'
    if value >= 2 * K ** 2:
        return f'{value / K ** 2:.2f} MB/s'
    return f'{value / K:.2f} KB/s'

def volume(value):
    for size, label in ((K**4, 'TB'), (K**3, 'GB'), (K**2, 'MB'), (K, 'KB')):
        if value >= size:
            return f'{value / size:.2f} {label}'
    return f'{value:.0f} B'

class History:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS usage(
                day TEXT, kind TEXT, network TEXT, app TEXT,
                down INTEGER NOT NULL, up INTEGER NOT NULL,
                PRIMARY KEY(day,kind,network,app));
            CREATE TABLE IF NOT EXISTS coverage(day TEXT PRIMARY KEY, seconds REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS usage_minute(
                minute INTEGER,kind TEXT,network TEXT,app TEXT,down INTEGER,up INTEGER,
                PRIMARY KEY(minute,kind,network,app));
            CREATE TABLE IF NOT EXISTS coverage_minute(minute INTEGER PRIMARY KEY,seconds REAL);
            CREATE TABLE IF NOT EXISTS history_meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS usage_legacy AS SELECT * FROM usage WHERE 0;
            CREATE TABLE IF NOT EXISTS coverage_legacy AS SELECT * FROM coverage WHERE 0;
        ''')
        with self.lock,self.db:
            if not self.db.execute("SELECT 1 FROM history_meta WHERE key='minute_started'").fetchone():
                # Preserve existing daily totals once; do not invent their time of day.
                self.db.execute('INSERT INTO usage_legacy SELECT * FROM usage')
                self.db.execute('INSERT INTO coverage_legacy SELECT * FROM coverage')
                self.db.execute('INSERT INTO history_meta VALUES(?,?)',('minute_started',datetime.now().isoformat()))
        self.minute_started=datetime.fromisoformat(self.db.execute("SELECT value FROM history_meta WHERE key='minute_started'").fetchone()[0])
        self.prune()

    def prune(self, today=None):
        cutoff = ((today or date.today()) - timedelta(days=RETENTION_DAYS-1)).isoformat()
        timestamp=int(datetime.combine(date.fromisoformat(cutoff),datetime.min.time()).timestamp())
        with self.lock, self.db:
            self.db.execute('DELETE FROM usage WHERE day < ?', (cutoff,))
            self.db.execute('DELETE FROM coverage WHERE day < ?', (cutoff,))
            self.db.execute('DELETE FROM usage_legacy WHERE day < ?', (cutoff,))
            self.db.execute('DELETE FROM coverage_legacy WHERE day < ?', (cutoff,))
            self.db.execute('DELETE FROM usage_minute WHERE minute < ?', (timestamp,))
            self.db.execute('DELETE FROM coverage_minute WHERE minute < ?', (timestamp,))

    def record(self, rows, seconds, started=None, ended=None):
        """Split intervals crossing local midnight; preserve every integer byte."""
        ended = ended or datetime.now()
        started = started or ended - timedelta(seconds=seconds)
        spans = []
        cursor = started
        while cursor.date() < ended.date():
            boundary = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time())
            spans.append((cursor.date().isoformat(), (boundary-cursor).total_seconds()))
            cursor = boundary
        spans.append((ended.date().isoformat(), max(0, (ended-cursor).total_seconds())))
        duration = sum(s for _, s in spans) or 1
        minute_spans=[]
        cursor=started
        while cursor < ended:
            boundary=min(cursor.replace(second=0,microsecond=0)+timedelta(minutes=1),ended)
            minute_spans.append((int(cursor.timestamp())//60*60,(boundary-cursor).total_seconds()))
            cursor=boundary
        if not minute_spans:minute_spans=[(int(ended.timestamp())//60*60,0)]
        with self.lock, self.db:
            for day, part in spans:
                self.db.execute('INSERT INTO coverage VALUES(?,?) ON CONFLICT(day) DO UPDATE SET seconds=seconds+excluded.seconds',
                                (day, seconds * part / duration))
            for minute,part in minute_spans:
                self.db.execute('INSERT INTO coverage_minute VALUES(?,?) ON CONFLICT(minute) DO UPDATE SET seconds=seconds+excluded.seconds',
                                (minute,seconds*part/duration))
            for kind, network, app, down, up in rows:
                if not down and not up:continue
                left_down, left_up = down, up
                for i, (day, part) in enumerate(spans):
                    d = left_down if i == len(spans)-1 else int(down * part / duration)
                    u = left_up if i == len(spans)-1 else int(up * part / duration)
                    left_down -= d
                    left_up -= u
                    self.db.execute('''INSERT INTO usage VALUES(?,?,?,?,?,?) ON CONFLICT(day,kind,network,app)
                        DO UPDATE SET down=down+excluded.down, up=up+excluded.up''', (day,kind,network,app,d,u))
                remaining_down,remaining_up=down,up
                for i,(minute,part) in enumerate(minute_spans):
                    d=remaining_down if i==len(minute_spans)-1 else int(down*part/duration)
                    u=remaining_up if i==len(minute_spans)-1 else int(up*part/duration)
                    remaining_down-=d;remaining_up-=u
                    self.db.execute('''INSERT INTO usage_minute VALUES(?,?,?,?,?,?)
                        ON CONFLICT(minute,kind,network,app) DO UPDATE SET down=down+excluded.down,up=up+excluded.up''',
                        (minute,kind,network,app,d,u))
        self.prune(ended.date())

    def query(self, start, end, kind='adapter', group='network', network=None):
        if isinstance(start,datetime):return self.query_window(start,end,kind,group,network)
        start, end = date.fromisoformat(start), date.fromisoformat(end)
        if end < start:
            raise ValueError('End date must be on or after start date.')
        if group not in ('network', 'app', 'day') or kind not in ('adapter', 'app'):
            raise ValueError('Invalid history query.')
        with self.lock:
            network_filter=' AND network=?' if network else ''
            parameters=(start.isoformat(),end.isoformat(),kind)+(network,) if network else (start.isoformat(),end.isoformat(),kind)
            return self.db.execute(f'''SELECT {group},SUM(down),SUM(up) FROM usage
                WHERE day BETWEEN ? AND ? AND kind=? {network_filter} GROUP BY {group} ORDER BY SUM(down)+SUM(up) DESC''',
                parameters).fetchall()

    def monitored(self, start, end):
        if isinstance(start,datetime):
            if end<=start:return 0
            with self.lock:
                seconds=self.db.execute('SELECT COALESCE(SUM(seconds),0) FROM coverage_minute WHERE minute>=? AND minute<?',
                    (int(start.timestamp())//60*60,end.timestamp())).fetchone()[0]
                for day,value in self.db.execute('SELECT day,seconds FROM coverage_legacy'):
                    if self.legacy_in_window(day,start,end):seconds+=value
                return seconds
        with self.lock:
            return self.db.execute('SELECT COALESCE(SUM(seconds),0) FROM coverage WHERE day BETWEEN ? AND ?', (start,end)).fetchone()[0]

    def legacy_in_window(self,day,start,end):
        lower=datetime.combine(date.fromisoformat(day),datetime.min.time())
        upper=min(lower+timedelta(days=1),self.minute_started)
        return lower<=upper and start<=lower and end>=upper

    def query_window(self,start,end,kind='adapter',group='network',network=None):
        if end<start:raise ValueError('End time must be on or after start time.')
        if end==start:return []
        if group not in ('network','app','day') or kind not in ('adapter','app'):raise ValueError('Invalid history query.')
        expression="strftime('%Y-%m-%d',minute,'unixepoch','localtime')" if group=='day' else group
        clause=' AND network=?' if network else ''
        parameters=(int(start.timestamp())//60*60,end.timestamp(),kind)+((network,) if network else ())
        totals={}
        with self.lock:
            for label,down,up in self.db.execute(f'''SELECT {expression},SUM(down),SUM(up) FROM usage_minute
                WHERE minute>=? AND minute<? AND kind=? {clause} GROUP BY {expression}''',parameters):
                totals[label]=[down,up]
            for day,row_kind,row_network,app,down,up in self.db.execute('SELECT * FROM usage_legacy WHERE kind=?',(kind,)):
                if network and network!=row_network:continue
                if not self.legacy_in_window(day,start,end):continue
                label=day if group=='day' else app if group=='app' else row_network
                value=totals.setdefault(label,[0,0]);value[0]+=down;value[1]+=up
        return sorted(((name,*value) for name,value in totals.items()),key=lambda row:row[1]+row[2],reverse=True)

    def precision_note(self,start,end):
        note='Rolling cutoffs use one-minute buckets; recent records flush about every five seconds.'
        with self.lock:
            for (day,) in self.db.execute('SELECT DISTINCT day FROM usage_legacy'):
                lower=datetime.combine(date.fromisoformat(day),datetime.min.time())
                upper=min(lower+timedelta(days=1),self.minute_started)
                if lower<end and upper>start and not self.legacy_in_window(day,start,end):
                    return note+' A partial older day has unknown timing and is excluded.'
        return note

    def export(self, path, start, end, kind, group, network=None):
        rows = self.query(start,end,kind,group,network)
        with open(path,'w',newline='',encoding='utf-8-sig') as output:
            writer = csv.writer(output)
            writer.writerow([group,'download_bytes','upload_bytes'])
            for name, down, up in rows:
                # Prevent spreadsheet formula execution from SSIDs/process names.
                writer.writerow(["'"+name if name[:1] in '=+-@' else name,down,up])

    def close(self):
        with self.lock:
            self.db.close()
