"""Create a static medium font for consistent Pillow/libass Chinese glyph rendering."""
import argparse
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');args=p.parse_args()
font=TTFont(args.source)
if 'fvar' in font:instantiateVariableFont(font,{'wght':500},inplace=True)
for name in font['name'].names:
    value={1:'QuotePilot Sans',2:'Medium',4:'QuotePilot Sans Medium',6:'QuotePilotSansMedium',16:'QuotePilot Sans',17:'Medium'}.get(name.nameID)
    if value:
        try:name.string=value.encode(name.getEncoding())
        except UnicodeEncodeError:pass
out=Path(args.destination);out.parent.mkdir(parents=True,exist_ok=True);font.save(out);print(out)
