"""Small, user-initiated setup check and repair dialog."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser
from . import vpn,wireguard_setup
from .prerequisites import inspect


def show(app):
    existing=getattr(app,'setup_dialog',None)
    if existing and existing.winfo_exists():existing.lift();return
    dialog=app.setup_dialog=tk.Toplevel(app.root);dialog.title('NetCroc setup');dialog.geometry('720x520')
    dialog.transient(app.root)
    from .desktop import center_window
    app._center_jobs.append(app.root.after_idle(lambda:center_window(dialog,app.root) if dialog.winfo_exists() else None))
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
            try:
                events.put(('checked',inspect(app.dashboard.folder,app.dashboard.vpn_store.backend)))
                if __import__('os').name=='nt' and not app.diagnostic:
                    try:events.put(('wireguard-status',wireguard_setup.status(app.dashboard.vpn_store.backend)))
                    except Exception:events.put(('wireguard-unavailable',None))
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
    def manage_wireguard():
        if __import__('os').name!='nt':
            import sys
            command='brew install wireguard-tools' if sys.platform=='darwin' else 'Install wireguard-tools using your distribution package manager (Ubuntu/Debian: sudo apt install wireguard-tools). '
            __import__('tkinter').messagebox.showinfo('WireGuard tools',command+' Then choose Check again. NetCroc manages the VPN profile after installation.',parent=dialog)
            return
        if busy['value']:return
        busy['value']=True;status.set('Preparing official WireGuard installer. Approve Windows if asked…')
        def work():
            try:events.put(('wireguard-done',wireguard_setup.install_or_update(app.dashboard.vpn_store.backend)))
            except Exception as error:events.put(('error',str(error)))
        threading.Thread(target=work,daemon=True).start()
    wireguard_button=ttk.Button(buttons,text='Install / update WireGuard',command=manage_wireguard)
    wireguard_button.pack(side='left')
    ttk.Label(outer,text='Windows: NetCroc manages the signed WireGuard installer. Linux/macOS: use the system WireGuard tools. Routing core is downloaded from its official release and checked against a pinned SHA-256.',wraplength=570,style='Muted.TLabel').pack(anchor='w',pady=10)
    def poll():
        if not dialog.winfo_exists():return
        while not events.empty():
            kind,value=events.get();busy['value']=False
            if kind=='checked':
                result.set('\n'.join(('Ready' if ok else 'Needs attention')+'  ·  '+name+'\n    '+note for name,ok,note in value))
                installed=any(name=='WireGuard' and ok for name,ok,note in value)
                if __import__('os').name=='nt':wireguard_button.configure(text='Check / update WireGuard' if installed else 'Install WireGuard',state='normal')
                else:wireguard_button.configure(text='WireGuard installed' if installed else 'WireGuard setup help',state='disabled' if installed else 'normal')
                status.set('Checks complete.');
            elif kind=='wireguard-status':
                if value['needed']:wireguard_button.configure(text=('Update WireGuard '+value['latest']) if value['installed'] else 'Install WireGuard',state='normal')
                else:wireguard_button.configure(text='WireGuard '+value['installed']+' ready',state='disabled')
            elif kind=='wireguard-unavailable':status.set('Tools checked. WireGuard update check unavailable; try again online.')
            elif kind=='wireguard-done':status.set(value);app.dashboard.refresh_vpn();refresh()
            elif kind=='repaired':status.set('Routing core installed and verified.');refresh()
            else:
                from .errors import explain
                headline,help_text=explain(value)
                status.set(headline+'. '+help_text)
                __import__('tkinter').messagebox.showerror('Setup could not finish',value,parent=dialog)
        dialog.after(200,poll)
    refresh();poll()
