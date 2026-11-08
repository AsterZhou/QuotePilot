"""180s truthful product cut: actual browser footage/screens, approved PDF and live receipts.
No generated product UI, invented platform state, customer ROI or third-party music.
"""
from pathlib import Path
import json,subprocess,hashlib,math,wave,re,os
from PIL import Image,ImageDraw,ImageFont
import pymupdf
ROOT=Path('tmp/product-video');ROOT.mkdir(parents=True,exist_ok=True)
OUT=ROOT/'render';OUT.mkdir(exist_ok=True)
STORY=json.loads(Path('media/storyboard.json').read_text());LIVE=json.loads(Path('evidence/sprint-p0/live.json').read_text())
BROWSER=Path('evidence/sprint-p2/browser');FONT=Path(os.environ.get('QUOTEPILOT_VIDEO_FONT','../sprint-runtime/video-fonts/QuotePilotSans.ttf'))
W,H=1920,1080;BG='#10292d';CREAM='#f5f1e8';MUTED='#b0c2bd';ORANGE='#e49b6a';ACCENT='#a9d8bf';X,Y,VW,VH=750,190,1090,660

def font(n):return ImageFont.truetype(str(FONT),n)
def wrap(s,n,width):
    rows=[];line='';f=font(n)
    for char in s:
        if char=='\n' or (line and f.getlength(line+char)>width):rows.append(line);line='' if char=='\n' else char
        else:line+=char
    if line:rows.append(line)
    return rows

def text(d,s,xy,n=36,color=CREAM,width=580,spacing=12):
    x,y=xy
    for row in wrap(s,n,width):d.text((x,y),row,font=font(n),fill=color);y+=n+spacing
    return y

def base(scene,i):
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    d.rectangle((0,0,16,H),fill=ORANGE);d.rounded_rectangle((70,45,130,105),radius=10,fill=ORANGE);d.text((84,46),'Q',font=font(43),fill=BG)
    d.text((155,53),'QUOTEPILOT',font=font(30),fill=CREAM);d.text((155,91),'RFQ / QUOTATION INTELLIGENCE',font=font(15),fill=MUTED)
    d.text((1480,65),'合成案例 · 本地真实运行',font=font(25),fill=ACCENT)
    d.line((75,140,1840,140),fill='#3f5859',width=2);d.text((80,183),scene['kicker'],font=font(22),fill=ORANGE)
    end=text(d,scene['title'],(78,245),64,width=590,spacing=15)
    by=max(end+45,480)
    for bullet in scene['bullets']:
        d.ellipse((82,by+18,94,by+30),fill=ORANGE);by=text(d,bullet,(112,by),32,color=MUTED,width=520,spacing=8)+25
    d.text((82,850),f'{i+1:02d} / {len(STORY["scenes"]):02d}',font=font(25),fill=ORANGE)
    d.rounded_rectangle((X-8,Y-8,X+VW+8,Y+VH+8),radius=16,fill='#38545a')
    d.rounded_rectangle((X,Y,X+VW,Y+VH),radius=10,fill=CREAM)
    d.rectangle((75,905,1845,1030),fill='#092126');d.text((80,1040),'剪辑加速 / 所有价格均为合成数据 / 无自动对客发送',font=font(20),fill=MUTED)
    d.text((1560,1040),'SUBTITLED CUT · 03:00',font=font(20),fill=ORANGE)
    return im

def screenshot(scene):
    mapping={'review':('01-field-evidence.png',350,1100),'supplier':('02-source-extraction.png',200,900),'cost':('03-cost-plans.png',1680,1900),'version':('05-version-impact.png',1050,1850),'approval':('04-approved.png',1700,2000),'upload':('01-field-evidence.png',100,450)}
    name,sy,ey=mapping[scene['id']];im=Image.open(BROWSER/name).convert('RGB');im=im.crop((252,0,im.width,im.height));im=im.resize((VW,round(im.height*VW/im.width)))
    p=OUT/(scene['id']+'-screen.png');im.save(p);return p,min(sy,im.height-VH),min(ey,im.height-VH)

