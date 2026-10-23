from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib, json, time, urllib.request, urllib.error, threading
from urllib.parse import urlencode
import os, base64, hmac
from datetime import datetime
from zoneinfo import ZoneInfo

PORT = int(os.environ.get('PORT', '8765'))
HOST = os.environ.get('HOST', '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1')
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD', '')
if HOST not in ('127.0.0.1', 'localhost', '::1') and not DASHBOARD_PASSWORD:
    raise SystemExit('Set DASHBOARD_PASSWORD before exposing this app on a public host.')
ENDPOINT = 'https://open-api.affiliate.shopee.vn/graphql'
monitor_lock = threading.Lock()
monitor_state = {'running': False, 'message': 'Chưa bật theo dõi', 'last_checked': None, 'error': None}
monitor_stop = None
VN_TZ = ZoneInfo('Asia/Ho_Chi_Minh')

PAGE = r'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Báo cáo chuyển đổi Shopee</title>
<style>
:root{--ink:#17251f;--muted:#718078;--line:#e3eae5;--green:#13845a;--pale:#f1f7f3;--orange:#ee5a35}*{box-sizing:border-box}body{margin:0;background:#f7f9f7;color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{max-width:1440px;margin:auto;padding:32px 24px}.head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:24px}.eyebrow{color:var(--green);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.1em}.head h1{margin:5px 0;font-size:30px;letter-spacing:-.04em}.head p{margin:0;color:var(--muted)}.pill{border:1px solid var(--line);border-radius:99px;padding:8px 12px;color:#53635a;background:white;font-size:12px}.panel{background:white;border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:18px;box-shadow:0 4px 16px #18271d08}.panel h2{font-size:16px;margin:0 0 14px}.grid{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:12px}.field label{display:block;font-size:12px;color:var(--muted);margin-bottom:6px}.field input,.field select{width:100%;height:42px;border:1px solid var(--line);border-radius:9px;padding:0 11px;font:inherit;color:var(--ink);background:white}.field.wide{grid-column:span 2}.actions{display:flex;align-items:center;gap:12px;margin-top:16px}.button{border:0;border-radius:9px;background:var(--green);color:white;font-weight:700;padding:12px 18px;font:inherit;cursor:pointer}.button:disabled{opacity:.55;cursor:wait}.hint{color:var(--muted);font-size:12px}.error{color:#b83325;background:#fff1ee;border-radius:9px;padding:12px;display:none;margin-top:14px;white-space:pre-wrap}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}.stat{background:var(--pale);border-radius:12px;padding:16px}.stat span{display:block;color:var(--muted);font-size:12px}.stat strong{font-size:22px;display:block;margin-top:4px}.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:12px}table{width:100%;border-collapse:collapse;min-width:1120px}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;background:#fafcfb}td{font-size:13px}tr:last-child td{border-bottom:0}.product{font-weight:650;max-width:260px}.sub{color:var(--muted);font-size:11px;margin-top:3px}.status{display:inline-block;border-radius:30px;padding:4px 8px;background:#f1f3f2;font-size:11px}.approved{color:#14754d;background:#e7f5ec}.pending{color:#9b6814;background:#fff4d8}.rejected{color:#ad3d31;background:#ffeeeb}.bottom{display:flex;justify-content:space-between;align-items:center;margin-top:14px}.pager{display:flex;gap:8px}.secondary{border:1px solid var(--line);background:white;border-radius:8px;padding:8px 12px;cursor:pointer}.secondary:disabled{opacity:.45}.empty{text-align:center;color:var(--muted);padding:42px}.foot{color:var(--muted);font-size:12px;margin:20px 2px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(120px,1fr))}.field.wide{grid-column:span 2}.head{gap:12px;flex-direction:column}.stats{grid-template-columns:1fr}}
</style></head><body><main class="wrap"><header class="head"><div><div class="eyebrow">Shopee Affiliate · Open API</div><h1>Báo cáo chuyển đổi</h1><p>Xem đơn hàng và hoa hồng trực tiếp trong trình duyệt.</p></div><div class="pill">Dữ liệu lấy từ API Shopee</div></header>
<section class="panel"><h2>Kết nối và bộ lọc</h2><form id="form"><div class="grid">
<div class="field"><label>App ID</label><input id="appId" required inputmode="numeric" placeholder="App ID" autocomplete="off"></div>
<div class="field wide"><label>App Secret</label><input id="secret" required type="password" placeholder="Secret API" autocomplete="new-password"></div>
<div class="field"><label>Trạng thái đơn</label><select id="status"><option value="">Tất cả</option><option value="0">Chờ xác nhận</option><option value="1">Đã duyệt</option><option value="2">Bị từ chối</option></select></div>
<div class="field"><label>Từ ngày</label><input id="from" type="date" required></div><div class="field"><label>Đến ngày</label><input id="to" type="date" required></div>
<div class="field"><label>Số dòng mỗi trang</label><select id="limit"><option>10</option><option>20</option><option>50</option><option>100</option></select></div>
</div><div class="actions"><button id="submit" class="button">Lấy báo cáo</button><span id="busy" class="hint"></span><span class="hint">Thông tin xác thực không được lưu.</span></div><div id="error" class="error"></div></form></section>
<section class="panel"><h2>Thông báo về điện thoại qua Telegram</h2><p class="hint">Tạo bot bằng @BotFather, mở bot và gửi /start. Kiểm tra AddLiveTag mỗi 15 giây, gửi khi phát hiện số đơn/hoa hồng đổi.</p><div class="grid" style="grid-template-columns:repeat(4,minmax(140px,1fr))"><div class="field wide"><label>AddLiveTag API Key</label><input id="addliveKey" type="password" placeholder="API key 48 ký tự" autocomplete="off"></div><div class="field"><label>Account ID (không bắt buộc)</label><input id="accountId" placeholder="Tất cả tài khoản"></div><div class="field wide"><label>Telegram Bot Token</label><input id="botToken" type="password" placeholder="123456:ABC…" autocomplete="off"></div><div class="field"><label>Chat ID</label><input id="chatId" placeholder="Tự tìm sau khi gửi /start" autocomplete="off"></div></div><div class="actions"><button id="findChat" type="button" class="secondary">Tìm Chat ID</button><button id="testTelegram" type="button" class="secondary">Gửi tin nhắn thử</button><button id="startMonitor" type="button" class="button">Bắt đầu gửi về điện thoại</button><button id="stopMonitor" type="button" class="secondary">Dừng</button><span id="monitorStatus" class="hint">Chưa bật theo dõi</span></div><div id="telegramHelp" class="hint" style="margin-top:10px">Telegram nhận tổng số đơn và hoa hồng ngay khi phát hiện chuyển đổi mới hoặc thay đổi trong ngày. Ngày chưa có đơn vẫn gửi tổng kết 0 đơn khi bắt đầu theo dõi và khi sang ngày mới. Không có GMV trong tin nhắn.</div></section>
<div class="stats"><div class="stat"><span>Số dòng trang này</span><strong id="count">—</strong></div><div class="stat"><span>Tổng hoa hồng hiển thị</span><strong id="commission">—</strong></div><div class="stat"><span>Trang</span><strong id="pageLabel">—</strong></div></div>
<section class="panel"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px"><h2 style="margin:0">Chi tiết đơn hàng</h2><button id="csv" class="secondary" disabled>Xuất CSV</button></div><div class="tablewrap"><table><thead><tr><th>Đơn hàng</th><th>Sản phẩm</th><th>Cửa hàng</th><th>SL</th><th>Giá</th><th>Hoa hồng</th><th>Thực nhận</th><th>Trạng thái</th><th>Thời gian mua</th><th>Sub ID</th></tr></thead><tbody id="rows"><tr><td colspan="10" class="empty">Nhập thông tin API và chọn khoảng ngày để bắt đầu.</td></tr></tbody></table></div><div class="bottom"><span id="pageInfo" class="hint"></span><div class="pager"><button id="prev" class="secondary" disabled>← Trước</button><button id="next" class="secondary" disabled>Tiếp →</button></div></div></section><div class="foot">Múi giờ ngày lọc theo trình duyệt của bạn. Hoa hồng được hiển thị theo giá trị API trả về. App Secret chỉ được gửi tới ứng dụng cục bộ này để ký request; không ghi vào file hay gửi sang dịch vụ trung gian.</div></main>
<script>
const $=id=>document.getElementById(id);let currentPage=1,hasNext=false,lastRows=[];
const day=d=>{const x=new Date(d);return new Date(x.getTime()-x.getTimezoneOffset()*60000).toISOString().slice(0,10)};
const now=new Date();$('to').value=day(now);const start=new Date(now);start.setDate(start.getDate()-6);$('from').value=day(start);
function money(v){if(v==null)return '—';const n=Number(v);return Number.isFinite(n)?new Intl.NumberFormat('vi-VN').format(n):String(v)}
function dateTime(v){if(!v)return '—';const d=new Date(Number(v)*1000);return Number.isNaN(+d)?'—':d.toLocaleString('vi-VN')}
function status(v){const names={0:['Chờ xác nhận','pending'],1:['Đã duyệt','approved'],2:['Bị từ chối','rejected']};const x=names[v]||[String(v??'—'),''];return `<span class="status ${x[1]}">${x[0]}</span>`}
function esc(v){return String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function csv(){const cols=['orderId','checkoutId','itemId','itemName','shopId','shopName','quantity','price','commission','netCommission','campaignType','purchaseStatus','itemStatus','purchaseTime','clickTime','subIds'];const q=v=>'"'+String(v??'').replaceAll('"','""')+'"';let lines=[cols.join(','),...lastRows.map(r=>cols.map(k=>q(Array.isArray(r[k])?r[k].join('|'):r[k])).join(','))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));a.download=`shopee-conversion-page-${currentPage}.csv`;a.click();URL.revokeObjectURL(a.href)}
$('csv').onclick=csv;
async function load(page){$('error').style.display='none';$('error').textContent='';$('submit').disabled=true;$('busy').textContent='Đang truy vấn…';try{const payload={appId:$('appId').value.trim(),secret:$('secret').value,startTime:Math.floor(new Date($('from').value+'T00:00:00').getTime()/1000),endTime:Math.floor(new Date($('to').value+'T23:59:59').getTime()/1000),purchaseStatus:$('status').value===''?null:Number($('status').value),page,limit:Number($('limit').value)};if(!Number.isFinite(payload.startTime)||!Number.isFinite(payload.endTime)||payload.startTime>payload.endTime)throw Error('Khoảng ngày không hợp lệ.');const res=await fetch('/api/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await res.json();if(!res.ok)throw Error(data.error||`Lỗi HTTP ${res.status}`);const root=data.data?.conversionReportV2;if(!root)throw Error(JSON.stringify(data.errors||data));currentPage=page;lastRows=root.nodes||[];hasNext=!!root.pageInfo?.hasNextPage;draw(lastRows,root.pageInfo||{});}catch(e){$('error').textContent=e.message||String(e);$('error').style.display='block'}finally{$('submit').disabled=false;$('busy').textContent=''}}
function draw(rows,info){$('count').textContent=rows.length;$('commission').textContent=money(rows.reduce((a,r)=>a+Number(r.netCommission??r.commission??0),0));$('pageLabel').textContent=info.page??currentPage;$('pageInfo').textContent=`Trang ${info.page??currentPage} · ${info.limit??rows.length} dòng/trang`;$('prev').disabled=currentPage<=1;$('next').disabled=!hasNext;$('csv').disabled=!rows.length;if(!rows.length){$('rows').innerHTML='<tr><td colspan="10" class="empty">Không có dữ liệu trong trang này.</td></tr>';return}$('rows').innerHTML=rows.map(r=>`<tr><td>${esc(r.orderId)}<div class="sub">Thanh toán: ${esc(r.checkoutId)}</div></td><td><div class="product">${esc(r.itemName)}</div><div class="sub">ID ${esc(r.itemId)} · ${esc(r.campaignType)}</div></td><td>${esc(r.shopName)}<div class="sub">ID ${esc(r.shopId)}</div></td><td>${esc(r.quantity)}</td><td>${money(r.price)}</td><td>${money(r.commission)}</td><td>${money(r.netCommission)}</td><td>${status(r.purchaseStatus)}</td><td>${dateTime(r.purchaseTime)}<div class="sub">Nhấp: ${dateTime(r.clickTime)}</div></td><td>${esc(Array.isArray(r.subIds)?r.subIds.join(', '):r.subIds)}</td></tr>`).join('')}
$('form').addEventListener('submit',e=>{e.preventDefault();load(1)});$('prev').onclick=()=>load(currentPage-1);$('next').onclick=()=>load(currentPage+1);
async function post(url,data){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Error(d.error||'Yêu cầu thất bại');return d}
$('findChat').onclick=async()=>{try{$('telegramHelp').textContent='Đang tìm…';const d=await post('/api/telegram/chat-id',{token:$('botToken').value.trim()});$('chatId').value=d.chat_id;$('telegramHelp').textContent='Đã tìm thấy Chat ID. Hãy gửi tin nhắn thử để xác nhận.'}catch(e){$('telegramHelp').textContent=e.message}};
$('testTelegram').onclick=async()=>{try{$('telegramHelp').textContent='Đang gửi tin nhắn thử…';await post('/api/telegram/test',{token:$('botToken').value.trim(),chat_id:$('chatId').value.trim()});$('telegramHelp').textContent='Đã gửi. Kiểm tra Telegram trên điện thoại.'}catch(e){$('telegramHelp').textContent=e.message}};
$('startMonitor').onclick=async()=>{try{const p={api_key:$('addliveKey').value.trim(),account_id:$('accountId').value.trim(),token:$('botToken').value.trim(),chat_id:$('chatId').value.trim()};const d=await post('/api/monitor/start',p);$('monitorStatus').textContent=d.message;statusTimer=setInterval(refreshMonitorStatus,10000)}catch(e){$('monitorStatus').textContent=e.message}};
$('stopMonitor').onclick=async()=>{try{const d=await post('/api/monitor/stop',{});$('monitorStatus').textContent=d.message;clearInterval(statusTimer)}catch(e){$('monitorStatus').textContent=e.message}};
let statusTimer=null;async function refreshMonitorStatus(){try{const d=await (await fetch('/api/monitor/status')).json();$('monitorStatus').textContent=d.message+(d.last_checked?' · kiểm tra lúc '+new Date(d.last_checked*1000).toLocaleTimeString('vi-VN'):'')+(d.error?' · lỗi: '+d.error:'');if(!d.running)clearInterval(statusTimer)}catch(e){}}

</script></body></html>'''

QUERY = '''query {
  conversionReportV2(startTime: %d, endTime: %d%s, page: %d, limit: %d) {
    nodes { orderId checkoutId itemId itemName shopId shopName quantity price commission netCommission campaignType purchaseStatus itemStatus purchaseTime clickTime subIds }
    pageInfo { page limit hasNextPage }
  }
}'''

def shopee_report(app_id, secret, start, end, page=1, limit=100, purchase_status=None):
    status_arg='' if purchase_status is None else ', purchaseStatus: '+str(int(purchase_status))
    query=QUERY%(int(start),int(end),status_arg,int(page),int(limit))
    payload=json.dumps({'query':query},ensure_ascii=False,separators=(',',':'))
    timestamp=str(int(time.time()))
    signature=hashlib.sha256((str(app_id)+timestamp+payload+str(secret)).encode()).hexdigest()
    auth=f'SHA256 Credential={app_id}, Signature={signature}, Timestamp={timestamp}'
    request=urllib.request.Request(ENDPOINT,data=payload.encode(),headers={'Authorization':auth,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=45) as response: result=json.loads(response.read().decode())
    if result.get('errors'): raise RuntimeError(json.dumps(result['errors'],ensure_ascii=False))
    return result.get('data',{}).get('conversionReportV2',{})

def telegram_call(token, method, data=None):
    url=f'https://api.telegram.org/bot{token}/{method}'
    payload=json.dumps(data or {}).encode()
    request=urllib.request.Request(url,data=payload,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=30) as response: result=json.loads(response.read().decode())
    if not result.get('ok'): raise RuntimeError(result.get('description','Telegram API lỗi'))
    return result.get('result')

def daily_conversion_summary(api_key, now, account_id=''):
    day_text=now.strftime('%Y-%m-%d')
    params={'type':'orders','source':'shopee','from':day_text,'to':day_text,'page':1,'page_size':50}
    if account_id: params['account_id']=account_id
    url='https://addlivetag.com/api/v1/conversions.php?'+urlencode(params)
    request=urllib.request.Request(url,headers={'X-API-Key':api_key,'Accept':'application/json'},method='GET')
    with urllib.request.urlopen(request,timeout=30) as response: result=json.loads(response.read().decode())
    if not result.get('ok'): raise RuntimeError(result.get('error') or result.get('message') or 'AddLiveTag API báo lỗi.')
    summary=result.get('summary') or {}
    order_count=int(summary.get('orders',result.get('meta',{}).get('total',0)) or 0)
    amount=summary.get('estimated_total_commission')
    if amount is None: amount=summary.get('gross_commission',0)
    commission=float(amount or 0)
    return order_count,commission

def format_vnd(value):
    return f'{value:,.0f}'.replace(',', '.')+' ₫'

def monitor_worker(config, stop_event):
    last_signature=None
    try:
        while not stop_event.is_set():
            now=datetime.now(VN_TZ)
            try:
                count,commission=daily_conversion_summary(config['api_key'],now,config.get('account_id',''))
                signature=(now.date(),count,commission)
                if signature!=last_signature:
                    date_text=now.strftime('%d/%m/%Y')
                    text=f'📊 Shopee hôm nay ({date_text})\nSố đơn: {count}\nTổng hoa hồng: {format_vnd(commission)}'
                    telegram_call(config['token'],'sendMessage',{'chat_id':config['chat_id'],'text':text})
                    last_signature=signature
                    with monitor_lock:
                        monitor_state.update(running=True,message='Đã gửi cập nhật chuyển đổi mới',last_checked=int(time.time()),error=None)
                else:
                    with monitor_lock:
                        monitor_state.update(running=True,message='Đang kiểm tra AddLiveTag mỗi 15 giây',last_checked=int(time.time()),error=None)
            except Exception as exc:
                with monitor_lock:
                    monitor_state.update(running=True,message='Đang thử lấy lại báo cáo',last_checked=int(time.time()),error=str(exc))
            if stop_event.wait(15): break
    finally:
        with monitor_lock:
            if monitor_stop is stop_event:
                monitor_state['running']=False
                if not monitor_state.get('error'): monitor_state['message']='Đã dừng theo dõi'

def telegram_error(e):
    if isinstance(e, urllib.error.HTTPError): return f'Telegram API trả lỗi {e.code}: {e.read().decode(errors="replace")}'
    if isinstance(e, urllib.error.URLError): return f'Không kết nối được Telegram: {e.reason}'
    return str(e)

class Handler(BaseHTTPRequestHandler):
    def authorized(self):
        if not DASHBOARD_PASSWORD: return True
        supplied=self.headers.get('Authorization','')
        expected='Basic '+base64.b64encode(('admin:'+DASHBOARD_PASSWORD).encode()).decode()
        if hmac.compare_digest(supplied,expected): return True
        self.send_response(401); self.send_header('WWW-Authenticate','Basic realm=Shopee Conversion Dashboard'); self.send_header('Content-Length','0'); self.end_headers(); return False
    def send_json(self, status, data):
        body=json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
    def read_json(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
    def do_GET(self):
        if not self.authorized(): return
        if self.path=='/api/monitor/status':
            with monitor_lock: data=dict(monitor_state)
            self.send_json(200,data); return
        if self.path not in ('/','/index.html'): self.send_error(404); return
        body=PAGE.encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        if not self.authorized(): return
        global monitor_stop
        try:
            req=self.read_json()
            if self.path=='/api/report':
                app_id=str(req['appId']).strip(); secret=str(req['secret']); start=int(req['startTime']); end=int(req['endTime']); page=int(req['page']); limit=int(req['limit']); status=req.get('purchaseStatus')
                if not app_id or not secret: raise ValueError('Vui lòng nhập App ID và App Secret.')
                if end<start or page<1 or limit<1 or limit>100: raise ValueError('Tham số ngày, trang hoặc giới hạn không hợp lệ (limit tối đa 100).')
                self.send_json(200,{'data':{'conversionReportV2':shopee_report(app_id,secret,start,end,page,limit,status)}}); return
            if self.path=='/api/telegram/chat-id':
                token=str(req['token']).strip()
                updates=telegram_call(token,'getUpdates',{'limit':100,'timeout':0})
                chats=[u.get('message',{}).get('chat') for u in updates if u.get('message',{}).get('chat')]
                if not chats: raise ValueError('Chưa thấy tin nhắn. Hãy mở bot trên Telegram, gửi /start rồi bấm tìm lại.')
                self.send_json(200,{'chat_id':str(chats[-1]['id'])}); return
            if self.path=='/api/telegram/test':
                telegram_call(str(req['token']).strip(),'sendMessage',{'chat_id':str(req['chat_id']).strip(),'text':'✅ Kết nối báo cáo Shopee thành công. Tin nhắn thử từ ứng dụng báo cáo.'})
                self.send_json(200,{'message':'Đã gửi tin nhắn thử'}); return
            if self.path=='/api/monitor/start':
                api_key=str(req['api_key']).strip(); account_id=str(req.get('account_id','')).strip(); token=str(req['token']).strip(); chat_id=str(req['chat_id']).strip()
                if not all((api_key,token,chat_id)): raise ValueError('Nhập AddLiveTag API Key, Telegram Bot Token và Chat ID.')
                with monitor_lock:
                    if monitor_stop: monitor_stop.set()
                    monitor_stop=threading.Event(); event=monitor_stop
                    monitor_state.update(running=True,message='Đang lấy báo cáo ban đầu…',last_checked=None,error=None)
                config={'api_key':api_key,'account_id':account_id,'token':token,'chat_id':chat_id}
                threading.Thread(target=monitor_worker,args=(config,event),daemon=True).start()
                self.send_json(200,{'message':'Đang bật theo dõi chuyển đổi trên máy tính'}); return
            if self.path=='/api/monitor/stop':
                with monitor_lock:
                    if monitor_stop: monitor_stop.set()
                    monitor_state.update(running=False,message='Đã dừng theo dõi')
                self.send_json(200,{'message':'Đã dừng theo dõi'}); return
            self.send_error(404)
        except urllib.error.HTTPError as e: self.send_json(e.code,{'error':telegram_error(e)})
        except urllib.error.URLError as e: self.send_json(502,{'error':telegram_error(e)})
        except Exception as e: self.send_json(400,{'error':str(e) or 'Yêu cầu không hợp lệ.'})
    def log_message(self, fmt,*args): pass

if __name__=='__main__':
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f'Mở ứng dụng tại http://{HOST}:{PORT}  (Ctrl+C để dừng)')
    try: server.serve_forever()
    except KeyboardInterrupt:
        if monitor_stop: monitor_stop.set()
        print('\nĐã dừng.')
