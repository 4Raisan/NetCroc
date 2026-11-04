"""Plain-language error summaries with optional technical details."""
import re,tkinter as tk
from tkinter import ttk,messagebox

def explain(error,context=""):

    raw=str(error);low=raw.lower()
    if '1062' in low or 'service has not been started' in low:
        if not str(context).lower().startswith('wifi'):
            return 'A Windows service is not running','The system service needed for this action is stopped or unavailable. Open Check setup. In Windows Sandbox, physical Wi-Fi services may not be provided.'
        return 'Wi-Fi is unavailable here','Windows is not providing a Wi-Fi service. Windows Sandbox and many virtual machines use a virtual wired connection instead. Network speeds and other tools can still work. On a physical PC, enable Wi-Fi and the WLAN AutoConfig service.'
    if 'access' in low or 'permission' in low or 'administrator' in low:
        return 'Windows permission is required','Approve the Windows administrator prompt, or reopen NetCroc as administrator for this action. Basic monitoring can continue without this permission.'
    if 'timed out' in low or 'timeout' in low:
        return 'The connection took too long','Check your internet connection and server, then try again. Nothing is confirmed connected until verification succeeds.'
    if 'not found' in low or 'no such file' in low or 'missing' in low:
        return 'A required file or tool is missing','Open Check setup to install or repair the missing component, then try again.'
    if 'certificate' in low or 'signature' in low:
        return 'The security check failed','The server certificate or installer signature could not be verified. Check the date/time and connection, or obtain a valid profile. NetCroc did not bypass this check.'
    if raw.startswith(('Choose ','Select ','Disconnect ','Wait ','Run NetCroc','Install ')):return 'Action needed',raw
    return 'The action could not finish','Check your connection and settings, then try again. Open Technical details if you need help diagnosing the problem.'

def install():
    if getattr(messagebox.showerror,'_netcroc_friendly',False):return
    original=messagebox.showerror
    def show(title=None,message=None,**kwargs):
        parent=kwargs.get('parent') or tk._default_root
        if parent is None:return original(title,message,**kwargs)
        headline,help_text=explain(message,title or "")
        dialog=tk.Toplevel(parent);dialog.title(title or 'NetCroc');dialog.transient(parent)
        body=ttk.Frame(dialog,padding=20);body.pack(fill='both',expand=True)
        ttk.Label(body,text=headline,font=('Segoe UI',14,'bold'),wraplength=480).pack(anchor='w')
        ttk.Label(body,text=help_text,wraplength=480,justify='left').pack(anchor='w',pady=12)
        details=tk.Text(body,height=5,wrap='word');details.insert('1.0',str(message));details.configure(state='disabled')
        def toggle():
            if details.winfo_manager():details.pack_forget()
            else:details.pack(fill='both',expand=True,pady=8)
            from .desktop import center_window
            center_window(dialog,parent)
        ttk.Button(body,text='Technical details',command=toggle).pack(side='left')
        ttk.Button(body,text='Close',command=dialog.destroy).pack(side='right')
        from .desktop import center_window
        center_window(dialog,parent);return 'ok'
    show._netcroc_friendly=True;messagebox.showerror=show
