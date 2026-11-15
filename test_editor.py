"""Offline checks. Run python test_editor.py [optional Evo1/Evo2 save paths]."""
import sys, tempfile, unittest, json
from pathlib import Path
from save_engine import *
from catalog import SLOTS
ROOT=Path(__file__).parent
DB=json.loads((ROOT/'catalog.json').read_text(encoding='utf8'))
def envelope(body):return body+'#'+checksum(body)
class Tests(unittest.TestCase):
    def test_catalog(self):
        self.assertEqual(len(DB['Evo2']['items']),74)
        self.assertEqual(len(DB['Evo2']['cards']),61)
        self.assertEqual(len(DB['Evo1']['items']),13)
        self.assertEqual(len(DB['Evo1']['cards']),23)
        self.assertEqual(len(DB['Evo2']['areas']),93)
        self.assertEqual(len(DB['Evo1']['loot']),24)
        for g in DB.values():
            for key in ['items','cards','areas']:self.assertEqual(len(g[key]),len({r['id'] for r in g[key]}))
    def test_synthetic_enum_and_refs(self):
        s=envelope('oy4:dataoy5:itemsaoy1:ci1y2:idwy18:evo1.InventoryItemy6:Potion:0ghy5:moneyi2y4:nameR5gy4:gamewy8:GameTypey4:Evo1:0g')
        self.assertEqual(game_type(s),'Evo1')
        items=plain(unpack(s)[1]['items']);items.append({'c':2,'id':('evo1.InventoryItem','Phoenix',[])})
        r=general_edit(s,{('items',):items,('money',):500})
        self.assertEqual(plain(unpack(r)[1]['items']),items)
        self.assertEqual(plain(unpack(r)[1]['name']),'Potion')
        self.assertEqual(plain(unpack(r)[1]['money']),500)
        self.assertEqual(general_edit(r,{}),r)
        with self.assertRaises(SaveError):unpack(r[:-1]+'!')
    def test_write_backup(self):
        a=envelope('oy4:dataoy5:moneyi1gy4:gamewy8:GameTypey4:Evo1:0g');b=general_edit(a,{('money',):2})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'slot.sav';self.assertIsNone(write_save(p,a));bak=write_save(p,b);self.assertEqual(load(bak),a);self.assertEqual(load(p),b)

def check_real(path):
    raw=load(path);body,state=unpack(raw);g=game_type(raw);assert general_edit(raw,{})==raw
    if g=='Evo1':
        items=plain(state['items']);existing={x['id'][1] for x in items};k=next((x['id'] for x in DB[g]['items'] if x['id'] not in existing),None)
        if k:items.append({'c':2,'id':('evo1.InventoryItem',k,[])})
        else:items[0]['c']+=1
        modified=general_edit(raw,{('items',):items,('money',):123456,('levels',0,'lv'):20});s=unpack(modified)[1];assert plain(s['items'])==items and plain(s['money'])==123456
        world=plain(state['world']);other=next(x['id'] for x in DB[g]['areas'] if x['id']!=world[1]);modified=general_edit(raw,{('world',):(world[0],other,[]) });assert plain(unpack(modified)[1]['world'])[1]==other
        cards=plain(state['cards']);modified=general_edit(raw,{('cards',):cards+[next(x for x in range(23) if x not in cards)]}) if len(set(cards))<23 else raw;unpack(modified)
    else:
        modified=edit(raw,{'level':30,'attack':100,'defense':100,'max_hp':250,'hp':250},checkpoints=True);s=unpack(modified)[1]
        while True:
            assert stats(s)['hp']==250 and stats(s)['attack']==100
            prev=s.get('prevSave');
            if not prev or not prev.value:break
            s=Parser(prev.value).parse().value
        items=plain(state['inventory']);eq=['LastSword','LastArmor','LastBelt','LastBoots'];owned={x['kind'] for x in items}
        for k in eq:
            if k not in owned:items.append({'qty':1,'kind':k})
        r=general_edit(raw,{('inventory',):items,('equip',):eq,('cards',):[x['id'] for x in DB[g]['cards']]});s=unpack(r)[1];assert plain(s['equip'])==eq and len(plain(s['cards']))==61
        area=next(x for x in DB[g]['areas'] if x['id']=='FirstVillage');v=next(x for x in area['variants'] if x['anchors']);anchor=v['anchors'][0]['id'];r=general_edit(raw,{('currentLevel',):area['id'],('currentTime',):v['time'],('startAnchor',):anchor,('heroX',):-1,('heroY',):-1});assert plain(unpack(r)[1]['startAnchor'])==anchor
        ps=positions(state)
        if ps:
            k,(x,y)=next(iter(ps.items()));r=edit(raw,coords={k:(x+0.25,y)});assert positions(unpack(r)[1])[k]==(x+0.25,y)
    print('Real save checks passed:',Path(path).name,g)
if __name__=='__main__':
    paths=sys.argv[1:];suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    for path in paths:check_real(path)
