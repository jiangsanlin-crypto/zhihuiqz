import json,os,sqlite3,threading
from datetime import datetime,timezone

def now(): return datetime.now(timezone.utc).isoformat()

class StateStore:
    def __init__(self,path:str):
        os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
        self.path=path; self.lock=threading.Lock(); self._init()
    def conn(self):
        c=sqlite3.connect(self.path,timeout=30,isolation_level=None); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self.conn() as c:
            c.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS events(
              delivery_id TEXT PRIMARY KEY,event_name TEXT,payload_json TEXT,status TEXT DEFAULT 'queued',
              attempts INTEGER DEFAULT 0,error TEXT,created_at TEXT,updated_at TEXT);""")
    def enqueue(self,did,event,payload):
        t=now()
        with self.lock,self.conn() as c:
            cur=c.execute("""INSERT OR IGNORE INTO events(delivery_id,event_name,payload_json,status,attempts,created_at,updated_at)
            VALUES(?,?,?,'queued',0,?,?)""",(did,event,json.dumps(payload),t,t)); return cur.rowcount==1
    def claim_next(self):
        with self.lock,self.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            r=c.execute("SELECT * FROM events WHERE status IN ('queued','retry') ORDER BY created_at LIMIT 1").fetchone()
            if not r: c.execute("COMMIT"); return None
            c.execute("UPDATE events SET status='running',attempts=attempts+1,updated_at=? WHERE delivery_id=?",(now(),r["delivery_id"]))
            c.execute("COMMIT")
            return {"delivery_id":r["delivery_id"],"event_name":r["event_name"],"payload":json.loads(r["payload_json"]),"attempts":r["attempts"]+1}
    def finish(self,did,status,error=None):
        with self.lock,self.conn() as c:
            c.execute("UPDATE events SET status=?,error=?,updated_at=? WHERE delivery_id=?",(status,error,now(),did))
