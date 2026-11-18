"""Retained independent official evidence, separate from provider packets.
Only called from a failed historical revision gate, never a full-run retry.
"""
import hashlib,json,subprocess,sys,urllib.request,urllib.error
from pathlib import Path
from .jpx_decisions import Evidence,IntegrityError

def load(cells,archive,*,allow_network=True):
    if archive is None:raise IntegrityError('independent evidence requires acquisition archive')
    if getattr(archive,'network_fallback_allowed',True) is False:allow_network=False
    root=archive.directory/'jpx-evidence';root.mkdir(exist_ok=True)
    by_date={}
    for c in cells:by_date.setdefault(c['session'],set()).add(c['symbol'])
    result={};failures={}
    # Bounded work: excessive request scope is held rather than unbounded fetch.
    if len(by_date)>20:return {},{'scope':'more than 20 independent report dates; manual review required'}
    for day,symbols in sorted(by_date.items()):
        compact=day.replace('-','');url=f'https://www.jpx.co.jp/automation/markets/statistics-equities/daily/files/{compact[:6]}/stq_{compact}.pdf'
        pdf=root/f'stq_{compact}.pdf';receipt=pdf.with_suffix('.source.json')
        if pdf.exists():
            if not receipt.exists():raise IntegrityError('retained JPX PDF missing provenance')
            saved=json.loads(receipt.read_text(encoding='utf-8'))
            if saved.get('url')!=url or saved.get('sha256')!=hashlib.sha256(pdf.read_bytes()).hexdigest():raise IntegrityError('retained JPX evidence bytes/provenance mismatch')
        elif allow_network:
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Cloud-source-quality/1.0'}),timeout=30) as response:
                    if response.geturl()!=url:raise IntegrityError('unexpected independent source redirect')
                    raw=response.read(20*1024*1024+1)
                if len(raw)>20*1024*1024 or not raw.startswith(b'%PDF-'):raise IntegrityError('invalid independent PDF response')
                # Exclusive create never overwrites retained evidence.
                with pdf.open('xb') as f:f.write(raw)
                receipt.write_text(json.dumps({'url':url,'sha256':hashlib.sha256(raw).hexdigest()}),encoding='utf-8')
            except (urllib.error.URLError,TimeoutError) as exc:
                failures[day]=f'official source unavailable: {type(exc).__name__}';continue
        else:
            failures[day]='independent PDF not retained; network disabled';continue
        try:
            # Existing system Python has fitz; no dependency installation.
            p=subprocess.run(['py','-3','-B',str(Path(__file__).with_name('jpx_pdf_extract.py')),str(pdf),day,*sorted(symbols)],capture_output=True,text=True,encoding='utf-8',timeout=45,check=True)
            parsed=json.loads(p.stdout)
        except (OSError,subprocess.SubprocessError,ValueError) as exc:
            failures[day]=f'independent PDF extraction unavailable: {type(exc).__name__}';continue
        sha=hashlib.sha256(pdf.read_bytes()).hexdigest()
        if parsed.get('pdf_sha256')!=sha or parsed.get('date')!=day:raise IntegrityError('independent extraction provenance mismatch')
        for symbol,row in parsed['rows'].items():
            if symbol not in symbols or row['symbol']!=symbol or row['date']!=day or row['pdf_sha256']!=sha:raise IntegrityError('independent extracted identity mismatch')
            for field,value in row['values'].items():
                ev=Evidence(symbol,day,field,value,url,sha,row['page'],'shares' if field=='volume' else 'JPY',row['basis'],row['open_kind'] if field=='open' else '',True)
                ev.check();result[(symbol,day,field)]=ev
        (root/f'stq_{compact}.extraction.json').write_text(json.dumps(parsed,ensure_ascii=True,indent=2),encoding='utf-8')
    return result,failures

