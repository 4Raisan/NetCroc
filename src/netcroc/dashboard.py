"""NetCroc local dashboard. Every network-changing action is explicit."""
from collections import defaultdict,deque
import ctypes
from datetime import date,datetime,timedelta
import os
from pathlib import Path
import queue
import socket
import threading
import time
import tkinter as tk
import webbrowser
import urllib.request
from tkinter import ttk,messagebox,filedialog
import psutil
from .platforms import admin
from .history import History,speed,volume,PERIODS,period_bounds
from .traffic import Rates,Traffic,process_identity
from .wifi import Wifi
from . import dns,research,vpn
from .app_names import aggregate,identity,UNKNOWN
from .tool_ui import actions,help_for,StatusLine

def table(parent,columns,widths=None):
    frame=ttk.Frame(parent); frame.pack(fill='both',expand=True,pady=8)
    tree=ttk.Treeview(frame,columns=columns,show='headings',height=6)
    for index,col in enumerate(columns):
        tree.heading(col,text=col); tree.column(col,width=widths[index] if widths else 150,minwidth=60,stretch=True)
    scroll=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    horizontal=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
    tree.configure(xscrollcommand=horizontal.set)
    horizontal.pack(side='bottom',fill='x')
    weights=widths or [150]*len(columns)
    def fit(event):
        available=max(1,event.width-20);total=sum(weights)
        for col,weight in zip(columns,weights):tree.column(col,width=max(60,int(available*weight/total)))
    frame.bind('<Configure>',fit)
    scroll.pack(side='right',fill='y'); tree.pack(fill='both',expand=True)
    return tree

def info_dialog(root,title,*messages):
    dialog=tk.Toplevel(root);dialog.title(title);dialog.geometry('620x360')
    from tkinter.scrolledtext import ScrolledText
    body=ScrolledText(dialog,wrap='word',font=('Segoe UI',10),padx=16,pady=16,bd=0)
    body.pack(fill='both',expand=True,padx=12,pady=12)
    body.insert('1.0','\n\n'.join(v.get() if hasattr(v,'get') else str(v) for v in messages));body.configure(state='disabled')
    ttk.Button(dialog,text='Got it',command=dialog.destroy).pack(pady=(0,12))


def rows(tree,items):
    # Reuse existing rows so live refreshes do not flicker or discard selection.
    snapshot=tuple(tuple(map(str,item)) for item in items)
    if snapshot == getattr(tree,'_netcroc_rows_cache',None):return
    tree._netcroc_rows_cache=snapshot
    existing=tree.get_children(); buckets=defaultdict(deque)
    for iid in existing:
        values=tree.item(iid,'values')
        if values:buckets[str(values[0])].append(iid)
    if not getattr(tree,'_netcroc_stripes',False):
        tree.tag_configure('alternate',background='#f6f9f7');tree._netcroc_stripes=True
    used=set()
    for index,item in enumerate(items):
        key=str(item[0]);iid=buckets[key].popleft() if buckets[key] else None
        tags=('alternate',) if index%2 else ()
        if iid is None:iid=tree.insert('','end',values=item,tags=tags)
        else:
            if tuple(map(str,tree.item(iid,'values'))) != tuple(map(str,item)) or tuple(tree.item(iid,'tags')) != tags:
                tree.item(iid,values=item,tags=tags)
            if tree.index(iid)!=index:tree.move(iid,'',index)
        used.add(iid)
    for iid in existing:
        if iid not in used:tree.delete(iid)


