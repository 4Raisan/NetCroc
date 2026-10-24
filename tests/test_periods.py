"""Rolling/month windows, minute accounting and non-destructive daily-history migration."""
from datetime import date,datetime,timedelta
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.history import History,PERIODS,period_bounds

class PeriodTests(unittest.TestCase):
    def test_only_three_periods(self):
        self.assertEqual(PERIODS,('Last 30 days','Last month','This month'))
        with self.assertRaises(ValueError):period_bounds('50 days')

    def test_rolling_preserves_current_time(self):
        now=datetime(2026,10,25,15,42,12)
        start,end=period_bounds('Last 30 days',now)
        self.assertEqual(start,datetime(2026,9,25,15,42,12));self.assertEqual(end,now)
        self.assertEqual(end-start,timedelta(days=30))

    def test_previous_month_excludes_current_month(self):
        self.assertEqual(period_bounds('Last month',datetime(2026,10,25,15)),(datetime(2026,9,1),datetime(2026,10,1)))

    def test_this_month_ends_now(self):
        now=datetime(2026,10,25,15,42)
        self.assertEqual(period_bounds('This month',now),(datetime(2026,10,1),now))

    def test_january_and_leap_february(self):
        self.assertEqual(period_bounds('Last month',datetime(2026,1,1)),(datetime(2025,12,1),datetime(2026,1,1)))
        start,end=period_bounds('Last month',datetime(2024,3,31))
        self.assertEqual((end-start).days,29)

    def test_two_31_day_months_are_retained(self):
        history=History(':memory:')
        history.db.execute('INSERT INTO usage VALUES(?,?,?,?,?,?)',('2026-07-01','adapter','wifi','',100,20))
        history.db.execute('INSERT INTO usage VALUES(?,?,?,?,?,?)',('2026-06-30','adapter','wifi','',200,30))
        history.db.commit();history.prune(date(2026,8,31))
        self.assertEqual(history.query('2026-01-01','2026-08-31'),[('wifi',100,20)]);history.close()

    def test_minute_boundary_preserves_every_byte(self):
        history=History(':memory:');end=datetime.now().replace(second=1,microsecond=0);start=end-timedelta(seconds=2)
        history.record([('app','wifi','browser',101,51)],2,start,end)
        records=history.db.execute('SELECT SUM(down),SUM(up),COUNT(*) FROM usage_minute').fetchone()
        self.assertEqual(records,(101,51,2))
        self.assertEqual(history.query(start-timedelta(minutes=1),end+timedelta(minutes=1),'app','app'),[('browser',101,51)])
        self.assertEqual(history.monitored(start-timedelta(minutes=1),end+timedelta(minutes=1)),2)
        history.close()

    def test_rolling_excludes_older_data_on_same_date(self):
        history=History(':memory:');end=datetime.now().replace(second=0,microsecond=0);start=end-timedelta(days=30)
        for moment,amount in ((start-timedelta(minutes=1),999),(start,100),(end-timedelta(minutes=1),200),(end,888)):
            history.db.execute('INSERT INTO usage_minute VALUES(?,?,?,?,?,?)',(int(moment.timestamp()),'app','wifi','browser',amount,0))
        history.db.commit()
        self.assertEqual(history.query(start,end,'app','app'),[('browser',300,0)]);history.close()

    def test_empty_window_does_not_include_current_minute(self):
        history=History(':memory:');now=datetime.now()
        history.record([('adapter','wifi','',100,20)],1,now-timedelta(seconds=1),now)
        self.assertEqual(history.query(now,now),[]);self.assertEqual(history.monitored(now,now),0);history.close()

    def make_old_database(self,path):
        db=sqlite3.connect(path)
        db.executescript('CREATE TABLE usage(day TEXT,kind TEXT,network TEXT,app TEXT,down INTEGER,up INTEGER,PRIMARY KEY(day,kind,network,app)); CREATE TABLE coverage(day TEXT PRIMARY KEY,seconds REAL);')
        day=(date.today()-timedelta(days=1)).isoformat()
        db.execute('INSERT INTO usage VALUES(?,?,?,?,?,?)',(day,'app','wifi','browser',1000,200))
        db.execute('INSERT INTO coverage VALUES(?,?)',(day,60));db.commit();db.close()

    def test_old_daily_history_migrates_once_without_double_count(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'usage.db';self.make_old_database(path)
            for _ in range(2):
                history=History(path);now=datetime.now()
                self.assertEqual(history.query(now-timedelta(days=30),now,'app','app'),[('browser',1000,200)])
                self.assertEqual(history.monitored(now-timedelta(days=30),now),60);history.close()

    def test_partial_legacy_day_is_unknown_not_estimated(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'usage.db';self.make_old_database(path);history=History(path)
            yesterday=datetime.combine(date.today()-timedelta(days=1),datetime.min.time())
            start=yesterday+timedelta(hours=12);end=datetime.now()
            self.assertEqual(history.query(start,end,'app','app'),[])
            self.assertIn('unknown timing',history.precision_note(start,end));history.close()

    def test_csv_obeys_selected_window_and_network(self):
        with tempfile.TemporaryDirectory() as folder:
            history=History(':memory:');now=datetime.now()
            history.record([('app','wifi','browser',100,20),('app','other','browser',999,99)],1,now-timedelta(seconds=1),now)
            output=Path(folder)/'usage.csv';history.export(output,now-timedelta(days=30),now,'app','app','wifi')
            self.assertIn('browser,100,20',output.read_text(encoding='utf-8-sig'));history.close()

if __name__=='__main__':unittest.main()
