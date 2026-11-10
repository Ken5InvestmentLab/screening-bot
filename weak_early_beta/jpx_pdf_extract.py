"""Read-only JPX stq two-session-layout parser. Run with existing py+fitz.
Unknown layouts/no-trade rows yield unavailable evidence, never guessed prices.
No downloads, writes or detection are performed by this helper.
"""
import hashlib,json,re,sys
from pathlib import Path
from datetime import date
from decimal import Decimal

def parse(path,session,symbols):
 import fitz
 raw=Path(path).read_bytes();sha=hashlib.sha256(raw).hexdigest();day=date.fromisoformat(session)
 doc=fitz.open(stream=raw,filetype='pdf');out={};ambiguous=set();domestic=False
 for page_no,page in enumerate(doc,1):
  words=page.get_text('words');text=page.get_text()
  if 'Domestic Stock' in text:domestic=True
  if any(t in text for t in ('Foreign Stock','Investment Trust','Exchange Traded','REIT','ETF')):domestic=False
  # Conservative recognized domestic industry page; unsupported continuation
  # layouts are held, not assigned a currency or security class by guess.
  if not domestic or not any(w[4] in {'水産・農林業','鉱業','建設業','食料品','繊維製品','パルプ・紙','化学','医薬品','石油・石炭製品','ゴム製品','ガラス・土石製品','鉄鋼','非鉄金属','金属製品','機械','電気機器','輸送用機器','精密機器','その他製品','電気・ガス業','陸運業','海運業','空運業','倉庫・運輸関連業','情報・通信業','卸売業','小売業','銀行業','証券、商品先物取引業','保険業','その他金融業','不動産業','サービス業'} and 140<w[1]<165 for w in words):continue
  if f'{day.year}年{day.month}月{day.day}日' not in text:continue
  if not ('morning' in text and 'afternoon' in text):continue
  # Explicit headers pin the recognized two-session numeric column schema.
  expected=[('Open',304),('High',365),('Low',426),('Close',484),('Open',544),('High',605),('Low',666),('Close',724)]
  if any(len([w for w in words if w[4]==label and abs(w[0]-x)<3 and 114<w[1]<122])!=1 for label,x in expected):continue
  if any(len([w for w in words if w[4]=='円[￥]' and abs(w[0]-x)<3 and 128<w[1]<134])!=1 for x in (326,386,446,506,566,626,686,746)):continue
  for symbol in symbols:
   ids=[w for w in words if w[4]==symbol and 70<w[0]<100 and w[1]>150]
   if not ids:continue
   if len(ids)!=1 or symbol in out:ambiguous.add(symbol);continue
   row=[w for w in words if abs(w[1]-ids[0][1])<1]
   cells=[]
   for lo in (283,343,403,463,523,583,643,703):
    found=[w for w in row if lo<w[0] and w[2]<lo+61 and re.fullmatch(r'[0-9,]+(?:\.[0-9]+)?',w[4])]
    if len(found)!=1:break
    cells.append(found[0])
   if len(cells)!=8:continue  # missing/no-trade session is not guessed
   am=list(map(lambda w:Decimal(w[4].replace(',','')),cells[:4]));pm=list(map(lambda w:Decimal(w[4].replace(',','')),cells[4:]))
   if any(v<=0 for v in am+pm) or not(am[2]<=min(am[0],am[3])<=max(am[0],am[3])<=am[1]) or not(pm[2]<=min(pm[0],pm[3])<=max(pm[0],pm[3])<=pm[1]):continue
   out[symbol]={'symbol':symbol,'date':session,'page':page_no,'pdf_sha256':sha,'basis':'actual_session_units','price_units':'JPY','section_verification':'domestic stock recognized industry header','values':{'open':str(am[0]),'high':str(max(am[1],pm[1])),'low':str(min(am[2],pm[2])),'close':str(pm[3])},'open_kind':'morning_first_trade','coordinates':[list(w[:5]) for w in cells], 'volume_status':'unavailable: common-stock units classification not independently verified'}
 for symbol in ambiguous:out.pop(symbol,None)
 return {'identity':'CLOUD_JPX_PARSED_REPORT_V1','pdf_sha256':sha,'date':session,'rows':out}
if __name__=='__main__':
 print(json.dumps(parse(sys.argv[1],sys.argv[2],sys.argv[3:]),ensure_ascii=True))