def custom(scene):
    panel=Image.new('RGB',(VW,VH),CREAM);d=ImageDraw.Draw(panel)
    if scene['id']=='opening':
        d.text((60,70),'从一封邮件，到一份可审批报价。',font=font(47),fill=BG)
        for y,a,b in [(220,'01','保留来源'),(320,'02','透明成本'),(420,'03','人工审批')]:
            d.text((60,y),a,font=font(52),fill='#bc6545');d.text((180,y+4),b,font=font(46),fill=BG);d.line((180,y+85,1000,y+85),fill='#d7ddd4',width=2)
    elif scene['id']=='platform':
        g=LIVE['genesis'];m=LIVE['commercial_mirror']
        for y,title,detail in [(45,'GENESIS / 真实模型响应',g['model']+' · '+str(g['usage']['total_tokens'])+' Token'),(245,'MATRIXONE / 应用层报价镜像','已审批 v3 → 云端写入 → 完整读回校验')]:
            d.rounded_rectangle((40,y,1050,y+170),radius=16,fill='#deebe0');d.text((70,y+18),title,font=font(28),fill='#1c594b');d.text((70,y+70),detail,font=font(37),fill=BG)
        d.text((70,171),g['response_id'],font=font(19),fill='#47665d')
        d.text((70,374),'SHA256 '+m['payload_sha256'][:30]+'…',font=font(20),fill='#47665d')
        d.rounded_rectangle((40,460,1050,620),radius=16,fill='#f3dfca');d.text((70,477),'MOI 原生工作流 / 未运行',font=font(32),fill='#98512e')
        d.text((70,532),'启动 HTTP 400 · 无执行 ID · 未创建计费实例',font=font(27),fill=BG)
    elif scene['id']=='closing':
        d.text((65,72),'为报价团队，保留判断的依据。',font=font(48),fill=BG)
        for y,s in [(205,'已验证：本地业务闭环、双角色审批'),(285,'已验证：Genesis推理、MatrixOne镜像'),(390,'待完成：MOI原生执行、独立公网预览'),(500,'价值主张待真实客户验证，不编造ROI')]:text(d,s,(70,y),34,color=BG,width=950)
    elif scene['id']=='export':
        with pymupdf.open(BROWSER/'approved.pdf') as doc:
            pix=doc[0].get_pixmap(matrix=pymupdf.Matrix(2,2));paper=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        paper=paper.crop((50,20,1120,860));paper.thumbnail((VW-30,VH-20));panel.paste(paper,((VW-paper.width)//2,5))
    path=OUT/(scene['id']+'-screen.png');panel.save(path);return path,0,0


def run(cmd,log):
    with open(log,'w') as file:subprocess.run(cmd,stdout=file,stderr=subprocess.STDOUT,check=True)

def srt_time(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'

def build():
    assert sum(s['duration'] for s in STORY['scenes'])==180
    raw=sorted((ROOT/'raw').glob('*.webm'));clips=[];subs=[];ass=[];n=0
    for i,scene in enumerate(STORY['scenes']):
        background=base(scene,i);bfile=OUT/(scene['id']+'-base.png');background.save(bfile)
        if scene['id'] in ('opening','platform','closing','export'):screen,sy,ey=custom(scene)
        else:screen,sy,ey=screenshot(scene)
        duration=scene['duration'];target=OUT/(scene['id']+'.mp4')
        # Three short real screencast inserts; other scenes pan across actual screenshots.
        mode={'upload':(0,.9,1.4,6),'supplier':(1,1.6,6.5,4),'approval':(0,10.7,12.9,7)}.get(scene['id'])
        cmd=['ffmpeg','-v','error','-y','-loop','1','-i',str(bfile)]
        if mode and raw:
            rid,begin,end,speed=mode;cmd+=['-ss',str(begin),'-t',str(end-begin),'-i',str(raw[rid])]
            filt=f'[1:v]setpts={speed}*(PTS-STARTPTS),crop=1188:1000:252:0,scale={VW}:{VH}:force_original_aspect_ratio=decrease,pad={VW}:{VH}:(ow-iw)/2:(oh-ih)/2:color=0xf5f1e8,tpad=stop_mode=clone:stop_duration={duration},fps=24[screen];'
        else:
            cmd+=['-loop','1','-i',str(screen)]
            filt=f"[1:v]crop={VW}:{VH}:0:'min(ih-{VH},{sy}+({ey}-{sy})*t/{duration})',fps=24[screen];"
        filt+=f'[0:v][screen]overlay={X}:{Y},fade=t=in:st=0:d=0.45,fade=t=out:st={duration-.45}:d=0.45,format=yuv420p[v]'
        cmd+=['-filter_complex',filt,'-map','[v]','-t',str(duration),'-r','24','-c:v','libx264','-preset','veryfast','-crf','22','-threads','2','-an',str(target)]
        run(cmd,OUT/(scene['id']+'.log'));clips.append(target)
        # Full narration as readable subtitles, apportioned by text length in each scene.
        phrases=[p for p in re.split(r'(?<=[。！？；])',scene['narration']) if p];elapsed=scene['start']+.4;usable=duration-.9;count=sum(len(p) for p in phrases)
        for phrase in phrases:
            length=usable*len(phrase)/count;n+=1;rows=wrap(phrase,42,1710)
            subs.append(f'{n}\n{srt_time(elapsed)} --> {srt_time(elapsed+length-.06)}\n'+ '\n'.join(rows)+'\n');ass.append((elapsed,elapsed+length-.06,rows));elapsed+=length
    def ass_time(t):
        c=round(t*100);return f'{c//360000}:{c//6000%60:02d}:{c//100%60:02d}.{c%100:02d}'
    ass_header='[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,QuotePilot Sans,42,&H00F5F1E8,&H00F5F1E8,&H0010292D,&H0010292D,0,0,0,0,100,100,0,0,1,1,0,2,100,100,86,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    events=[]
    for a,b,rows in ass:events.append('Dialogue: 0,'+ass_time(a)+','+ass_time(b)+',Default,,0,0,0,,'+r'\N'.join(rows))
    (ROOT/'narration.ass').write_text(ass_header+'\n'.join(events)+'\n')
    (ROOT/'narration.srt').write_text('\n'.join(subs));(ROOT/'narration.txt').write_text('\n\n'.join(s['narration'] for s in STORY['scenes']))
    (OUT/'concat.txt').write_text(''.join("file '"+str(p.resolve())+"'\n" for p in clips))
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-c','copy',str(ROOT/'picture.mp4')],OUT/'concat.log')
    # Original low-volume synthesis, no third-party recording/song.
    audio='aevalsrc=0.014*sin(2*PI*130.8128*t)+0.009*sin(2*PI*196*t)+0.006*sin(2*PI*261.6256*t):s=48000:d=180'
    style="FontName=QuotePilot Sans,FontSize=24,PrimaryColour=&H00F5F1E8,OutlineColour=&H0010292D,BorderStyle=1,Outline=1,MarginV=32,Alignment=2"
    run(['ffmpeg','-v','error','-y','-i',str(ROOT/'picture.mp4'),'-f','lavfi','-i',audio,'-vf',f"ass={ROOT/'narration.ass'}:fontsdir={FONT.parent}",'-af','afade=t=in:d=3,afade=t=out:st=176:d=4','-c:v','libx264','-preset','veryfast','-crf','22','-threads','2','-c:a','aac','-b:a','128k','-t','180','-movflags','+faststart',str(ROOT/'QuotePilot_180s_subtitled.mp4')],OUT/'final.log')
    movie=ROOT/'QuotePilot_180s_subtitled.mp4';metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]));duration=float(metadata['format']['duration']);assert abs(duration-180)<.15
    video=next(s for s in metadata['streams'] if s['codec_type']=='video');assert (video['width'],video['height'])==(1920,1080)
    report={'duration_seconds':duration,'width':video['width'],'height':video['height'],'fps':video['r_frame_rate'],'sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'bytes':movie.stat().st_size,'synthetic_business_data':True,'product_ui_sources':'real local browser screenshots and two actual screencasts','native_workflow_claim':'not executed: HTTP400 / no execution ID','public_preview_claim':'not deployed','voiceover':False,'voice_blocker':'Edge TTS certificate validation failed; no TLS verification disabled, no paid voice service used','audio':'original low-volume synthesized tones; no third-party song','subtitle_file':'narration.srt','scenes':len(STORY['scenes'])}
    Path('evidence/sprint-p2/video-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':build()
