"""Game Patches module for Evoland Toolkit."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import os,sys,re
from patch_engine import PATCH_INFO,inspect,apply,PatchError

def discover():
    home=Path.home();roots=[home/'.steam/steam',home/'.local/share/Steam',home/'.var/app/com.valvesoftware.Steam/.local/share/Steam']
    if sys.platform=='win32':roots.extend(Path(os.environ.get(v,'C:/Program Files (x86)'))/'Steam' for v in ('ProgramFiles(x86)','ProgramFiles'))
    libraries=[]
    for root in roots:
        libraries.append(root)
        try:
            txt=(root/'steamapps/libraryfolders.vdf').read_text(encoding='utf8');libraries.extend(Path(s.replace('\\\\','\\')) for s in re.findall(r'"path"\s+"([^"]+)"',txt))
        except OSError:pass
    for root in libraries:
        for name in ('Evoland Legendary Edition','Evoland 2'):
            p=root/'steamapps/common'/name
            if any((p/n).is_file() for n in ('hlboot.dat','sdlboot.dat')):return str(p)
    return ''

class PatchWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent);self.title('Evoland Toolkit — Game Patches');self.geometry('810x580');self.minsize(720,510);self.transient(parent)
        f=ttk.Frame(self,padding=18);f.pack(fill='both',expand=True)
        ttk.Label(f,text='Game patches',style='Title.TLabel').pack(anchor='w');ttk.Label(f,text='Evoland 2 · Experimental community patches',style='Heading.TLabel').pack(anchor='w',pady=(4,5));ttk.Label(f,text='Only the verified Legendary Edition builds are supported. Close the game before applying or restoring patches.',wraplength=740).pack(anchor='w',pady=(0,12))
        ttk.Label(f,text='Game installation folder').pack(anchor='w');self.path=tk.StringVar(value=discover());row=ttk.Frame(f);row.pack(fill='x',pady=(4,6));ttk.Entry(row,textvariable=self.path).pack(side='left',fill='x',expand=True);ttk.Button(row,text='Browse…',command=self.browse).pack(side='left',padx=(6,0));ttk.Button(row,text='Check',command=self.check).pack(side='left',padx=(6,0));self.info=tk.StringVar(value='Select the folder containing hlboot.dat or sdlboot.dat.');ttk.Label(f,textvariable=self.info,wraplength=740,justify='left').pack(anchor='w',pady=(3,12))
        self.vars={};self.controls=[]
        for k,(title,desc) in PATCH_INFO.items():
            box=ttk.LabelFrame(f,text=title,padding=10);box.pack(fill='x',pady=(0,8));v=tk.BooleanVar(value=False);self.vars[k]=v;c=ttk.Checkbutton(box,text='Enable experimental patch',variable=v,command=self.enable_buttons);c.pack(anchor='w');self.controls.append(c);ttk.Label(box,text=desc,wraplength=700,justify='left').pack(anchor='w',pady=(4,0))
        self.ready=False;self.checked_path=None;self.states=[];bar=ttk.Frame(f);bar.pack(fill='x',pady=(5,6));self.applybtn=ttk.Button(bar,text='Apply selection',command=lambda:self.run(False));self.applybtn.pack(side='left');self.restorebtn=ttk.Button(bar,text='Restore original game',command=lambda:self.run(True));self.restorebtn.pack(side='left',padx=6);ttk.Button(bar,text='Close',command=self.destroy).pack(side='right');self.status=tk.StringVar(value='Original boot files will be backed up automatically. Saves are never edited here.');ttk.Label(f,textvariable=self.status,wraplength=740).pack(anchor='w',pady=(5,0));self.path.trace_add('write',lambda *_:self.invalidate());self.enable_buttons()
        if self.path.get():self.check()
    def invalidate(self):
        self.ready=False;self.info.set('Path changed. Click Check to verify the game files.');self.enable_buttons()
    def enable_buttons(self):
        for c in self.controls:c.configure(state='normal' if self.ready else 'disabled')
        self.applybtn.configure(state='normal' if self.ready else 'disabled');self.restorebtn.configure(state='normal' if self.ready and any(s['state'] for s in self.states) else 'disabled')
    def browse(self):
        p=filedialog.askdirectory(parent=self,title='Select Evoland Legendary Edition installation folder')
        if p:self.path.set(p);self.check()
    def check(self):
        self.ready=False;self.states=[]
        try:
            if not self.path.get().strip():raise PatchError('Select an installation folder.')
            self.checked_path=Path(self.path.get()).expanduser().resolve();self.states=inspect(self.checked_path);lines=[]
            for s in self.states:
                label='Unsupported / modified' if s['state'] is None else 'Original' if not s['state'] else 'Installed: '+s['state'].replace(',',' + ');lines.append(f"{s['name']}: {label}"+(' · backup verified' if s['backup'] else ''))
            self.info.set('\n'.join(lines));self.ready=all(s['state'] is not None and (not s['state'] or s['backup']) for s in self.states)
            if self.ready:
                common=set.intersection(*(set(s['state'].split(',')) if s['state'] else set() for s in self.states))
                for k,v in self.vars.items():v.set(k in common)
                self.status.set('Verified build. Select the patches to install. If builds differ, applying a selection synchronizes them.')
            else:self.status.set('Unsupported build or missing original backup. No writes are allowed.')
        except Exception as e:self.info.set(str(e));self.status.set('Nothing has been modified.')
        self.enable_buttons()
    def run(self,restore):
        if not self.ready or Path(self.path.get()).expanduser().resolve()!=self.checked_path:return
        patches=set() if restore else {k for k,v in self.vars.items() if v.get()};label='Restore the original game files' if not patches else 'Apply: '+', '.join(PATCH_INFO[k][0] for k in sorted(patches))
        if not messagebox.askyesno('Confirm game patch',label+'?\n\nClose Evoland first. These patches have passed bytecode checks but have not been tested in a running game. Original files are backed up; save files are untouched.',parent=self):return
        try:
            apply(self.checked_path,patches);self.check();self.status.set('Verified successfully. '+('Experimental patches installed. Test in-game; restore if needed.' if patches else 'Original game files restored.'))
        except Exception as e:messagebox.showerror('Patch failed',str(e),parent=self);self.check()
