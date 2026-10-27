"""Generate clearly synthetic GUI previews without reading passwords or changing networking."""
import json
import math
import ctypes
import time
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.ui import App

def main():
    output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True)
    root=tk.Tk();app=App(root,diagnostic=True)
    root.title('NetCroc · SYNTHETIC PREVIEW · no network changes')
    root.geometry('1180x740+10+10')
    dashboard=app.dashboard
    dashboard.history.record([('adapter','Preview Wi-Fi','',4*1024**3,512*1024**2),
        ('app','Preview Wi-Fi','browser.exe',3*1024**3,256*1024**2),
        ('app','Preview Wi-Fi','video-call.exe',1024**3,256*1024**2)],1)
    dashboard.live({'interfaces':{'Wi-Fi':(8.5*1024**2,1.2*1024**2,1,1)},
        'apps':{('Wi-Fi','browser.exe'):(7*1024**2,500*1024),('Wi-Fi','video-call.exe'):(1.5*1024**2,700*1024)},
        'totals':{('Wi-Fi','browser.exe'):(3*1024**3,256*1024**2),('Wi-Fi','video-call.exe'):(1024**3,256*1024**2)},
        'elapsed':1,'wifi':{'Wi-Fi':'Preview Wi-Fi'},'up':{'Wi-Fi'}})
    dashboard.points.clear()
    dashboard.points.extend(((6+2*math.sin(i/5))*1024**2,(1+.5*math.cos(i/9))*1024**2) for i in range(90))
    dashboard.capture_status.set('SYNTHETIC PREVIEW: sample app data, not a measured capture.')
    dashboard.refresh_history()
    book=app.shell.book
    try:
        for index,name in ((9,'home'),(10,'tools'),(1,'live'),(2,'history'),(3,'dns'),(0,'keepalive'),(6,'vpn'),(7,'ssh-tls'),(8,'vless')):
            book.select(index);root.deiconify();root.update();dashboard.draw_graph();root.update()
            time.sleep(.35)
            user=ctypes.windll.user32
            user.GetParent.argtypes=[ctypes.c_void_p];user.GetParent.restype=ctypes.c_void_p
            window=user.GetParent(root.winfo_id()) or root.winfo_id()
            ImageGrab.grab(window=window).save(output/(name+'.png'))
        app.compare_window();app.compare_dialog.geometry('+80+80');root.update();time.sleep(.35)
        window=user.GetParent(app.compare_dialog.winfo_id()) or app.compare_dialog.winfo_id()
        ImageGrab.grab(window=window).save(output/'comparison.png')
        app.compare_dialog.destroy()
        dashboard.ssh_tab.edit()
        editor=next(child for child in root.winfo_children() if isinstance(child,tk.Toplevel))
        editor.geometry('+80+80');root.update()
        editor_book=next(child for child in editor.winfo_children() if isinstance(child,ttk.Notebook))
        for index,name in ((0,'ssh-account'),(1,'ssh-trust'),(2,'ssh-payload'),(3,'ssh-routing')):
            editor_book.select(index);root.update();time.sleep(.15)
            window=user.GetParent(editor.winfo_id()) or editor.winfo_id()
            ImageGrab.grab(window=window).save(output/(name+'.png'))
        editor.destroy()
        (output/'preview.json').write_text(json.dumps({'synthetic':True,'tabs':len(book.tabs()),'dns_changed':False,'wifi_changed':False,'passwords_read':False}),encoding='utf-8')
    finally:app.quit()

if __name__=='__main__':main()