class Dashboard:
    def __init__(self,app,notebook,diagnostic=False):
        self.app=app; self.root=app.root; self.diagnostic=diagnostic; self.notebook=notebook
        self.events=queue.Queue(); self.stop=threading.Event(); self.points=deque(maxlen=90)
        self.last_live=None; self.profiles=[]; self.adapter_info=[]; self.dns_results=[]; self.busy=False
        from . import core
        self.folder=core.data_folder()
        if not diagnostic: self.folder.mkdir(parents=True,exist_ok=True)
        self.history=History(':memory:' if diagnostic else self.folder/'usage.sqlite3')
        self.dns=dns.DnsManager(self.folder/'dns-restore.json')
        self.traffic=None; self.capture_retry=threading.Event()
        self.tab_live=self.tab(notebook,'Live traffic')
        self.tab_history=self.tab(notebook,'Usage history')
        self.tab_dns=self.tab(notebook,'DNS')
        self.tab_wifi=self.tab(notebook,'Saved Wi-Fi')
        self.tab_research=self.tab(notebook,'URL study')
        self.tab_vpn=self.tab(notebook,'VPN')
        self.vpn_store=vpn.ProfileStore(self.folder/'wireguard'/'profiles')
        self.vpn_profiles=[]
        self.vpn_baseline=None
        self.build_live(); self.build_history(); self.build_dns(); self.build_wifi(); self.build_research(); self.build_vpn()
        from .ssh_ui import SSHTab
        self.ssh_tab=SSHTab(app,notebook,self.folder,diagnostic=diagnostic)
        from .vless_ui import VlessTab
        self.vless_tab=VlessTab(app,notebook,self.folder,diagnostic=diagnostic)
        self.root.after(250,self.poll)
        self.root.after(30000,self.refresh_active_history)
        if not diagnostic:
            self.monitor_thread=threading.Thread(target=self.monitor,daemon=True); self.monitor_thread.start()
            self.refresh_wifi()
            self.root.after(1500,self.refresh_dns)
            self.root.after(2200,self.refresh_vpn)

    def tab(self,book,name):
        tab=ttk.Frame(book,padding=16); book.add(tab,text=name); return tab

    def build_live(self):
        tab=self.tab_live
        ttk.Label(tab,text='Live traffic',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(tab,text='Your connection, right now.',style='Muted.TLabel').pack(anchor='w',pady=(4,10))
        line=ttk.Frame(tab); line.pack(fill='x',pady=8)
        self.adapter=tk.StringVar(value='Auto (active adapter)')
        self.adapter_box=ttk.Combobox(line,textvariable=self.adapter,state='readonly',width=25,values=['Auto (active adapter)'])
        self.adapter_box.pack(side='left')
        self.live_status=tk.StringVar(value='Starting local adapter monitoring…')
        ttk.Label(tab,textvariable=self.live_status).pack(anchor='w')
        self.down=tk.StringVar(value='↓ 0.00 KB/s'); self.up=tk.StringVar(value='↑ 0.00 KB/s')
        ttk.Label(line,textvariable=self.down,font=('Segoe UI',18,'bold')).pack(side='left',padx=20)
        ttk.Label(line,textvariable=self.up,font=('Segoe UI',18,'bold')).pack(side='left')
        self.graph=tk.Canvas(tab,height=150,bg='#ffffff',highlightthickness=0); self.graph.pack(fill='x',pady=6)
        ttk.Label(tab,text='Download / upload · last 90 samples',style='Muted.TLabel').pack(anchor='w',pady=(0,4))
        self.capture_status=tk.StringVar(value='Per-app monitoring initializes below.')
        self.capture_summary=tk.StringVar(value='App tracking is starting…')
        ttk.Label(tab,textvariable=self.capture_summary,style='Muted.TLabel',wraplength=780).pack(anchor='w',pady=(4,0))
        ttk.Button(tab,text='Retry app tracking',command=self.app.enable_app_tracking).pack(anchor='w',pady=4)
        ttk.Button(tab,text='Tracking details',command=lambda:info_dialog(self.root,'About live traffic',self.capture_status,'Speeds use bytes per second (1024-based). Adapter totals include local traffic. App capture counts Internet TCP/UDP; a VPN may attribute traffic to its tunnel app.')).pack(anchor='e')
        if os.name=='nt' and not admin():
            ttk.Button(tab,text='Enable app tracking',command=self.app.enable_app_tracking).pack(anchor='w')
        self.apps=table(tab,('Application','Download /s','Upload /s','Observed total'),[450,150,150,150])


    def build_history(self):
        tab=self.tab_history
        ttk.Label(tab,text='Usage',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(tab,text='See where your data goes.').pack(anchor='w',pady=5)
        line=ttk.Frame(tab); line.pack(fill='x')
        self.history_period=tk.StringVar(value='Last 30 days')
        for period in PERIODS:
            ttk.Radiobutton(line,style='Segment.TRadiobutton',text=period,variable=self.history_period,value=period,command=self.refresh_history).pack(side='left',padx=4)
        self.group=tk.StringVar(value='Wi-Fi / adapters')
        group_box=ttk.Combobox(line,textvariable=self.group,state='readonly',values=['Wi-Fi / adapters','Applications','Daily totals'],width=19)
        group_box.pack(side='left',padx=8)
        group_box.bind('<<ComboboxSelected>>',lambda _event:self.refresh_history())
        ttk.Button(line,text='Export',command=self.export_history).pack(side='right')
        filter_line=ttk.Frame(tab);self.app_filters=filter_line
        ttk.Label(filter_line,text='Show apps').pack(side='left',padx=(0,8))
        self.history_minimum=tk.IntVar(value=self.app.desktop.data['usage_minimum_mb'])
        for text,value in [('All',0),('1 MB+',1),('5 MB+',5)]:
            ttk.Radiobutton(filter_line,text=text,variable=self.history_minimum,value=value,command=self.refresh_history).pack(side='left',padx=6)
        ttk.Button(filter_line,text='App details',command=self.history_details).pack(side='right')
        self.history_display=[];self.history_chart_rows=[]
        self.history_range=tk.StringVar()
        self.history_range_label=ttk.Label(tab,textvariable=self.history_range,style='Muted.TLabel')
        line=ttk.Frame(tab);line.pack(fill='x',pady=5)
        ttk.Label(line,text='Network').pack(side='left',padx=4)
        self.history_network=tk.StringVar(value='All networks')
        self.history_network_box=ttk.Combobox(line,textvariable=self.history_network,values=['All networks'],state='readonly',width=35)
        self.history_network_box.pack(side='left')
        self.history_network_box.bind('<<ComboboxSelected>>',lambda _event:self.refresh_history())
        ttk.Button(line,text='About these numbers',command=lambda:info_dialog(self.root,'Usage details',self.history_range,self.history_status,self.history_precision)).pack(side='right')
        self.history_status=tk.StringVar(value='History starts with this installation.')
        self.usage_down=tk.StringVar(value='—');self.usage_up=tk.StringVar(value='—');self.usage_coverage=tk.StringVar(value='—')
        cards=ttk.Frame(tab);cards.pack(fill='x',pady=(8,6))
        for col,(label,value) in enumerate([('↓ Downloaded',self.usage_down),('↑ Uploaded',self.usage_up),('Recorded',self.usage_coverage)]):
            cards.columnconfigure(col,weight=1,uniform='summary')
            card=ttk.Frame(cards,style='Card.TFrame',padding=(14,10));card.grid(row=0,column=col,sticky='nsew',padx=(0,8) if col<2 else 0)
            ttk.Label(card,text=label,style='Card.TLabel',font=('Segoe UI',9)).pack(anchor='w')
            ttk.Label(card,textvariable=value,style='Card.TLabel',font=('Segoe UI',17,'bold')).pack(anchor='w',pady=(4,0))
        self.history_summary_cards=cards
        self.history_body=ttk.Frame(tab);self.history_body.pack(fill='both',expand=True)
        self.history_table=table(self.history_body,('Network / application / date','Downloaded','Uploaded','Total'),[480,150,150,150])
        self.bars=tk.Canvas(self.history_body,height=150,bg='#ffffff',highlightthickness=0); self.bars.pack(side='bottom',fill='x',before=self.history_table.master)
        self.history_empty=ttk.Frame(self.history_body,padding=28)
        self.history_empty_title=tk.StringVar()
        self.history_empty_message=tk.StringVar()
        ttk.Label(self.history_empty,textvariable=self.history_empty_title,font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(8,10))
        ttk.Label(self.history_empty,textvariable=self.history_empty_message,wraplength=650).pack(anchor='w',pady=(0,16))
        self.history_enable=ttk.Button(self.history_empty,text='Retry app tracking',command=self.app.enable_app_tracking)
        ttk.Button(self.history_empty,text='See network totals',command=self.show_network_history).pack(anchor='w',pady=8)
        self.history_precision=tk.StringVar(value='Missing history is unknown, not zero usage.')
        self.history_footer=ttk.Label(tab,text='Only usage recorded while NetCroc is running appears here. Recorded data is kept for 62 days; older days are removed automatically.',style='Muted.TLabel',wraplength=740)
        self.history_footer.pack(side='bottom',fill='x',pady=4,before=self.history_body)
        self.history_body.bind('<Configure>',self.resize_history)
        self.bars.bind('<Configure>',lambda _event:self.draw_history_bars())

    def show_network_history(self):
        self.group.set('Wi-Fi / adapters');self.refresh_history()

    def period(self,period):
        self.history_period.set(period);self.refresh_history()

    def refresh_active_history(self):
        if self.stop.is_set():return
        if self.notebook.select()==str(self.tab_history):self.refresh_history()
        self.root.after(30000,self.refresh_active_history)

    def history_args(self):
        start,end=period_bounds(self.history_period.get())
        mode=self.group.get()
        return start,end,'app' if mode=='Applications' else 'adapter', 'app' if mode=='Applications' else 'day' if mode=='Daily totals' else 'network',None if self.history_network.get()=='All networks' else self.history_network.get()

    def refresh_history(self):
        try:
            start,end,kind,group,network=self.history_args(); result=self.history.query(start,end,kind,group,network)
            if kind=='app':self.app_filters.pack(fill='x',pady=4,before=self.history_summary_cards)
            else:self.app_filters.pack_forget()
            self.history_range.set(f'{start:%d %b %Y %H:%M} → {end:%d %b %Y %H:%M}'+(' (end exclusive)' if self.history_period.get()=='Last month' else ' (now)'))
            self.history_precision.set(self.history.precision_note(start,end)+' Missing history is unknown, not zero usage.')
            networks=self.history.query(start,end,'adapter','network')
            self.history_network_box.configure(values=['All networks']+[name for name,_,_ in networks])
            raw_result=result
            minimum=self.history_minimum.get()*1024**2 if kind=='app' else 0
            self.app.desktop.update({'usage_minimum_mb':self.history_minimum.get()})
            if kind=='app':
                self.history_display=aggregate(result,minimum)
                result=[(v.label,v.down,v.up) for v in self.history_display]
            else:self.history_display=[]
            self.history_chart_rows=result
            self.history_table.heading('Network / application / date',text='Application' if kind=='app' else 'Network / date')
            rows(self.history_table,[(n,volume(d),volume(u),volume(d+u)) for n,d,u in result])
            seconds=self.history.monitored(start,end)
            total_down=sum(d for _,d,_ in raw_result); total_up=sum(u for _,_,u in raw_result)
            self.usage_down.set(volume(total_down));self.usage_up.set(volume(total_up));self.usage_coverage.set(f'{seconds/3600:.1f} hours')
            self.history_status.set(f'Download {volume(total_down)} · Upload {volume(total_up)} · Monitoring coverage {seconds/3600:.2f} hours. '+
                (f'Showing {len(result)} app groups'+(f' of at least {self.history_minimum.get()} MB.' if minimum else '.') if kind=='app' else 'Adapter totals include LAN. Combining virtual/physical adapters can double-count traffic.'))
            if not raw_result:self.history_status.set('No recorded data in this period.')
            elif not result:self.history_status.set('Recorded usage exists, but no apps reach this filter. Choose All or a lower minimum.')
            self.history_empty.pack_forget()
            if result:
                self.history_table.master.pack(fill='both',expand=True,pady=8)
                self.bars.pack(side='bottom',fill='x',before=self.history_table.master)
            else:
                self.history_table.master.pack_forget();self.bars.pack_forget()
                self.history_empty.pack(fill='both',expand=True)
                if raw_result:
                    self.history_empty_title.set('No apps match this minimum')
                    self.history_empty_message.set('Choose All or 1 MB+ to see smaller usage. The filter does not delete or change any records.')
                    self.history_enable.pack_forget()
                elif kind=='app':
                    self.history_empty_title.set('App usage has not been recorded yet')
                    needs_admin=os.name=='nt' and not admin()
                    self.history_empty_message.set('Windows approval is needed to track each app. Enable tracking to record usage from now on. Earlier app usage cannot be recovered.' if needs_admin else 'Only traffic captured while app tracking is active appears here. Check Live traffic for capture status. Earlier app usage cannot be recovered.')
                    self.history_enable.configure(text='Enable app tracking' if needs_admin else 'Retry app tracking',command=self.app.enable_app_tracking)
                    self.history_enable.pack(anchor='w',before=self.history_empty.winfo_children()[-1])
                else:
                    self.history_empty_title.set('No saved usage for this period')
                    self.history_empty_message.set('NetCroc records usage while it is running. Choose another period or leave it open to collect new data. Missing history is not zero usage.')
                    self.history_enable.pack_forget()
            self.draw_history_bars()
        except (ValueError,OSError) as error: messagebox.showerror('History',str(error))

    def resize_history(self,event):
        self.bars.configure(height=min(180,max(96,event.height//3)))

    def draw_history_bars(self):
        self.bars.delete('all');items=getattr(self,'history_chart_rows',[])[:6]
        width=max(260,self.bars.winfo_width());height=max(80,self.bars.winfo_height())
        label_width=min(230,max(100,int(width*.28)));maximum=max([d+u for _,d,u in items] or [1]) or 1
        step=min(28,max(13,(height-14)//max(1,len(items))))
        from tkinter import font
        measure=font.Font(font=('Segoe UI',9))
        for index,(name,down,up) in enumerate(items):
            label=name
            while label and measure.measure(label)>label_width-16:label=label[:-1]
            if label!=name:label=label[:-1]+'…'
            y=7+index*step;length=max(0,width-label_width-110)*(down+up)/maximum
            self.bars.create_text(8,y+step/2,text=label,fill='#294638',anchor='w',font=('Segoe UI',9))
            self.bars.create_rectangle(label_width,y+2,label_width+length,y+step-2,fill='#20a779',outline='')
            self.bars.create_text(label_width+length+6,y+step/2,text=volume(down+up),fill='#294638',anchor='w',font=('Segoe UI',8))

    def history_details(self):
        selected=self.history_table.selection()
        if not selected:return
        index=self.history_table.index(selected[0])
        if self.group.get()=='Applications' and index<len(self.history_display):
            item=self.history_display[index];title=item.label;text='Recorded file locations / identities:\n\n'+'\n'.join(item.sources)
            if item.label==UNKNOWN:text+='\n\nThese process identities were unavailable at capture time. Old PIDs are not reassigned to current apps.'
        else:
            title='Usage details';text=str(self.history_table.item(selected[0],'values')[0])
        dialog=tk.Toplevel(self.root);dialog.title(title);dialog.geometry('720x320')
        from tkinter.scrolledtext import ScrolledText
        body=ScrolledText(dialog,wrap='word',font=('Segoe UI',10));body.pack(fill='both',expand=True,padx=12,pady=12)
        body.insert('1.0',text);body.configure(state='disabled')
        ttk.Button(dialog,text='Copy details',command=lambda:(self.root.clipboard_clear(),self.root.clipboard_append(text))).pack(pady=(0,12))

    def export_history(self):
        try:
            args=self.history_args()
            path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='NetCroc-usage.csv')
            if path:self.history.export(path,*args)
        except (ValueError,OSError) as error: messagebox.showerror('Export',str(error))

    def build_dns(self):
        tab=self.tab_dns
        ttk.Label(tab,text='DNS',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(tab,text='1. Test your connection   2. Compare results   3. Apply only if useful',style='Muted.TLabel').pack(anchor='w',pady=(6,14))
        self.dns_status=tk.StringVar(value='Loading connection…')
        ttk.Label(tab,textvariable=self.dns_status,wraplength=780).pack(anchor='w',pady=6)
        line=ttk.Frame(tab);line.pack(fill='x')
        self.dns_adapter=tk.StringVar()
        self.dns_box=ttk.Combobox(line,textvariable=self.dns_adapter,state='readonly',width=30);self.dns_box.pack(side='left')
        self.dns_table=table(tab,('Resolver','Servers','Median lookup','Failures'),[180,330,180,130])
        actions(tab,[('Test DNS',self.test_dns),('Apply selected',self.apply_dns)],[('Refresh connections',self.refresh_dns),('Restore original DNS',self.restore_dns),
            ('How DNS testing works',help_for(self.root,'DNS','Testing changes nothing. A faster resolver may help website lookups; it does not increase download bandwidth. Apply changes IPv4 DNS and requires confirmation. Original settings are saved and a watchdog can roll back an uncommitted change. Use Restore original DNS to undo it.'))])
        ttk.Label(tab,text='Testing leaves your settings unchanged.',style='Muted.TLabel').pack(anchor='w',pady=6)

    def task(self,kind,fn):
        if self.busy:
            messagebox.showinfo('Working','Wait for the current network operation to finish.'); return
        self.busy=True
        def work():
            try: self.events.put((kind,fn()))
            except Exception as error: self.events.put(('error',str(error)))
        threading.Thread(target=work,daemon=True).start()

    def refresh_dns(self):
        if self.busy:self.root.after(1000,self.refresh_dns)
        else:self.task('adapters',dns.adapters)

    def selected_adapter(self):
        index=self.dns_box.current()
        if index<0 or index>=len(self.adapter_info): raise ValueError('Choose a connected adapter first.')
        return self.adapter_info[index]

    def test_dns(self):
        try:
            adapter=self.selected_adapter(); self.dns_status.set('Testing repeated DNS lookups; current settings remain unchanged…')
            self.task('dns',lambda:dns.benchmark(adapter['servers']))
        except ValueError as error:messagebox.showerror('DNS',str(error))

    def apply_dns(self):
        try:
            if os.name=='nt' and not admin():raise PermissionError('Close NetCroc and use Run as administrator when you are at the PC. No settings were changed.')
            item=self.dns_table.selection()
            if not item:raise ValueError('Test DNS, then select a resolver.')
            name=self.dns_table.item(item[0],'values')[0]
            result=next(r for r in self.dns_results if r['name']==name)
            if result['failures']:raise ValueError('Choose a resolver with no test failures.')
            adapter=self.selected_adapter()
            if not messagebox.askyesno('Apply DNS',f"Change IPv4 DNS on {adapter['name']} to {', '.join(result['servers'])}?\n\nThis can briefly affect lookups. Postpone if this connection is needed for remote access."):return
            self.dns_status.set('Checking DNS, saving the original settings and starting rollback protection…')
            def work():self.dns.apply(adapter,result['servers']);return 'DNS applied and validated. Original settings can be restored.'
            self.task('message',work)
        except (ValueError,PermissionError) as error:messagebox.showerror('DNS',str(error))

    def restore_dns(self):
        if os.name=='nt' and not admin():
            messagebox.showinfo('Administrator required','Run NetCroc as administrator to restore DNS.');return
        if messagebox.askyesno('Restore DNS','Restore the saved original adapter DNS settings?'):
            def work():self.dns.restore();return 'Original DNS settings restored.'
            self.task('message',work)

    def build_wifi(self):
        tab=self.tab_wifi
        ttk.Label(tab,text='Wi-Fi',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(tab,text='Your saved networks and passwords.').pack(anchor='w',pady=6)
        self.wifi_status=tk.StringVar(value='Loading saved networks…')
        ttk.Label(tab,textvariable=self.wifi_status,wraplength=750).pack(anchor='w',pady=6)
        self.wifi_search=tk.StringVar()
        search=ttk.Frame(tab);search.pack(fill='x',pady=5)
        ttk.Label(search,text='Find a network').pack(side='left',padx=(0,8))
        ttk.Entry(search,textvariable=self.wifi_search).pack(side='left',fill='x',expand=True)
        self.wifi_search.trace_add('write',lambda *_:self.render_wifi())
        self.visible_profiles=[]
        self.wifi_table=table(tab,('Network','Status','Password','Copy'),[390,120,230,65])
        self.wifi_table.bind('<ButtonRelease-1>',self.copy_wifi_cell)
        line=ttk.Frame(tab);line.pack(fill='x')
        ttk.Button(line,text='Connect',command=lambda:self.wifi_action('connect')).pack(side='left')
        ttk.Button(line,text='Refresh',command=self.refresh_wifi).pack(side='left',padx=6)
        if os.name!='nt':ttk.Button(line,text='Show password',command=self.reveal_wifi).pack(side='left',padx=6)
        ttk.Button(line,text='Details',command=self.wifi_details).pack(side='right')
        ttk.Button(line,text='Forget',command=lambda:self.wifi_action('forget')).pack(side='right',padx=6)
        ttk.Label(tab,text='Select a network to connect. Your current connection is protected from Forget.',wraplength=750).pack(anchor='w',pady=10)

    def render_wifi(self):
        search=self.wifi_search.get().strip().casefold()
        self.visible_profiles=sorted((p for p in self.profiles if search in p['profile'].casefold()),key=lambda p:(not p['connected'],p['profile'].casefold()))
        rows(self.wifi_table,[(p['profile'],'Connected' if p['connected'] else 'Saved',p['password'],'Copy') for p in self.visible_profiles])
        connected=next((p['profile'] for p in self.profiles if p['connected']),None)
        self.wifi_status.set(('Connected to '+connected+' · ' if connected else '')+f'{len(self.visible_profiles)} saved networks'+(' shown' if search else ''))

    def selected_wifi(self):
        selected=self.wifi_table.selection()
        return self.visible_profiles[self.wifi_table.index(selected[0])] if selected else None

    def copy_wifi_cell(self,event):
        if self.wifi_table.identify_column(event.x) != '#4':return
        row=self.wifi_table.identify_row(event.y)
        if not row:return
        index=self.wifi_table.index(row)
        if index>=len(self.visible_profiles):return
        password=self.visible_profiles[index]['password']
        if not password or password in ('Windows permission required','No readable saved password','Open network'):
            self.wifi_status.set('This network has no readable saved password to copy.');return
        self.root.clipboard_clear();self.root.clipboard_append(password)
        self.wifi_status.set('Password copied to clipboard.')

    def wifi_details(self):
        item=self.selected_wifi()
        if item:
            messagebox.showinfo('Network details','Network: '+item['profile']+'\nSecurity: '+str(item['auth'])+'\nAdapter: '+str(item['interface'].description))

    def reveal_wifi(self):
        item=self.selected_wifi()
        if not item:return
        wifi=Wifi()
        try:messagebox.showinfo('Saved Wi-Fi password',wifi.password(item))
        except OSError:messagebox.showerror('Saved Wi-Fi password','The OS denied password access or no stored password was found.')
        finally:wifi.close()

    def refresh_wifi(self):
        def work():
            wifi=Wifi()
            try:return wifi.profiles()
            finally:wifi.close()
        # Startup needs two independent reads; wait until the task slot is available.
        if self.busy:self.root.after(1000,self.refresh_wifi)
        else:self.task('wifi',work)

    def wifi_action(self,action):
        item=self.selected_wifi()
        if not item:return
        if not messagebox.askyesno('Wi-Fi',f"{action.title()} profile {item['profile']}?"+ ('\nThis may disconnect your current connection.' if action=='connect' else '')):return
        def work():
            wifi=Wifi()
            try:getattr(wifi,action)(item)
            finally:wifi.close()
            return 'Connection requested; Windows may need time to connect.' if action=='connect' else 'Saved Wi-Fi profile removed.'
        self.task('message',work)

    def build_research(self):
        tab=self.tab_research
        ttk.Label(tab,text='Website tests',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(tab,text='1. Test ISP websites   2. Pick a responsive result   3. Use it for connection checks',wraplength=950).pack(anchor='w',pady=8)
        ttk.Button(tab,text='Test websites (1–3 minutes)',command=lambda:self.task('research',research.study)).pack(anchor='w')
        self.research_status=tk.StringVar(value='Ready. Testing leaves your network settings unchanged.')
        ttk.Label(tab,textvariable=self.research_status,wraplength=950).pack(anchor='w',pady=8)
        self.research_table=table(tab,('ISP','Candidate URL','Successful checks','Median HEAD'),[110,500,170,150])
        ttk.Button(tab,text='Use selected URL for keep-alive',command=self.use_url).pack(anchor='w')
        ttk.Button(tab,text='How to read results',command=help_for(self.root,'Website tests','Results measure response times on this connection, not a guaranteed speed boost. A matching ISP hostname is not inherently faster. Failed/rate-limited endpoints are unsuitable. One check per second can use data and create 86,400 requests per day.')).pack(anchor='w',pady=6)

    def use_url(self):
        selected=self.research_table.selection()
        if selected:
            self.app.custom.set(self.research_table.item(selected[0],'values')[1])
            messagebox.showinfo('URL selected','URL copied to Keep-alive. Pause an active run before saving new settings.')

    def build_vpn(self):
        tab=self.tab_vpn
        ttk.Label(tab,text='WireGuard VPN',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(tab,text='1. Import your provider file   2. Select it   3. Connect',style='Muted.TLabel').pack(anchor='w',pady=(6,14))
        self.vpn_line=StatusLine(tab,'Import a .conf profile to begin.')
        self.vpn_status=self.vpn_line.var
        self.vpn_table=table(tab,('Profile','Server','Routes','Service','Handshake'),[170,240,130,120,140])
        self.vpn_table.bind('<<TreeviewSelect>>',lambda _event:self._update_vpn_buttons())
        extra=[('Refresh status',self.refresh_vpn),('Remove selected profile',lambda:self.vpn_action('remove')),('Check public IP',lambda:self.check_vpn_ip()),('Save baseline IP',lambda:self.check_vpn_ip(True)),('Install WireGuard',lambda:webbrowser.open(vpn.INSTALL_URL))]
        extra += [('Get profile: '+name,lambda url=url:webbrowser.open(url)) for name,plan,url in vpn.PROVIDERS]
        extra += [('How to use WireGuard',help_for(self.root,'WireGuard VPN','Use a .conf file from a provider and install WireGuard. NetCroc does not supply accounts or servers. Importing does not connect. Connecting changes system routes/DNS and may interrupt internet. Check handshake and public IP to verify connectivity. Closing NetCroc leaves this tunnel active; use Disconnect to stop it. Data charges still apply.'))]
        self.vpn_bar=actions(tab,[('Import profile',self.import_vpn),('Connect',lambda:self.vpn_action('connect')),('Disconnect',lambda:self.vpn_action('disconnect'))],extra)
        self.vpn_ip=tk.StringVar(value='Public IP not checked.')
        ttk.Label(tab,textvariable=self.vpn_ip,wraplength=780).pack(anchor='w',pady=6)
        ttk.Label(tab,text='Disconnect here to stop the VPN. Closing NetCroc leaves it running.',style='Muted.TLabel').pack(anchor='w',pady=6)
        self._vpn_empty(0);self._update_vpn_buttons()

    def _vpn_empty(self,count):
        self.vpn_table.configure(height=6 if count else 3)
        self.vpn_table.master.pack_configure(expand=bool(count))

    def _update_vpn_buttons(self):
        selection=self.vpn_table.selection()
        chosen=bool(selection)
        running=False
        if chosen:
            values=self.vpn_table.item(selection[0],'values')
            running=bool(values) and str(values[3]).lower()=='running'
        idle=not self.busy
        self.vpn_bar.set_enabled({'Connect':idle and chosen and not running,
                                  'Disconnect':idle and chosen and running,
                                  'Import profile':idle})
        if running:self.vpn_bar.set_primary('Disconnect')
        elif chosen:self.vpn_bar.set_primary('Connect')
        else:self.vpn_bar.set_primary('Import profile')

    def import_vpn(self):
        if self.busy:return
        path=filedialog.askopenfilename(title='Import your WireGuard profile',filetypes=[('WireGuard configuration','*.conf')])
        if path:
            self.vpn_line.busy('Encrypting and saving the profile…')
            self.task('vpn-import',lambda:self.vpn_store.import_file(path))

    def refresh_vpn(self):
        if self.stop.is_set():return
        if self.busy:
            self.root.after(500,self.refresh_vpn);return
        def check():
            profiles=self.vpn_store.profiles()
            return [(item,self.vpn_store.backend.status(vpn.tunnel_name(item['id']))) for item in profiles]
        if not self.busy:self.task('vpn',check)

    def selected_vpn(self):
        selection=self.vpn_table.selection()
        if not selection:raise ValueError('Choose an imported VPN profile first.')
        for item in self.vpn_profiles:
            if item['id']==selection[0]:return item
        raise ValueError('That profile is no longer saved. Refresh the list and choose again.')

    def vpn_action(self,action):
        if self.busy:return
        try:
            item=self.selected_vpn()
            if action=='connect' and self.ssh_tab.session and not self.ssh_tab.session.cancel.is_set():
                raise ValueError('Disconnect the SSH tunnel before connecting WireGuard.')
            if action=='connect' and self.vless_tab.session and not self.vless_tab.session.cancel.is_set():
                raise ValueError('Disconnect VLESS before connecting WireGuard.')
            if action in ('connect','disconnect'):self.vpn_store.backend.require_admin()
        except (ValueError,PermissionError) as error:
            messagebox.showerror('VPN',str(error));return
        text={'connect':'Connect this VPN? It can change routes and DNS for the PC and interrupt remote access.','disconnect':'Disconnect this VPN and return traffic to your normal connection?','remove':'Remove this saved profile from NetCroc? Your original imported file will remain.'}[action]
        if not messagebox.askyesno('VPN · '+item['label'],text):return
        self.vpn_line.busy({'connect':'Connecting the VPN tunnel…','disconnect':'Disconnecting the VPN tunnel…','remove':'Removing the saved profile…'}[action])
        def perform():
            getattr(self.vpn_store,action)(item['id'])
            return action
        self.task('vpn-action',perform)

    def check_vpn_ip(self,baseline=False):
        if self.busy:return
        self.vpn_line.busy('Saving the baseline public IP…' if baseline else 'Checking the public IP…')
        def check():
            import ipaddress
            with urllib.request.urlopen('https://api.ipify.org',timeout=8) as response:
                address=str(ipaddress.ip_address(response.read(128).decode('ascii').strip()))
            return address,baseline
        self.task('vpn-ip',check)

    def monitor(self):
        rates=Rates(); app_totals=defaultdict(lambda:[0,0]); wifi=None
        try:
            self.traffic=Traffic(); self.traffic.start()
        except Exception as error:
            self.events.put(('capture',f'Per-app capture unavailable: {type(error).__name__}. Adapter totals still work.'))
            self.traffic=None
        try:wifi=Wifi()
        except OSError:pass
        identities={}; address_map={}; wifi_names={}; last_refresh=0; previous_wall=datetime.now(); buffered=[]; covered=0; flush_at=time.monotonic()
        capture_started=time.monotonic();capture_bytes=0;fallback_attempted=False
        while not self.stop.is_set():
            try:
                if self.capture_retry.is_set():
                    self.capture_retry.clear()
                    if self.traffic:self.traffic.close()
                    try:
                        self.traffic=Traffic(system=fallback_attempted);self.traffic.start();capture_started=time.monotonic();capture_bytes=0
                        self.events.put(('capture',self.traffic.status))
                    except Exception as error:
                        self.traffic=None;self.events.put(('capture',f'Per-app capture unavailable: {type(error).__name__}. Adapter totals still work.'))
                now=time.monotonic(); wall=datetime.now()
                if now-last_refresh>=5:
                    last_refresh=now
                    stats=psutil.net_if_stats()
                    address_map={a.address.split('%')[0]:name for name,addresses in psutil.net_if_addrs().items() for a in addresses if a.family in (socket.AF_INET,socket.AF_INET6)}
                    if wifi:
                        wifi_names={}
                        for interface in wifi.interfaces():
                            profile=wifi.current(interface)
                            if profile:
                                # psutil AF_LINK MAC identity avoids localized adapter names.
                                for name,addresses in psutil.net_if_addrs().items():
                                    if any(a.address==interface.description for a in addresses):wifi_names[name]=profile
                                # POSIX interfaces already use native interface names.
                                if os.name!='nt':
                                    wifi_names[str(interface.guid)]=profile;continue
                                # Windows adapter GUID -> friendly name from registry.
                                try:
                                    import winreg
                                    key=r'SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}\{'+str(interface.guid)+'}\\Connection'
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,key) as handle:
                                        name=winreg.QueryValueEx(handle,'Name')[0]
                                    wifi_names[name]=profile
                                except OSError:pass
                    identities={p.pid:(p.info.get('exe') or p.info.get('name') or UNKNOWN) for p in psutil.process_iter(['name','exe'],ad_value=None)}
                elapsed,interfaces=rates.sample(psutil.net_io_counters(pernic=True,nowrap=False),now)
                if elapsed>10:
                    if self.traffic:self.traffic.drain()
                    previous_wall=wall
                    self.stop.wait(1)
                    continue  # Sleep/suspension is unknown coverage, not hours of zero traffic.
                capture_bytes+=sum(max(0,v[2])+max(0,v[3]) for v in interfaces.values())
                if os.name=='nt' and self.traffic and not self.traffic.events and not fallback_attempted and now-capture_started>=15 and capture_bytes>=4096 and admin():
                    fallback_attempted=True;self.traffic.close()
                    self.events.put(('capture','No app events received. Trying Windows system capture…'))
                    try:
                        self.traffic=Traffic(system=True);self.traffic.start()
                    except Exception as error:
                        self.traffic=None;self.events.put(('capture',f'App tracking unavailable: {type(error).__name__}. Network totals still work.'))
                live_apps=defaultdict(lambda:[0,0])
                batch=[]
                for name,(down_s,up_s,down,up) in interfaces.items():
                    if name.lower().startswith('loopback'):continue
                    network=wifi_names.get(name) or name
                    batch.append(('adapter',network,'',down,up))
                if self.traffic:
                    for (pid,local),(down,up) in self.traffic.drain().items():
                        name=identities.get(pid) or process_identity(pid)
                        nic=address_map.get(local,'Unattributed interface')
                        network=wifi_names.get(nic) or nic
                        batch.append(('app',network,name,down,up))
                        live_apps[(nic,name)][0]+=down; live_apps[(nic,name)][1]+=up
                        app_totals[(nic,name)][0]+=down; app_totals[(nic,name)][1]+=up
                # Flush every 5 seconds, keeping original interval timestamps for midnight splits.
                if elapsed>0:
                    buffered.append((batch,elapsed,previous_wall,wall)); covered+=elapsed
                if now-flush_at>=5:
                    for sample,seconds,start,end in buffered:self.history.record(sample,seconds,start,end)
                    buffered=[]; flush_at=now
                previous_wall=wall
                self.events.put(('live',{'interfaces':interfaces,'apps':dict(live_apps),'totals':dict(app_totals),
                    'elapsed':elapsed,'wifi':dict(wifi_names),'up':{n for n,s in stats.items() if s.isup}}))
                if self.traffic:
                    self.events.put(('capture',self.traffic.status+f' Events: {self.traffic.events}; decode errors: {self.traffic.errors}; reported loss: {self.traffic.lost}.'))
            except Exception as error:self.events.put(('capture',f'Monitoring error: {type(error).__name__}; incomplete interval.'))
            self.stop.wait(1)
        for sample,seconds,start,end in buffered:self.history.record(sample,seconds,start,end)
        if self.traffic:self.traffic.close()
        if wifi:wifi.close()

    def live(self,value):
        self.last_live=value
        self.app.observe_wifi(value.get('wifi', {}))
        interfaces=value['interfaces']; names=[n for n in interfaces if not n.lower().startswith('loopback')]
        self.adapter_box.configure(values=['Auto (active adapter)']+names)
        selected=self.adapter.get()
        if selected.startswith('Auto'):
            # Choose one interface, never sum virtual and physical copies of the same traffic.
            candidates=[n for n in names if n in value['up']]
            physical=[n for n in candidates if not any(x in n.lower() for x in ('vethernet','virtual','vpn','loopback','wsl','bluetooth','tunnel'))]
            selected=max(physical or candidates,key=lambda n:sum(interfaces[n][:2]),default='')
        down,up=interfaces.get(selected,(0,0,0,0))[:2]
        self.app.activity = (down+up, time.monotonic())
        self.down.set('↓ '+speed(down)); self.up.set('↑ '+speed(up))
        if self.app.tray:self.app.tray.title=('NetCroc · ↓ '+speed(down)+' · ↑ '+speed(up))[:127]
        network=value['wifi'].get(selected,'')
        self.live_status.set(f"Adapter: {selected or 'not connected'}"+(f' · Wi-Fi: {network}' if network else ''))
        if hasattr(self.app, 'shell') and hasattr(self.app.shell, 'network'):
            self.app.shell.network.set(network or selected or 'No active connection')
        self.points.append((down,up)); self.draw_graph()
        total_rows=[];rate_rows=[]
        for (nic,name),(total_down,total_up) in value['totals'].items():
            if nic!=selected:continue
            total_rows.append((name,total_down,total_up))
            down_bytes,up_bytes=value['apps'].get((nic,name),(0,0))
            rate_rows.append((name,down_bytes/max(value['elapsed'],.001),up_bytes/max(value['elapsed'],.001)))
        totals={v.key:v for v in aggregate(total_rows)}
        rates=aggregate(rate_rows)
        rows(self.apps,[(v.label,speed(v.down),speed(v.up),volume(totals[v.key].down+totals[v.key].up)) for v in rates])
        self.overlay_snapshot={'network':network or selected or 'not connected','apps':[(v.label,v.down+v.up) for v in rates if v.down+v.up>0]}

    def draw_graph(self):
        canvas=self.graph; canvas.delete('all'); width=max(canvas.winfo_width(),260); height=max(90,canvas.winfo_height())
        maximum=max([max(p) for p in self.points] or [1]) or 1
        canvas.create_text(8,8,text=speed(maximum),fill='#60776a',anchor='nw')
        if len(self.points)<2:return
        for axis,color in ((0,'#2589d8'),(1,'#18a778')):
            coords=[]
            for index,point in enumerate(self.points):coords.extend((index*(width-10)/89+5,height-10-point[axis]/maximum*(height-35)))
            canvas.create_line(*coords,fill=color,width=2)

    def poll(self):
        if self.stop.is_set():return
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='live':self.live(value);continue
            if kind=='capture':
                self.capture_status.set(value)
                lower=value.lower()
                self.capture_summary.set('App tracking is recording.' if 'capture active' in lower else 'App tracking is unavailable. Network speeds still work.' if 'unavailable' in lower or 'stopped' in lower else 'No app traffic recorded yet. Retrying Windows capture…' if 'trying windows' in lower else 'Waiting for app traffic. If the list stays empty, choose Retry app tracking.')
                continue
            self.busy=False
            self.vpn_line.stop_busy()
            if kind=='adapters':
                self.adapter_info=value; self.dns_box.configure(values=[f"{a['name']} ({a['index']})" for a in value])
                if value:self.dns_box.current(0)
                pending=self.dns.load()
                self.dns_status.set(('Choose a connection and select Test DNS.' if value else 'No connected adapter found.')+(' Original settings are available to restore.' if pending else ''))
            elif kind=='dns':
                self.dns_results=value
                rows(self.dns_table,[(r['name'],', '.join(r['servers']),f"{r['median']:.1f} ms" if r['median'] is not None else 'Unavailable',f"{r['failures']}/{r['attempts']}") for r in value])
                self.dns_status.set('Test finished. Results include cached lookups and network variation. Nothing was changed.')
            elif kind=='wifi':
                self.profiles=value
                self.render_wifi()
            elif kind=='research':
                rows(self.research_table,[(r['isp'],r['url'],f"{r['success']}/{r['attempts']}",f"{r['median_ms']:.1f} ms" if r['median_ms'] is not None else 'Unavailable') for r in value])
                if not self.diagnostic:dns.atomic(self.folder/'url-study.json',{'results':value,'recommended_for_retest':research.recommendations(value)})
                self.research_status.set('Study complete. Use successful results as candidates; repeat on your own ISP.')
            elif kind=='vpn':
                self.vpn_profiles=[item for item,status in value]
                selected=self.vpn_table.selection()
                self.vpn_table.delete(*self.vpn_table.get_children())
                for item,status in value:
                    self.vpn_table.insert('', 'end',iid=item['id'],values=(item['label'],item['endpoint'],item['route'],status['service'],status['handshake']))
                if selected and self.vpn_table.exists(selected[0]):self.vpn_table.selection_set(selected[0])
                self._vpn_empty(len(value))
                self.vpn_line.info(f'{len(value)} saved profiles. '+('WireGuard client found.' if self.vpn_store.backend.installed() else 'Install the official WireGuard client to connect.'))
            elif kind=='vpn-import':
                self.vpn_line.ok('Profile encrypted and saved. No connection or DNS changes were made.')
                self.refresh_vpn()
            elif kind=='vpn-action':
                self.vpn_line.info('VPN operation completed. Refreshing actual service status…')
                self.refresh_vpn()
            elif kind=='vpn-ip':
                address,baseline=value
                if baseline:
                    self.vpn_baseline=address
                    self.vpn_ip.set('Baseline public IPv4: '+address+' · held in memory only.')
                else:
                    comparison=(' · '+('changed from baseline' if address!=self.vpn_baseline else 'same as baseline')) if self.vpn_baseline else ' · no baseline saved'
                    self.vpn_ip.set('Current public IPv4: '+address+comparison+' · this is not a DNS-leak test.')
            elif kind=='message':messagebox.showinfo('NetCroc',value)
            elif kind=='error':
                self.dns_status.set(value); self.wifi_status.set(value); self.vpn_line.error(value); messagebox.showerror('NetCroc',value)
            self._update_vpn_buttons()
        self.root.after(250,self.poll)

    def close(self):
        self.vless_tab.close()
        self.ssh_tab.close()
        self.stop.set()
        # The monitor owns DB writes. Do not close SQLite while its thread is flushing.
        if hasattr(self,'monitor_thread'):
            self.monitor_thread.join(timeout=3)
            if self.monitor_thread.is_alive():return
        self.history.close()
