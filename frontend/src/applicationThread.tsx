import React, { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, CalendarClock, MessageCircle, Send } from "lucide-react";
import {
  ApplicationMessage,
  Interview,
  getApplicationInterviews,
  getApplicationMessages,
  getMe,
  getMyEmployers,
  scheduleInterview,
  sendApplicationMessage
} from "./api";
import "./portal.css";

function ApplicationThread(){
  const applicationId=Number(new URLSearchParams(location.search).get("id"));
  const [messages,setMessages]=useState<ApplicationMessage[]>([]);
  const [interviews,setInterviews]=useState<Interview[]>([]);
  const [body,setBody]=useState("");
  const [canSchedule,setCanSchedule]=useState(false);
  const [startsAt,setStartsAt]=useState("");
  const [interviewLocation,setInterviewLocation]=useState("");
  const [note,setNote]=useState("");
  const [error,setError]=useState("");

  async function refresh(){
    if(!applicationId){setError("缺少申请编号");return;}
    try{
      const [m,i]=await Promise.all([
        getApplicationMessages(applicationId),
        getApplicationInterviews(applicationId)
      ]);
      setMessages(m);setInterviews(i);
    }catch(e){setError(e instanceof Error?e.message:"加载失败");}
  }

  useEffect(()=>{
    (async()=>{
      try{
        await getMe();
        const employers=await getMyEmployers().catch(()=>[]);
        setCanSchedule(employers.length>0);
        await refresh();
      }catch{
        window.location.href="/auth.html";
      }
    })();
  },[]);

  async function send(e:FormEvent){
    e.preventDefault();
    if(!body.trim())return;
    try{
      await sendApplicationMessage(applicationId,body.trim());
      setBody("");
      await refresh();
    }catch(e){setError(e instanceof Error?e.message:"发送失败");}
  }

  async function schedule(e:FormEvent){
    e.preventDefault();
    try{
      await scheduleInterview(applicationId,{
        starts_at:startsAt,
        location:interviewLocation,
        meeting_url:"",
        note
      });
      setStartsAt("");setInterviewLocation("");setNote("");
      await refresh();
    }catch(e){setError(e instanceof Error?e.message:"安排失败");}
  }

  return <div className="portalShell">
    <header className="portalTop"><button className="iconOnly" onClick={()=>history.back()}><ArrowLeft/></button><strong>招聘沟通</strong><span/></header>
    <main className="portalMain">
      {error&&<div className="errorBox">{error}</div>}
      <section>
        <div className="sectionMiniTitle"><CalendarClock/> 面试安排</div>
        {!interviews.length&&<div className="portalCard compactMuted">暂时没有面试安排</div>}
        {interviews.map(i=><article className="portalCard interviewCard" key={i.id}>
          <b>{new Date(i.starts_at).toLocaleString()}</b>
          <span>📍 {i.location||"地点待确认"}</span>
          {i.note&&<p>{i.note}</p>}
        </article>)}
      </section>

      {canSchedule&&<form className="portalCard formGrid" onSubmit={schedule}>
        <div className="stepTitle"><CalendarClock/> 安排面试</div>
        <label>时间<input type="datetime-local" value={startsAt} onChange={(e)=>setStartsAt(e.target.value)} required/></label>
        <label>地点<input value={interviewLocation} onChange={(e)=>setInterviewLocation(e.target.value)} placeholder="Factory HR Office" required/></label>
        <label>备注<textarea value={note} onChange={(e)=>setNote(e.target.value)} rows={2} placeholder="需要携带的资料等"/></label>
        <button className="primaryWide">确认面试</button>
      </form>}

      <section>
        <div className="sectionMiniTitle"><MessageCircle/> 消息</div>
        <div className="messageThread">
          {!messages.length&&<div className="portalCard compactMuted">还没有消息</div>}
          {messages.map(m=><div className="messageBubble" key={m.id}>
            <div><b>{m.sender_name||"User"}</b><small>{new Date(m.created_at).toLocaleString()}</small></div>
            <p>{m.body}</p>
          </div>)}
        </div>
        <form className="messageComposer" onSubmit={send}>
          <input value={body} onChange={(e)=>setBody(e.target.value)} placeholder="输入消息..." maxLength={4000}/>
          <button><Send/></button>
        </form>
      </section>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><ApplicationThread/></React.StrictMode>);
