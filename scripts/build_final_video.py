"""Video v2: actual operation footage as full-frame source, Chinese voice, 175 seconds.
No product screenshots/pans are used. Titles/subtitles are editorial overlays only.
"""
import argparse,json,subprocess,hashlib,re,os
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path('tmp/final-video');OUT=ROOT/'v2-render';OUT.mkdir(exist_ok=True)
FONT=Path(os.environ.get('QUOTEPILOT_VIDEO_FONT','../sprint-runtime/video-fonts/QuotePilotSans.ttf'))
STORY=json.loads(Path('media/final_storyboard.json').read_text());EVIDENCE=Path('evidence/final-p1/capture')
clips={x['id']:x for x in json.loads((EVIDENCE/'timeline.json').read_text())}
def recording_path(value):
 p=Path(value)
 if p.exists():return p
 restored=ROOT/'take4'/p.name
 if restored.exists():return restored
 raise FileNotFoundError('Restore recording from materials ZIP: '+p.name)
rolefiles={role:recording_path(json.loads((EVIDENCE/(role+'-video.json')).read_text())['path']) for role in ['admin','reviewer']}
firstadmin=ROOT/'raw/page@63d2789b90dde5bb6c1777998b25058b.webm'
thirdadmin=Path(json.loads(Path('evidence/final-p1/verified/admin-video.json').read_text())['path'])
REUSE=False
def run(cmd,log):
 if REUSE and not log.name.startswith('intake-') and ('-part' in log.stem or log.stem.endswith(('-overlay','-concat'))) and Path(cmd[-1]).suffix=='.mp4' and Path(cmd[-1]).exists():return
 with open(log,'w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
def font(n):return ImageFont.truetype(str(FONT),n)
def wrap(text,width,n):
 rows=[];s=''
 for c in text:
  if s and font(n).getlength(s+c)>width:rows.append(s);s=c
  else:s+=c
 if s:rows.append(s)
 return rows
def overlay(scene):
 im=Image.new('RGBA',(1920,1080));d=ImageDraw.Draw(im)
 d.rectangle((0,0,1920,118),fill=(10,34,36,241));d.rectangle((0,955,1920,1080),fill=(10,34,36,240));d.rectangle((0,0,12,1080),fill='#d78b5d')
 d.text((45,20),'Q / QUOTEPILOT',font=font(24),fill='#edaa73');d.text((45,55),scene['title'],font=font(36),fill='#faf5e9')
 d.text((1505,25),'真实本地操作 · 合成案例',font=font(23),fill='#b7d2c7')
 d.text((1510,1050),'GENESIS / MATRIXONE',font=font(17),fill='#9fbdb1')
 if scene['id']=='hook':
  d.rounded_rectangle((1170,690,1855,915),radius=15,fill=(10,34,36,235));d.text((1210,715),'100 → 500',font=font(78),fill='#f1ac77');d.text((1218,825),'数量更新，旧审批不能沿用',font=font(29),fill='#faf5e9')
 p=OUT/(scene['id']+'-overlay.png');im.save(p);return p

def source(name,target):
 c=clips[name];return (rolefiles[c['role']],c['start_seconds'],c['duration_seconds'],target)
def render_piece(file,start,length,target,path,oy=100):
 # Preserve a real recording; focus the main product area at a fixed camera crop.
 ratio=target/length
 vf=f'setpts={ratio}*(PTS-STARTPTS),crop=1188:668:252:{oy},scale=1920:1080,fps=24,format=yuv420p'
 run(['ffmpeg','-v','error','-y','-ss',str(max(0,start)),'-t',str(length),'-i',str(file),'-vf',vf,'-t',str(target),'-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-an',str(path)],path.with_suffix('.log'))

def build(sample):
 scenes=STORY['scenes'][:1] if sample else STORY['scenes'];final=[];subtitles=[];manifest=[]
 for scene in scenes:
  sid=scene['id'];duration=scene['duration']
  if sid=='hook':
   c=clips['hook'];sources=[(rolefiles['admin'],c['start_seconds']+3.3,min(3,c['duration_seconds']-3.3),4),(rolefiles['admin'],2,13,14)]
  elif sid=='intake':
   evidence=clips['evidence'];sources=[(firstadmin,.75,.65,5),(firstadmin,1.4,2,4),(rolefiles['admin'],evidence['start_seconds']+3.2,evidence['duration_seconds']-3.2,11)]
  elif sid=='evidence':sources=[source('evidence',duration)]
  elif sid=='supplier':sources=[source('supplier',duration)]
  elif sid=='pricing':sources=[source('pricing',duration)]
  elif sid=='change':sources=[source('change',duration)]
  elif sid=='reprice':sources=[source('reprice_review',4),source('reprice_calculate',8),source('reprice_business',4),source('reprice_approve',5)]
  elif sid=='export':sources=[source('export',duration)]
  elif sid=='platform':sources=[source('platform',duration)]
  else:sources=[source('reprice_approve',duration)]
  pieces=[]
  for j,(file,start,length,target) in enumerate(sources):
   p=OUT/(sid+f'-part{j}.mp4');oy=200 if sid in ('pricing','reprice','export','close') else 50 if sid=='evidence' else 100
   render_piece(file,start,length,target,p,oy);pieces.append(p)
  listing=OUT/(sid+'-concat.txt');listing.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in pieces));picture=OUT/(sid+'-picture.mp4')
  run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(picture)],OUT/(sid+'-concat.log'))
  png=overlay(scene);voice=ROOT/'voice'/(sid+'.mp3');voice_duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(voice)]));tempo=max(1,voice_duration/(duration-.4))
  target=OUT/(sid+'-final.mp4');filt=f'[0:v][1:v]overlay=0:0,fade=t=in:st=0:d=0.18,fade=t=out:st={duration-.18}:d=0.18,format=yuv420p[v];[2:a]atempo={tempo},apad,atrim=0:{duration}[a]'
  run(['ffmpeg','-v','error','-y','-i',str(picture),'-i',str(png),'-i',str(voice),'-filter_complex',filt,'-map','[v]','-map','[a]','-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-c:a','aac','-b:a','160k',str(target)],OUT/(sid+'-overlay.log'));final.append(target)
  phrase=[p for p in re.split(r'(?<=[。！？；])',scene['narration']) if p];total=sum(len(p) for p in phrase);t=scene['start']+.15;spoken=min(duration-.4,voice_duration/tempo)
  for p in phrase:
   sec=spoken*len(p)/total;subtitles.append((t,t+sec,wrap(p,1730,38)));t+=sec
  manifest.append({'scene':sid,'sources':[{'path':str(f),'start':s,'length':l,'target':t} for f,s,l,t in sources],'footage_kind':'real_browser_video','target_duration':duration,'voice_seconds':voice_duration,'voice_tempo':tempo})
 def at(t):
  c=round(t*100);return f'{c//360000}:{c//6000%60:02d}:{c//100%60:02d}.{c%100:02d}'
 header='[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,QuotePilot Sans,38,&H00F5F1E8,&H00F5F1E8,&H0010292D,&H0010292D,0,0,0,0,100,100,0,0,1,1,0,2,90,90,60,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
 ass=OUT/('sample.ass' if sample else 'final.ass');ass.write_text(header+'\n'.join('Dialogue: 0,'+at(a)+','+at(b)+',Default,,0,0,0,,'+r'\N'.join(rows) for a,b,rows in subtitles)+'\n')
 listing=OUT/('sample.txt' if sample else 'all.txt');listing.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in final));combined=OUT/('sample-combined.mp4' if sample else 'combined.mp4');run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(combined)],OUT/'combine.log')
 movie=ROOT/('QuotePilot_v2_Opening_18s.mp4' if sample else 'QuotePilot_v2_175s.mp4');run(['ffmpeg','-v','error','-y','-i',str(combined),'-vf',f'ass={ass}:fontsdir={FONT.parent}','-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-c:a','aac','-b:a','160k','-movflags','+faststart',str(movie)],OUT/'final-export.log')
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]));expected=18 if sample else 175;assert abs(float(meta['format']['duration'])-expected)<.2
 video=next(s for s in meta['streams'] if s['codec_type']=='video');assert (video['width'],video['height'])==(1920,1080)
 report={'file':str(movie),'duration_seconds':float(meta['format']['duration']),'width':1920,'height':1080,'fps':video['r_frame_rate'],'sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'bytes':movie.stat().st_size,'all_product_backgrounds':'actual browser screencasts, not screenshot pans','voice':'synthesized Mandarin Chinese zh-CN-XiaoxiaoNeural','voice_present':True,'synthetic_business_data':True,'public_acceptance':False,'timeline':manifest,'complete_playback_review':False}
 Path('evidence/final-p2/'+('opening-validation.json' if sample else 'video-validation.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='timeline'},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--opening',action='store_true');p.add_argument('--reuse-unchanged-scenes',action='store_true');args=p.parse_args();REUSE=args.reuse_unchanged_scenes;build(args.opening)
