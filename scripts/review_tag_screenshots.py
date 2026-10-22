"""Tile every acceptance screenshot without omitting pixels for manual viewing."""
from pathlib import Path
import json
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'.cache/frontend-visual-review/unify-card-tags/current'
out=folder/'review';out.mkdir(exist_ok=True)
manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
tiles=[]
for case in manifest['cases']:
    for suffix in ('','-end'):
        filename=f"{case['name']}-{case['width']}{suffix}.png"
        im=Image.open(folder/filename).convert('RGB')
        if not suffix and case.get('viewport_files'):
            # Every document pixel comes from an actually painted viewport. Crop
            # overlap before its fixed bottom bar; the final viewport keeps it.
            verified=Image.new('RGB',(case['width'],case['height']),'white')
            views=case['viewport_files']
            for index,view in enumerate(views):
                source=Image.open(folder/view['file']).convert('RGB')
                stop=views[index+1]['y'] if index+1<len(views) else case['height']
                verified.paste(source.crop((0,0,case['width'],stop-view['y'])),(0,view['y']))
            verified.save(folder/(filename[:-4]+'-verified.png'))
            im=verified
        # Desktop at 75% remains legible; mobile stays at native pixel width.
        if im.width==1280: im=im.resize((960,round(im.height*.75)))
        for y in range(0,im.height,900):
            part=im.crop((0,y,im.width,min(y+900,im.height)))
            tile=Image.new('RGB',(im.width,930),'#eeeeee')
            ImageDraw.Draw(tile).text((4,4),filename+f' / y={y}',fill='black')
            tile.paste(part,(0,25));tiles.append((filename,y,tile))
sheets=[];row=[];width=0
def save():
    global row,width
    if not row:return
    sheet=Image.new('RGB',(width,930),'#cccccc');x=0;items=[]
    for filename,y,tile in row:
        sheet.paste(tile,(x,0));items.append({'file':filename,'y':y,'x':x});x+=tile.width+8
    name=f'sheet-{len(sheets)+1:03}.png';sheet.save(out/name)
    sheets.append({'sheet':name,'tiles':items});row=[];width=0
for filename,y,tile in tiles:
    if row and width+tile.width+8>1960:save()
    row.append((filename,y,tile));width+=tile.width+8
save()
(out/'index.json').write_text(json.dumps(sheets,indent=2),encoding='utf-8')
print(json.dumps({'screenshots':len(manifest['cases'])*2,'tiles':len(tiles),'sheets':len(sheets),'review_directory':str(out)}))
