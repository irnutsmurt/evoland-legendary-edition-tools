"""Unified Evoland Legendary Edition save editor. No third-party dependencies."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from pathlib import Path
import json,sys,math
from save_engine import *
from catalog import extract,SLOTS,TIMES,human
ROOT=Path(__file__).resolve().parent
class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title('Evoland Save Editor');self.geometry('1120x760');self.minsize(850,580)
        self.catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf8'));self.path=None;self.original=self.draft=None;self.state=None;self.game=None;self.history=[];self.tables={};self.statvars={}
        style=ttk.Style(self);
        if 'clam' in style.theme_names() and self.tk.call('tk','windowingsystem')=='x11':style.theme_use('clam')
        style.configure('Title.TLabel',font=('TkDefaultFont',18,'bold'));style.configure('Heading.TLabel',font=('TkDefaultFont',12,'bold'));style.configure('Treeview',rowheight=26);style.configure('TButton',padding=6);style.configure('TNotebook.Tab',padding=(12,8))
        outer=ttk.Frame(self,padding=16);outer.pack(fill='both',expand=True)
        head=ttk.Frame(outer);head.pack(fill='x');ttk.Label(head,text='Evoland Save Editor',style='Title.TLabel').pack(side='left');self.game_label=tk.StringVar(value='No save loaded');ttk.Label(head,textvariable=self.game_label,style='Heading.TLabel').pack(side='right')
        self.summary=tk.StringVar(value='Open an Evoland 1 or Evoland 2 .sav file to get started.');ttk.Label(outer,textvariable=self.summary,wraplength=950).pack(anchor='w',pady=(5,12))
        bar=ttk.Frame(outer);bar.pack(fill='x',pady=(0,10));self.actions={}
        for text,fn in [('Open save…',self.open_dialog),('Save as…',lambda:self.save(True)),('Overwrite save',lambda:self.save(False)),('Undo',self.undo),('Review changes',self.review),('Reset edits',self.reset),('Import game catalogs…',self.import_catalog)]:
            b=ttk.Button(bar,text=text,command=fn);b.pack(side='left',padx=(0,5));self.actions[text]=b
        self.tabs=ttk.Notebook(outer);self.tabs.pack(fill='both',expand=True);self.status=tk.StringVar(value='Offline • Original save stays intact until you save.');ttk.Label(outer,textvariable=self.status,wraplength=1000).pack(anchor='w',pady=(10,0))
        self.protocol('WM_DELETE_WINDOW',self.close);self.bind('<Control-o>',lambda e:self.open_dialog());self.bind('<Control-s>',lambda e:self.save(True));self.bind('<Control-z>',lambda e:self.undo());self.update_header()
        t=self.tab('Welcome','Edit both games from a single application.');ttk.Label(t,text='1. Open a .sav file.\n2. Choose a tab and apply your changes.\n3. Review the changes, then Save as or Overwrite.\n\nThe game is detected automatically. Catalogs are included; no game installation is required.\nEvery overwrite creates a timestamped backup. Close the game before replacing its save.',justify='left',wraplength=700).pack(anchor='w',pady=20)
        if len(sys.argv)>1:self.open_path(sys.argv[1])
    def tab(self,name,desc):
        t=ttk.Frame(self.tabs,padding=14);self.tabs.add(t,text=name);ttk.Label(t,text=name,style='Heading.TLabel').pack(anchor='w');ttk.Label(t,text=desc,wraplength=930).pack(anchor='w',pady=(3,10));return t
    def buttons(self,parent,*items):
        f=ttk.Frame(parent);f.pack(fill='x',pady=(8,0));
        for label,fn in items:ttk.Button(f,text=label,command=fn).pack(side='left',padx=(0,6))
        return f
    def table(self,parent,columns,rows,edit=None,search=True,filters=None):
        # rows are (stable key, visible tuple). Local filtering retains selected IDs.
        if search:
            r=ttk.Frame(parent);r.pack(fill='x',pady=(0,6));ttk.Label(r,text='Search').pack(side='left');q=tk.StringVar();ttk.Entry(r,textvariable=q).pack(side='left',fill='x',expand=True,padx=8)
        filter_var=None;owned_var=None
        if filters:
            r2=ttk.Frame(parent);r2.pack(fill='x',pady=(0,6));ttk.Label(r2,text='Category').pack(side='left');filter_var=tk.StringVar(value='All');ttk.Combobox(r2,textvariable=filter_var,values=['All',*filters],state='readonly',width=18).pack(side='left',padx=8);owned_var=tk.BooleanVar(value=False);ttk.Checkbutton(r2,text='Owned only',variable=owned_var).pack(side='left',padx=10)
        f=ttk.Frame(parent);f.pack(fill='both',expand=True);t=ttk.Treeview(f,columns=tuple(range(len(columns))),show='headings',selectmode='browse');sb=ttk.Scrollbar(f,command=t.yview);t.configure(yscrollcommand=sb.set);sb.pack(side='right',fill='y');t.pack(fill='both',expand=True)
        for i,(name,width) in enumerate(columns):t.heading(i,text=name,command=lambda j=i:sort(j));t.column(i,width=width,minwidth=55,anchor='w')
        def fill(*_):
            sel=t.selection();t.delete(*t.get_children());needle=q.get().lower() if search else ''
            for k,vs in rows:
                if filters and ((filter_var.get()!='All' and vs[1]!=filter_var.get()) or (owned_var.get() and not vs[2])):continue
                if needle in ' '.join(map(str,vs)).lower():t.insert('','end',iid=str(k),values=vs)
            if sel and t.exists(sel[0]):t.selection_set(sel[0])
        def sort(j):
            def key(r):
                v=r[1][j];return (0,v) if isinstance(v,(int,float)) else (1,str(v).lower())
            rows.sort(key=key,reverse=getattr(t,'reverse',False));t.reverse=not getattr(t,'reverse',False);fill()
        if search:q.trace_add('write',fill)
        if filters:filter_var.trace_add('write',fill);owned_var.trace_add('write',fill)
        fill();
        if edit:t.bind('<Double-1>',lambda e:edit(t))
        return t
    def selected(self,t):
        s=t.selection();return s[0] if s else None
    def get(self,p):return plain(resolve(self.state,p))
    def update_header(self):
        dirty=self.draft is not None and self.draft!=self.original
        for k,b in self.actions.items():
            if k not in ('Open save…','Import game catalogs…'):b.configure(state='normal' if self.draft and (dirty or k=='Save as…') else 'disabled')
        if self.state:
            s=self.state;g='Evoland 1' if self.game=='Evo1' else 'Evoland 2';self.game_label.set(g+' • '+('Unsaved edits' if dirty else 'Checksum valid'))
            if self.game=='Evo2': detail=f"Level {self.get(('level','level'))}   |   {self.get(('currentLevel',))}   |   {self.get(('gold',)):,} gold"
            else: detail=f"Level {self.get(('levels',0,'lv'))}   |   {self.get(('world',))[1]}   |   {self.get(('money',)):,} glis"
            self.summary.set(f'{self.path.name}   •   {detail}');self.title('Evoland Save Editor — '+self.path.name+(' *' if dirty else ''))
    def confirm_discard(self):return self.original==self.draft or messagebox.askyesno('Discard edits?','There are unsaved changes. Discard them?',parent=self)
    def close(self):
        if self.confirm_discard():self.destroy()
    def open_dialog(self):
        if not self.confirm_discard():return
        p=filedialog.askopenfilename(filetypes=[('Evoland saves','*.sav'),('All files','*')],parent=self)
        if p:self.open_path(p)
    def open_path(self,path):
        try:
            text=load(path);_,s=unpack(text);g=game_type(text)
            if g=='Evo2':stats(s)
            else:
                for p in [('items',),('levels',0,'lv'),('money',),('world',)]:resolve(s,p)
            self.path=Path(path);self.original=self.draft=text;self.state=s;self.game=g;self.history=[];self.rebuild();self.status.set('Loaded successfully. Checksum valid.')
        except Exception as e:messagebox.showerror('Cannot open save',str(e),parent=self)
    def stage(self,changes=None,stat=None,coords=None,checkpoints=False,description='Changes applied'):
        try:
            new=self.draft
            if stat or coords:new=edit(new,stat or {},coords or {},checkpoints)
            if changes:new=general_edit(new,changes)
            if new==self.draft:return
            self.history.append((self.draft,description));self.draft=new;self.state=unpack(new)[1];self.rebuild();self.status.set(description+' — staged, not written to disk.')
        except Exception as e:messagebox.showerror('Cannot apply edit',str(e),parent=self)
    def undo(self):
        if self.history:
            self.draft,desc=self.history.pop();self.state=unpack(self.draft)[1];self.rebuild();self.status.set('Undid: '+desc)
    def reset(self):
        if self.confirm_discard():self.draft=self.original;self.state=unpack(self.draft)[1];self.history=[];self.rebuild();self.status.set('All edits discarded.')
    def review(self):
        if not self.history:return
        w=tk.Toplevel(self);w.title('Review staged changes');w.geometry('650x380');f=ttk.Frame(w,padding=14);f.pack(fill='both',expand=True);ttk.Label(f,text=f'{len(self.history)} edit operation(s)',style='Heading.TLabel').pack(anchor='w');t=tk.Text(f,wrap='word',height=14);t.pack(fill='both',expand=True,pady=8)
        for i,(_,desc) in enumerate(self.history,1):t.insert('end',f'{i}. {desc}\n')
        t.configure(state='disabled');ttk.Button(f,text='Close',command=w.destroy).pack(anchor='e')
    def save(self,copy):
        if not self.draft:return
        try:
            if copy:
                p=filedialog.asksaveasfilename(parent=self,initialdir=self.path.parent,initialfile=self.path.stem+'_edited.sav',defaultextension='.sav',filetypes=[('Evoland saves','*.sav')]);
                if not p:return
                p=Path(p)
            else:p=self.path
            if p.resolve()==self.path.resolve() and load(p)!=self.original:raise SaveError('Original save changed on disk. Reload it before overwriting.')
            if p.exists() and not messagebox.askyesno('Overwrite save?',f'Replace {p.name}? A backup will be created. Close the game first.',parent=self):return
            backup=write_save(p,self.draft);self.open_path(p);self.status.set('Saved. Checksum verified.'+(f' Backup: {backup.name}' if backup else ''))
        except Exception as e:messagebox.showerror('Cannot save',str(e),parent=self)
    def import_catalog(self):
        p=filedialog.askdirectory(title='Select folder containing evo1.pak and evo2.pak',parent=self)
        if not p:return
        try:self.catalog=extract(p);self.rebuild() if self.state else None;self.status.set('Game catalogs loaded from your installation (this session).')
        except Exception as e:messagebox.showerror('Catalog import failed',str(e),parent=self)
    def rebuild(self):
        active=self.tabs.tab(self.tabs.select(),'text') if self.tabs.select() else ''
        for child in self.tabs.winfo_children():child.destroy()
        self.db=self.catalog[self.game];self.itemdb={x['id']:x for x in self.db['items']};self.make_stats();self.make_items();self.make_equipment();self.make_cards();
        if self.game=='Evo2':self.make_team()
        elif 'hackEquip' in self.state:self.make_loot()
        self.make_world();self.make_quests();self.make_advanced();self.make_reference()
        for tab in self.tabs.tabs():
            if self.tabs.tab(tab,'text')==active:self.tabs.select(tab);break
        self.update_header()
    def form(self,parent,fields):
        f=ttk.Frame(parent);f.pack(anchor='nw',fill='x');vs={}
        for i,(key,label,value) in enumerate(fields):
            ttk.Label(f,text=label).grid(row=i//2,column=(i%2)*2,sticky='w',padx=(0,12),pady=7);v=tk.StringVar(value=str(value));ttk.Entry(f,textvariable=v,width=22).grid(row=i//2,column=(i%2)*2+1,sticky='ew',padx=(0,28),pady=7);vs[key]=v
        return vs
    def make_stats(self):
        t=self.tab('Stats','Edit character values directly. Apply changes before switching tabs. High values may exceed normal game limits.')
        if self.game=='Evo2':
            names={'level':'Level','attack':'Attack','defense':'Defense','max_hp':'Maximum HP','hp':'Current HP','xp':'Experience','gold':'Gold'};vs=self.form(t,[(k,n,self.get(p)) for k,p in FIELDS.items() for n in [names[k]]]);cp=tk.BooleanVar(value=True);ttk.Checkbutton(t,text='Also apply changed stats to embedded checkpoints (survive death)',variable=cp).pack(anchor='w',pady=8)
            def apply():
                try:
                    values={k:int(v.get()) for k,v in vs.items()};changed={k:v for k,v in values.items() if v!=self.get(FIELDS[k])};self.stage(stat=changed,checkpoints=cp.get(),description='Stats: '+', '.join(f'{names[k]}={v}' for k,v in changed.items()))
                except ValueError:messagebox.showerror('Invalid value','Enter whole numbers.',parent=self)
            def boost():
                for k,v in {'level':30,'attack':100,'defense':100,'max_hp':250,'hp':250}.items():vs[k].set(v)
            self.buttons(t,('Apply stats',apply),('Full heal',lambda:vs['hp'].set(vs['max_hp'].get())),('Boss boost preset',boost));ttk.Label(t,text='Presets populate the fields; Apply stats stages them. Equipment bonuses are separate reference values.',wraplength=850).pack(anchor='w',pady=12)
        else:
            fields=[(('levels',0,'lv'),'Hero level'),(('levels',0,'xp'),'Hero XP'),(('levels',1,'lv'),'Companion level'),(('levels',1,'xp'),'Companion XP'),(('money',),'Glis'),(('life',),'Current life'),(('maxLife',),'Maximum life'),(('finalLife',),'Final-stage life'),(('keys',),'Keys'),(('heroName',),'Hero name'),(('girlName',),'Companion name')];fields=[(p,n) for p,n in fields if p[0] in self.state];vs=self.form(t,[(p,n,self.get(p)) for p,n in fields]);
            def apply():
                try:
                    changes={p:(int(v.get()) if type(self.get(p))==int else v.get()) for p,v in vs.items()};
                    if any(type(v)==int and not 0<=v<=2147483647 for v in changes.values()):raise ValueError('Values must be nonnegative integers.')
                    if changes[('life',)]>changes[('maxLife',)]:raise ValueError('Current life cannot exceed maximum life.')
                    if any(changes.get(p,1)<1 for p in [('levels',0,'lv'),('levels',1,'lv'),('maxLife',)]):raise ValueError('Level and maximum life must be at least 1.')
                    self.stage(changes={p:v for p,v in changes.items() if v!=self.get(p)},description='Stats: '+', '.join(f'{label}={changes[p]}' for p,label in fields if changes[p]!=self.get(p)))
                except ValueError as e:messagebox.showerror('Invalid value',str(e),parent=self)
            self.buttons(t,('Apply stats',apply),('Full heal',lambda:vs[('life',)].set(vs[('maxLife',)].get())));ttk.Label(t,text='Evoland 1 stores levels and experience, but no direct attack/defense fields were found in this save. Equipment affects combat; final-stage life has separate storage.',wraplength=850).pack(anchor='w',pady=12)
    def inventory(self):
        path=('inventory',) if self.game=='Evo2' else ('items',);raw=self.get(path);return path,raw,{(x['kind'] if self.game=='Evo2' else x['id'][1]):(x['qty'] if self.game=='Evo2' else x['c']) for x in raw}
    def quantity(self,key,q,raw=None):
        path,old,owned=self.inventory();raw=old if raw is None else raw;kind=lambda x:x['kind'] if self.game=='Evo2' else x['id'][1];count='qty' if self.game=='Evo2' else 'c';found=False;new=[]
        for x in raw:
            if kind(x)==key:
                found=True
                if q:new.append(dict(x,**{count:q}))
            else:new.append(x)
        if q and not found:new.append({'qty':q,'kind':key} if self.game=='Evo2' else {'c':q,'id':('evo1.InventoryItem',key,[])})
        return path,new
    def make_items(self):
        t=self.tab('Items','Search all known items, including items not currently owned. Double-click to change quantity; zero removes an item.');path,raw,owned=self.inventory();rows=[]
        for id in sorted(set(self.itemdb)|set(owned)):
            x=self.itemdb.get(id,{'name':human(id),'category':'Unknown'});rows.append((id,(x['name'],x['category'],owned.get(id,0),x.get('attack','—'),x.get('defense','—'),id)))
        def change(tree):
            k=self.selected(tree)
            if k is None:return
            q=simpledialog.askinteger('Item quantity',f'{self.itemdb.get(k,{}).get("name",k)}\nNew quantity (0 removes):',initialvalue=owned.get(k,0),minvalue=0,maxvalue=999999,parent=self)
            if q is None:return
            if self.game=='Evo2' and k in (self.get(('equip',)) or []) and q==0:messagebox.showerror('Equipped item','Unequip this item before removing it.',parent=self);return
            if (q==0 or self.itemdb.get(k,{}).get('category') in ('Other','Unknown')) and not messagebox.askyesno('Change item?', 'Some items are tied to story progress. This changes inventory only, not quest flags. Continue?',parent=self):return
            p,v=self.quantity(k,q);self.stage({p:v},description=f'Item {k}: {owned.get(k,0)} → {q}')
        tree=self.table(t,[('Item',240),('Category',100),('Owned',65),('Attack',65),('Defense',65),('Internal ID',150)],rows,change,filters=sorted({r[1][1] for r in rows}));self.buttons(t,('Set selected quantity',lambda:change(tree)))
    def make_equipment(self):
        t=self.tab('Equipment','Equip known gear from the correct slot. Missing equipped items are added to inventory automatically.' if self.game=='Evo2' else 'Evoland 1 equipment is represented by inventory items. Double-click gear to edit its quantity.');
        if self.game=='Evo1':
            _,_,owned=self.inventory();rows=[(k,(x['name'],x['category'],owned.get(k,0),k)) for k,x in self.itemdb.items() if x['category'] in ('Weapon','Armor')];
            def gear(tree):
                k=self.selected(tree)
                if k is None:return
                q=simpledialog.askinteger('Equipment quantity',self.itemdb[k]['name'],initialvalue=owned.get(k,0),minvalue=0,maxvalue=99,parent=self)
                if q is not None:
                    if q==0 and not messagebox.askyesno('Remove equipment?','This may affect combat or progression. Continue?',parent=self):return
                    p,raw=self.quantity(k,q);self.stage({p:raw},description=f'Equipment {k}: {owned.get(k,0)} → {q}')
            tree=self.table(t,[('Equipment',240),('Type',100),('Owned',80),('Internal ID',130)],rows,gear);self.buttons(t,('Set gear quantity',lambda:gear(tree)));return
        eq=self.get(('equip',));vars=[];lookup=[];f=ttk.Frame(t);f.pack(fill='x');
        for i,slot in enumerate(SLOTS):
            ttk.Label(f,text=slot,width=12).grid(row=i,column=0,sticky='w',pady=8);opts={f"{x['name']}  |  ATK +{x['attack']}  DEF +{x['defense']}  [{k}]":k for k,x in self.itemdb.items() if x['category']==slot};opts={'(None)':None,**opts};current=(eq[i] or None) if i<len(eq) else None
            if current and current not in opts.values():opts[f'{current} [existing]']=current
            v=tk.StringVar(value=next(k for k,id in opts.items() if id==current));ttk.Combobox(f,values=list(opts),textvariable=v,state='readonly',width=62).grid(row=i,column=1,sticky='ew',pady=8);vars.append(v);lookup.append(opts)
        f.columnconfigure(1,weight=1)
        def apply():
            new=[opts[v.get()] for v,opts in zip(vars,lookup)];p,raw,owned=self.inventory()
            for k in new:
                if k and not owned.get(k):_,raw=self.quantity(k,1,raw);owned[k]=1
            self.stage({p:raw,('equip',):new},description='Equipment: '+', '.join(k or 'None' for k in new))
        def best():
            for v,opts in zip(vars,lookup):v.set(max((k for k,id in opts.items() if id in self.itemdb),key=lambda k:self.itemdb[opts[k]]['attack']+self.itemdb[opts[k]]['defense']))
        self.buttons(t,('Apply equipment',apply),('Select highest bonuses',best));ttk.Label(t,text='Attack and defense in the save are not recalculated here. Use Stats to adjust them separately.',wraplength=850).pack(anchor='w',pady=10)
    def make_cards(self):
        t=self.tab('Collectibles','Manage cards and collectible counters. Evoland 1 numeric card names are a provisional XML-order mapping; verify in-game.' if self.game=='Evo1' else 'Manage your card collection and Star inventory count.');cards=self.get(('cards',));db={x['id']:x for x in self.db['cards']};rows=[]
        for k in dict.fromkeys([*db,*cards]):
            x=db.get(k,{});rows.append((k,(x.get('name',str(k)), 'Yes' if k in cards else 'No',x.get('power',f"{x.get('attack','—')} / {x.get('life','—')}"),k)))
        def toggle(tree):
            k=self.selected(tree)
            if k is None:return
            if self.game=='Evo1':
                k=int(k)
                if not messagebox.askyesno('Raw card index',f'Change ownership of raw card index {k}? Mapping is not verified in-game.',parent=self):return
            new=[x for x in cards if x!=k] if k in cards else cards+[k];self.stage({('cards',):new},description=f'Card {k}: '+('removed' if k in cards else 'added'))
        tree=self.table(t,[('Card',250),('Owned',80),('Power / ATK / HP',150),('ID',130)],rows,toggle)
        def allcards():
            if messagebox.askyesno('Add all cards?','Add every catalog card. Quest flags and achievements are unchanged.',parent=self):self.stage({('cards',):list(dict.fromkeys([*cards,*db]))},description='Add all catalog cards')
        def stars():
            val=self.get(('stars',)) if self.game=='Evo1' else self.inventory()[2].get('Star',0);q=simpledialog.askinteger('Stars','New star count:',initialvalue=val,minvalue=0,maxvalue=99999,parent=self)
            if q is not None:
                if self.game=='Evo1':self.stage({('stars',):q},description=f'Stars: {val} → {q}')
                else:p,v=self.quantity('Star',q);self.stage({p:v},description=f'Stars: {val} → {q}')
        self.buttons(t,('Toggle selected card',lambda:toggle(tree)),('Set stars',stars), *((('Add all cards',allcards),) if self.game=='Evo2' else ()))
    def make_team(self):
        t=self.tab('Companions','Modify existing companion unlock values and active-party HP/MP. Unlock values are raw game data; -1 may indicate default HP/MP.');persist=self.get(('teamPersist',));team=self.get(('team',));active={x['k']:(i,x) for i,x in enumerate(team)};rows=[(k,(k,x.get('unlock','—'),active[k][1].get('life') if k in active else '—',active[k][1].get('mp') if k in active else '—')) for k,x in persist.items()]
        def edit_team(tree):
            k=self.selected(tree)
            if k is None:return
            changes={};p=('teamPersist',k,'unlock')
            if 'unlock' in persist[k]:
                q=simpledialog.askinteger('Companion',f'{k}: raw unlock value',initialvalue=self.get(p),minvalue=0,maxvalue=10,parent=self)
                if q is None:return
                changes[p]=q
            if k in active:
                for name in ('life','mp'):
                    p=('team',active[k][0],name);q=simpledialog.askinteger('Companion',f'{k}: {name}',initialvalue=self.get(p),minvalue=-1,maxvalue=99999,parent=self)
                    if q is not None:changes[p]=q
            self.stage(changes,description=f'Companion {k}')
        tree=self.table(t,[('Character',200),('Unlock',100),('HP',100),('MP',100)],rows,edit_team);self.buttons(t,('Edit companion',lambda:edit_team(tree)))
    def make_loot(self):
        t=self.tab('Loot','Diablo-style loot records. Names are based on XML order; the saved flag meaning has not been verified. Only existing flags are editable.')
        db={x['id']:x for x in self.db.get('loot',[])};raw=self.get(('hackEquip',));existing={x['id']:(i,x) for i,x in enumerate(raw)};rows=[]
        for k in sorted(set(db)|set(existing)):
            x=db.get(k,{});row=existing.get(k);rows.append((k,(x.get('name',f'Loot {k}'),x.get('slot','—'),'Yes' if row else 'No',str(row[1]['flag']) if row else '—',k)))
        def toggle(tree):
            k=self.selected(tree)
            if k is None:return
            k=int(k)
            if k not in existing:messagebox.showinfo('No saved record','This entry is absent in the save. Structural insertion is not supported.',parent=self);return
            i,x=existing[k]
            if messagebox.askyesno('Raw loot flag',f"Toggle raw flag for {db.get(k,{}).get('name',k)}? Its gameplay meaning is unverified.",parent=self):self.stage({('hackEquip',i,'flag'):not x['flag']},description=f'Loot {k} flag toggled')
        tree=self.table(t,[('Loot',340),('Slot',100),('Saved record',90),('Raw flag',90),('ID',65)],rows,toggle);self.buttons(t,('Toggle raw flag',lambda:toggle(tree)))
    def make_world(self):
        t=self.tab('World','Location changes can break story progression. Use known spawn anchors, and always keep a backup.')
        if self.game=='Evo1':
            vs=self.form(t,[(('pos','x'),'Position X',self.get(('pos','x'))),(('pos','y'),'Position Y',self.get(('pos','y')))]);world=self.get(('world',));ids=[x['id'] for x in self.db['areas']];v=tk.StringVar(value=world[1]);r=ttk.Frame(t);r.pack(fill='x',pady=10);ttk.Label(r,text='World ID').pack(side='left');ttk.Combobox(r,textvariable=v,values=ids,state='readonly',width=35).pack(side='left',padx=10)
            def apply():
                try:
                    new={p:float(x.get()) for p,x in vs.items()};new[('world',)]=(world[0],v.get(),[])
                    if not all(math.isfinite(new[p]) for p in vs):raise ValueError('Coordinates must be finite')
                    if messagebox.askyesno('Unsafe relocation','Evoland 1 coordinate and world pairing is not validated. Continue?',parent=self):self.stage(new,description='Raw world / position edit')
                except ValueError as e:messagebox.showerror('Invalid position',str(e),parent=self)
            self.buttons(t,('Apply raw relocation',apply));return
        areas={x['id']:x for x in self.db['areas']};labels={f"{x['name']} [{x['id']}]":x['id'] for x in areas.values()};current=self.get(('currentLevel',));label=next((k for k,v in labels.items() if v==current),current);a=tk.StringVar(value=label);tm=tk.StringVar();anchor=tk.StringVar();variant_map={};anchor_map={};f=ttk.Frame(t);f.pack(fill='x');f.columnconfigure(1,weight=1)
        for i,(n,v) in enumerate([('Area',a),('Timeline',tm),('Spawn anchor',anchor)]):ttk.Label(f,text=n,width=15).grid(row=i,column=0,sticky='w',pady=6);box=ttk.Combobox(f,textvariable=v,state='readonly',width=60);box.grid(row=i,column=1,sticky='ew',pady=6);setattr(self,'world_box'+str(i),box)
        self.world_box0['values']=sorted(labels)
        info=tk.StringVar();ttk.Label(t,textvariable=info,wraplength=850).pack(anchor='w',pady=8)
        def anchors(*_):
            variant=variant_map.get(tm.get(),{});anchor_map.clear();anchor_map.update({f"{x['id']}  ({x['x']}, {x['y']})":x for x in variant.get('anchors',[])});self.world_box2['values']=list(anchor_map);cur=self.get(('startAnchor',));anchor.set(next((k for k,v in anchor_map.items() if v['id']==cur),next(iter(anchor_map),'')));info.set(f"Map size: {variant.get('width','—')} × {variant.get('height','—')} tiles  •  {len(anchor_map)} known anchors. Only explicit map anchors are offered.")
        def variants(*_):
            variant_map.clear();variant_map.update({TIMES[x['time']]:x for x in areas.get(labels.get(a.get()),{}).get('variants',[]) if 0<=x['time']<len(TIMES)});self.world_box1['values']=list(variant_map);cur=self.get(('currentTime',));name=TIMES[cur] if 0<=cur<len(TIMES) else '';tm.set(name if name in variant_map else next(iter(variant_map),''));anchors()
        self.world_box0.bind('<<ComboboxSelected>>',variants);self.world_box1.bind('<<ComboboxSelected>>',anchors);variants()
        def relocate():
            if a.get() not in labels or tm.get() not in variant_map or anchor.get() not in anchor_map:messagebox.showerror('Missing anchor','Select an area, timeline and known anchor.',parent=self);return
            if not messagebox.askyesno('Relocate character','Teleporting may bypass required story events. The previous checkpoint is not changed. Continue?',parent=self):return
            id=labels[a.get()];v=variant_map[tm.get()];name=anchor_map[anchor.get()]['id'];self.stage({('currentLevel',):id,('currentTime',):v['time'],('startAnchor',):name,('heroX',):-1,('heroY',):-1},description=f'Relocate to {id} / {tm.get()} / {name}')
        self.buttons(t,('Apply relocation',relocate));
        if positions(self.state):
            ttk.Separator(t).pack(fill='x',pady=15);ttk.Label(t,text='Sylph Forest objects',style='Heading.TLabel').pack(anchor='w');pos=positions(self.state);r=ttk.Frame(t);r.pack(fill='x',pady=6);opts={f'{k}  —  X {x:g}, Y {y:g}':k for k,(x,y) in pos.items()};v=tk.StringVar(value=next(iter(opts)));ttk.Combobox(r,values=list(opts),textvariable=v,state='readonly',width=45).pack(side='left');
            def move():
                k=opts[v.get()];x,y=pos[k];newx=simpledialog.askfloat('Object position','X (quarter-tile increments):',initialvalue=x,parent=self)
                if newx is None:return
                newy=simpledialog.askfloat('Object position','Y (quarter-tile increments):',initialvalue=y,parent=self)
                if newy is not None:self.stage(coords={k:(newx,newy)},description=f'Forest object {k}: ({x}, {y}) → ({newx}, {newy})')
            ttk.Button(r,text='Edit position',command=move).pack(side='left',padx=8)
    def scalar_rows(self,roots):
        rows=[];paths={}
        def walk(n,p):
            if p==('prevSave',):return
            if isinstance(n.value,dict):
                for k,v in n.value.items():walk(v,p+(k,))
            elif isinstance(n.value,list):
                for i,v in enumerate(n.value):
                    if isinstance(v,Node):walk(v,p+(i,))
            elif n.tag in ('i','z','d','t','f','n','y','R','w'):
                key=str(len(paths));paths[key]=p;value=n.value[1] if n.tag=='w' else n.value;rows.append((key,(' / '.join(map(str,p)),str(value)[:250],n.tag)))
        for k in roots:
            if k in self.state:walk(self.state[k],(k,))
        return rows,paths
    def scalar_editor(self,t,roots,warning):
        rows,paths=self.scalar_rows(roots)
        def change(tree):
            key=self.selected(tree)
            if key is None:return
            p=paths[key];n=resolve(self.state,p);v=n.value;name=' / '.join(map(str,p));new=None
            if p[:2]==('sylves','dr'):messagebox.showinfo('Forest object','Use the World tab to edit packed positions.',parent=self);return
            if n.tag=='w':messagebox.showinfo('Enum','Raw enum editing is disabled here. Use a dedicated tab.',parent=self);return
            if type(v)==bool:new=messagebox.askyesnocancel('Set flag',f'{name}\nYes = true; No = false; Cancel = unchanged.',parent=self)
            elif type(v)==int:new=simpledialog.askinteger('Edit value',name,initialvalue=v,minvalue=-2147483648,maxvalue=2147483647,parent=self)
            elif type(v)==float:new=simpledialog.askfloat('Edit value',name,initialvalue=v,parent=self)
            else:new=simpledialog.askstring('Edit value',name,initialvalue='' if v is None else v,parent=self)
            if new is not None and new!=v and messagebox.askyesno('Confirm raw edit',warning,parent=self):self.stage({p:new},description=f'{name}: {v} → {new}')
        tree=self.table(t,[('Save field',520),('Value',260),('Type',65)],rows,change);self.buttons(t,('Edit selected field',lambda:change(tree)))
    def make_quests(self):
        t=self.tab('Progression','Search existing quest flags, area records, achievements and other progress counters. Editing them may make the save unplayable.');roots=('globalFlags','doneRtc','levelData','ach','tacticsTroups','pendingRtc','heroFlags','gameMode') if self.game=='Evo2' else ('chests','wdata','ach','hackEquip','nchests','girlBits','rtcBits','cardLevel','campQuest','villageUnlock','weapons','heroGrow','has3D','canSave','freeMove','monsters','scroll','color','music','view');self.scalar_editor(t,roots,'This is a raw progression edit. Related flags, achievements and counts are not updated automatically. Continue?')
    def make_advanced(self):
        t=self.tab('Advanced','Browse all existing scalar save fields. Embedded checkpoint strings, enum changes and structural edits are protected.');self.scalar_editor(t,[k for k in self.state if k!='prevSave'],'Changing an internal value can corrupt progression or violate gameplay invariants. Continue?')
    def make_reference(self):
        t=self.tab('Reference','Game database reference. This tab does not modify the save.');opts=['Areas','Cards','Items']+(['Enemies','Map events'] if self.game=='Evo2' else ['Chest rewards']);v=tk.StringVar(value=opts[0]);r=ttk.Frame(t);r.pack(fill='x',pady=(0,8));ttk.Label(r,text='Catalog').pack(side='left');box=ttk.Combobox(r,textvariable=v,values=opts,state='readonly',width=20);box.pack(side='left',padx=8);f=ttk.Frame(t);f.pack(fill='both',expand=True)
        def show(*_):
            for w in f.winfo_children():w.destroy()
            k=v.get()
            if k=='Areas':
                rows=[]
                for x in self.db['areas']:
                    if x.get('variants'):
                        for i,z in enumerate(x['variants']):rows.append((f"{x['id']}-{i}",(x['name'],x['id'],TIMES[z['time']],f"{z['width']} × {z['height']}",', '.join(y['id'] for y in z['anchors']))))
                    else:rows.append((x['id'],(x['name'],x['id'],'—','—','—')))
                self.table(f,[('Location',200),('ID',150),('Timeline',90),('Map size',100),('Known anchors',360)],rows)
            elif k=='Map events':
                rows=[(f"{x['id']}-{z['time']}-{i}",(x['name'],x['id'],TIMES[z['time']],e)) for x in self.db['areas'] for z in x['variants'] for i,e in enumerate(z.get('events',[]))];self.table(f,[('Area',220),('ID',150),('Timeline',100),('RTC event ID',280)],rows)
            elif k=='Chest rewards':self.table(f,[('Reward name (reference only)',500)],[(i,(name,)) for i,name in enumerate(self.db.get('chest_names',[]))])
            elif k=='Enemies':self.table(f,[('Enemy',200),('ID',150),('Attack',80),('Defense',80),('HP',80),('XP',80)],[(x['id'],(x['name'],x['id'],x['attack'],x['defense'],x['life'],x['xp'])) for x in self.db['monsters']])
            elif k=='Items':self.table(f,[('Item',230),('ID',150),('Category',100),('Price',80),('ATK',80),('DEF',80)],[(x['id'],(x['name'],x['id'],x['category'],x.get('price','—'),x.get('attack','—'),x.get('defense','—'))) for x in self.db['items']])
            else:self.table(f,[('Card',230),('ID',130),('Cost',90),('ATK',90),('HP / power',140)],[(x['id'],(x['name'],x['id'],x.get('cost','—'),x.get('attack','—'),x.get('life',x.get('power','—')))) for x in self.db['cards']])
        box.bind('<<ComboboxSelected>>',show);show()
if __name__=='__main__':
    if '--smoke-test' in sys.argv:
        sys.argv.remove('--smoke-test')
        app=App()
        if not app.catalog.get('Evo1') or not app.catalog.get('Evo2'):
            raise RuntimeError('Game catalogs missing')
        app.update_idletasks()
        app.destroy()
    else:
        App().mainloop()
