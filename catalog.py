"""Read Heaps PAK indices without extracting or distributing game assets."""
import struct, json, zipfile, re
from pathlib import Path
class Pak:
    def __init__(self,path):
        self.path=Path(path); self.entries={}
        with self.path.open('rb') as f:
            magic, self.base, size=struct.unpack('<4sII',f.read(12))
            if magic!=b'PAK\0' or self.base<12 or self.base+size!=self.path.stat().st_size: raise ValueError('Invalid PAK header')
            def entry(prefix=''):
                n=f.read(1)[0]; name=f.read(n).decode('utf8'); directory=f.read(1)[0]; key=prefix+name
                if directory==1:
                    count=struct.unpack('<I',f.read(4))[0]
                    if count>100000:raise ValueError('Invalid PAK count')
                    for _ in range(count):entry(key+'/' if key else '')
                elif directory==0:
                    off,length,crc=struct.unpack('<III',f.read(12))
                    if off+length>size:raise ValueError('Invalid PAK offset')
                    self.entries[key]=(off,length)
                else:raise ValueError('Invalid PAK entry')
            entry()
            if f.tell()>self.base:raise ValueError('Invalid PAK index size')
    def read(self,name):
        off,n=self.entries[name]
        with self.path.open('rb') as f:f.seek(self.base+off);return f.read(n)

EVO1_ITEMS=['Potion','Phoenix','Sword2','Armor2','BigSword','Armor3','MagicScroll','DvdPlayer','Bow','Bombs','Card','Choboko','ChobokoCooked']
EVO1_WORLDS='WStart WOver WMeadow WVillage WWell WDungeonStart WDungeon WCave WInterior WMeadow2 WCave2 WLimbs WVillage2 WTwoWorlds2D WTwoWorlds3D WHack WCave2D3D WCave2D3D_2 WBonusDungeon WBonusSwitch2D WBonusSwitch3D WEnd'.split()
SLOTS=['Weapon','Armor','Belt','Boots']
TIMES=['Past','Present','Future','Ancient']
def xml_group(raw,key):
    from html import unescape
    m=re.search(r'<g id="'+re.escape(key)+r'">(.*?)</g>',raw,re.S)
    return [unescape(re.sub('<[^>]+>','',v)).strip() for v in re.findall(r'<t(?:\s[^>]*)?>(.*?)</t>',m.group(1),re.S)] if m else []
def human(id):return re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',id).replace('_',' ')
def extract(folder):
    import csv,io,xml.etree.ElementTree as ET
    folder=Path(folder); a=Pak(folder/'evo1.pak'); b=Pak(folder/'evo2.pak')
    raw=a.read('extra/texts.xml').decode('utf-8-sig'); names=xml_group(raw,'items'); places=xml_group(raw,'places');
    if len(names)!=len(EVO1_ITEMS):raise ValueError('Unexpected Evoland 1 item count')
    items1=[dict(id=i,name=n,category=('Weapon' if i in ('Sword2','BigSword','Bow','Bombs') else 'Armor' if i.startswith('Armor') else 'Consumable' if i in ('Potion','Phoenix') else 'Other')) for i,n in zip(EVO1_ITEMS,names)]
    tetra=a.read('extra/tetra.xml').decode('utf-8-sig'); cards=ET.fromstring(tetra[:tetra.index('</cards>')+8]); cards1=[dict(id=i,code=c.get('id'),name=(c.text or '').replace('${hero}','Clink').replace('${girl}','Kaeris'),power=c.get('power')) for i,c in enumerate(cards)]
    loot=[dict(id=i,name=n,slot=slot) for i,(n,slot) in enumerate(re.findall(r'<i name="([^"]+)" slot="([^"]+)"',a.read('extra/hack.xml').decode('utf-8-sig')))]
    worlds=[dict(id=i,name=(places[j] if j<len(places) and places[j] else human(i))) for j,i in enumerate(EVO1_WORLDS)]
    # The XML place list does not exactly match enum count; keep IDs authoritative.
    for w in worlds:w['name']=human(w['id'])
    d=json.loads(b.read('data.cdb')); s={x['name']:x['lines'] for x in d['sheets']}
    try: lang=Pak(folder/'evo2-extra.pak').read('extra/lang/en.csv')
    except (OSError,ValueError,KeyError):lang=b.read('extra/lang/en.csv')
    tr={r[0]:r[3] for r in csv.reader(io.StringIO(lang.decode('utf-8-sig')),delimiter=';') if len(r)>=4}
    def label(typ,x,key='name'):
        v=tr.get(f'{typ} ({x["id"]})') or x.get(key) or human(x['id'])
        if v.startswith('${'):v=human(x['id']).capitalize()
        return v.split('#',1)[-1] if typ=='item' else v
    items2=[dict(id=x['id'],name=label('item',x),category=SLOTS[x['equip']] if 'equip' in x else ('Material' if x['id'] in ('Mineral','GreenGoo','RedGoo','Energy') else 'Consumable' if 'Potion' in x['id'] else 'Other'),attack=x.get('attack',0),defense=x.get('defense',0),price=x.get('price',0)) for x in s['item']]
    cards2=[dict(id=x['id'],name=label('card',x),cost=x.get('cost',0),attack=x.get('attack',0),life=x.get('life',0)) for x in s['card']]
    areas=[dict(id=x['id'],name=label('level',x,'names'),variants=[]) for x in s['levelEntry']]; byid={x['id']:x for x in areas}
    anchor_idx=next(i for i,x in enumerate(next(t for t in d['customTypes'] if t['name']=='Action')['cases']) if x['name']=='Anchor')
    rtc_idx=next(i for i,x in enumerate(next(t for t in d['customTypes'] if t['name']=='Action')['cases']) if x['name']=='RTC')
    for x in s['levelData']:
        if x.get('level') not in byid:continue
        anchors=[];rtc=[]
        for t in x.get('triggers',[]):
            ac=t.get('action',[])
            if isinstance(ac,list) and len(ac)>1:
                if ac[0]==anchor_idx:anchors.append({'id':ac[1],'x':t['x'],'y':t['y']})
                if ac[0]==rtc_idx:rtc.append(ac[1])
        byid[x['level']]['variants'].append(dict(time=x['time'],width=x['width'],height=x['height'],anchors=anchors,events=sorted(set(rtc))))
    return {'Evo1':{'items':items1,'cards':cards1,'areas':worlds,'loot':loot,'chest_names':re.findall(r'<c\b[^>]*\bname="([^"]+)"',a.read('extra/chests.xml').decode('utf-8-sig'))},'Evo2':{'items':items2,'cards':cards2,'areas':areas,'monsters':[dict(id=x['id'],name=label('monster',x),attack=x.get('attack',0),defense=x.get('defense',0),life=x.get('life',0),xp=x.get('xp',0)) for x in s['monster']], 'level_rules':s['stats'][0]['levelUp']}}
if __name__=='__main__':
    import sys
    print(json.dumps(extract(sys.argv[1]),ensure_ascii=False,indent=2))
