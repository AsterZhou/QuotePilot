"""No-key Chinese voice generation, using environment CA without disabling TLS."""
import asyncio,json,os,ssl,hashlib,subprocess
from pathlib import Path
import edge_tts,edge_tts.communicate as communicate
async def main():
    communicate._SSL_CTX=ssl.create_default_context()
    story=json.loads(Path('media/final_storyboard.json').read_text());root=Path('tmp/final-video/voice');root.mkdir(parents=True,exist_ok=True);rows=[]
    for scene in story['scenes']:
        target=root/(scene['id']+'.mp3')
        try:
            await edge_tts.Communicate(scene['narration'],story['voice'],rate='+5%',proxy=os.environ.get('HTTPS_PROXY')).save(str(target))
            duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(target)]))
            rows.append({'scene':scene['id'],'success':True,'duration_seconds':duration,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        except Exception as e:rows.append({'scene':scene['id'],'success':False,'error_type':type(e).__name__,'reason':str(e)[:500]});break
    Path('evidence/final-p2/voice-generation.json').write_text(json.dumps({'voice':story['voice'],'tls_verified':True,'api_key_required':False,'synthesized_voice':True,'results':rows},ensure_ascii=False,indent=2)+'\n');print(json.dumps({'successes':sum(x['success'] for x in rows),'scenes':len(story['scenes'])}))
if __name__=='__main__':asyncio.run(main())
