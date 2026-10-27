"""Small, user-initiated setup check and repair dialog."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser
from . import vpn
from .prerequisites import inspect


def show(app):
    existing=getattr(app,'setup_dialog',None)
    if existing and existing.winfo_exists():existing.lift();return
    dialog=app.setup_dialog=tk.Toplevel(app.root);dialog.title('NetCroc setup');dialog.geometry('640x390')
    outer=ttk.Frame(dialog,padding=20);outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='Setup & repairs',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(outer,text='Check what is ready. Optional tools are only needed for their features.',wraplength=570).pack(anchor='w',pady=(4,14))
    result=tk.StringVar(value='Checking…')
    ttk.Label(outer,textvariable=result,justify='left',wraplength=570).pack(anchor='w',fill='x',pady=8)
    status=tk.StringVar(value='Nothing is installed automatically.')
    ttk.Label(outer,textvariable=status,wraplength=570).pack(anchor='w',pady=8)
    buttons=ttk.Frame(outer);buttons.pack(anchor='w',pady=8)
    events=queue.Queue();busy={'value':False}
    def refresh():
        if busy['value']:return
        busy['value']=True;status.set('Checking installed tools…')
        def work():
            try:events.put(('checked',inspect(app.dashboard.folder,app.dashboard.vpn_store.backend)))
            except Exception as error:events.put(('error',type(error).__name__))
        threading.Thread(target=work,daemon=True).start()
    def repair():
        if busy['value']:return
        if app.dashboard.ssh_tab.session or app.dashboard.vless_tab.session:
            status.set('Disconnect the SSH / VLESS tunnel before repairing the core.');return
        busy['value']=True;status.set('Downloading and verifying the optional routing core…')
        def work():
            try:app.dashboard.ssh_tab.routing.install();events.put(('repaired',None))
            except Exception as error:events.put(('error',type(error).__name__))
        threading.Thread(target=work,daemon=True).start()
    ttk.Button(buttons,text='Check again',command=refresh).pack(side='left',padx=(0,8))
    ttk.Button(buttons,text='Install / repair routing core',command=repair).pack(side='left',padx=(0,8))
    ttk.Button(buttons,text='Get WireGuard',command=lambda:webbrowser.open(vpn.INSTALL_URL)).pack(side='left')
    ttk.Label(outer,text='WireGuard opens the official installer page. Routing core is downloaded from its official release and checked against a pinned SHA-256.',wraplength=570,style='Muted.TLabel').pack(anchor='w',pady=10)
    def poll():
        if not dialog.winfo_exists():return
        while not events.empty():
            kind,value=events.get();busy['value']=False
            if kind=='checked':
                result.set('\n'.join(('Ready' if ok else 'Needs attention')+'  ·  '+name+'\n    '+note for name,ok,note in value))
                status.set('Checks complete.');
            elif kind=='repaired':status.set('Routing core installed and verified.');refresh()
            else:status.set('Could not complete setup: '+value+'. Check your connection and try again.')
        dialog.after(200,poll)
    refresh();poll()
