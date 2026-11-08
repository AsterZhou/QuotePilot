"""Decode the actual MP4 and sample every scene, no mocked media evidence."""
from pathlib import Path
import json,subprocess,hashlib,re
from PIL import Image,ImageStat,ImageDraw
root=Path('tmp/product-video');movie=root/'QuotePilot_180s_subtitled.mp4';scenes=json.loads(Path('media/storyboard.json').read_text())['scenes']
decoded=subprocess.run(['ffmpeg','-v','error','-i',str(movie),'-f','null','-'],capture_output=True,text=True)
assert decoded.returncode==0 and not decoded.stderr,decoded.stderr
sheet=Image.new('RGB',(1920,1080),'#ffffff');checks=[]
for i,s in enumerate(scenes):
    t=s['start']+s['duration']/2;out=root/(s['id']+'-final.png')
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(movie),'-frames:v','1',str(out)],check=True)
    im=Image.open(out);std=max(ImageStat.Stat(im).stddev);assert std>10
    checks.append({'scene':s['id'],'time_seconds':t,'nonblack_stddev':round(std,2),'frame_sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
    im.thumbnail((380,214));x=(i%5)*384;y=(i//5)*540;sheet.paste(im,(x,y+28));ImageDraw.Draw(sheet).text((x+5,y+5),s['id'],fill='black')
sheet.save(root/'review-contact.png')
volume=subprocess.run(['ffmpeg','-hide_banner','-i',str(movie),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True)
volumes=re.findall(r'(mean_volume|max_volume): ([\-0-9.]+) dB',volume.stderr)
report={'sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'full_file_decode_exit_code':decoded.returncode,'sampled_frames':checks,'all_decoded':True,'audio_db':dict(volumes),'note':'Technical checks; final Chinese glyph/layout inspection performed on decoded frames separately'}
Path('evidence/sprint-p2/frame-decode.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'decoded':True,'frames_checked':len(checks),'audio_db':dict(volumes)}))
