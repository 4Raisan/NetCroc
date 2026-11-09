"""About panel with a non-blocking release check."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from . import updates, updater

class About:
    def __init__(self,app):
        self.app=app;self.root=app.root;self.events=queue.Queue();self.busy=False
        self.summary=tk.StringVar(value='Updates not checked')
        self.latest=tk.StringVar(value='v'+updates.VERSION+' · '+('Not checked' if app.diagnostic else 'Checking…'))
        if not app.diagnostic:self.root.after(1800,self.check)
    def check(self):
        if self.busy:return
        self.busy=True;self.summary.set('Checking for updates…')
        def work():
            try:self.events.put(updates.check())
            except Exception:self.events.put({'status':'unavailable'})
        threading.Thread(target=work,daemon=True).start()
        self.root.after(150,self.poll)
    def poll(self):
        if self.app.closing:return
        try:data=self.events.get_nowait()
        except queue.Empty:self.root.after(150,self.poll);return
        self.busy=False
        self.latest.set('v'+updates.VERSION+' · '+('Outdated' if data['status']=='available' else 'Latest' if data['status']=='current' else 'Check unavailable'))
        self.release=data
        self.update_url=data.get('url',updates.REPO+'/releases')
        if data['status']=='available':self.summary.set('Update available: '+data['version'])
        elif data['status']=='current':self.summary.set('No newer release found · '+data['version'])
        else:self.summary.set('Update check unavailable')
    def install(self):
        if self.busy or self.app.closing:
            return
        release = getattr(self, 'release', {})
        if release.get('status') != 'available':
            return
        if not messagebox.askyesno('Update NetCroc',
                                   f"Download {release['version']} and restart NetCroc? Active connections may be interrupted.",
                                   parent=self.root):
            return
        self.busy = True
        self.summary.set('Downloading and verifying update…')
        self.latest.set('Downloading update…')

        def work():
            try:
                self.events.put(updater.stage_update(release))
            except Exception as error:
                self.events.put(error)

        threading.Thread(target=work, daemon=True).start()
        self.root.after(150, self.poll_install)

    def poll_install(self):
        if self.app.closing:
            return
        try:
            result = self.events.get_nowait()
        except queue.Empty:
            self.root.after(150, self.poll_install)
            return
        try:
            if isinstance(result, Exception):
                raise result
            updater.launch_update(*result)
        except Exception as error:
            self.busy = False
            self.latest.set('v'+updates.VERSION+' · Outdated')
            self.summary.set('Update available: '+self.release['version'])
            messagebox.showerror('Update failed', str(error), parent=self.root)
            return
        self.app.quit()

    def show(self):
        old=getattr(self,'dialog',None)
        if old and old.winfo_exists():old.lift();return
        dialog=self.dialog=tk.Toplevel(self.root);dialog.title('About NetCroc');dialog.geometry('520x310')
        body=ttk.Frame(dialog,padding=22);body.pack(fill='both',expand=True)
        ttk.Label(body,text='NetCroc',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(body,text='Your quiet network companion.',style='Muted.TLabel').pack(anchor='w',pady=(2,14))
        ttk.Label(body,text='Version '+updates.VERSION).pack(anchor='w')
        ttk.Label(body,textvariable=self.summary,wraplength=460).pack(anchor='w',pady=12)
        line=ttk.Frame(body);line.pack(anchor='w')
        ttk.Button(line,text='Check for updates',command=self.check).pack(side='left',padx=(0,8))
        ttk.Button(line,text='View releases',command=lambda:webbrowser.open(updates.REPO+'/releases')).pack(side='left')
        ttk.Button(body,text='Star on GitHub',command=lambda:webbrowser.open(updates.REPO)).pack(anchor='w',pady=14)
