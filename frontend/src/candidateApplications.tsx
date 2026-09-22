import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, CalendarClock, CheckCircle2, MessageCircle } from "lucide-react";
import { CandidateApplication, getMe, getMyApplications } from "./api";
import "./portal.css";

const statusText:Record<string,string>={
  applied:"已报名",contacted:"企业已联系",interview:"面试中",offered:"已录用",joined:"已到岗",rejected:"未通过"
};

function CandidateApplications(){
  const [items,setItems]=useState<CandidateApplication[]>([]);
  const [message,setMessage]=useState("");

  useEffect(()=>{
    (async()=>{
      try{
        const me=await getMe();
        if(me.role!=="candidate"){window.location.href="/auth.html";return;}
        setItems(await getMyApplications());
      }catch(e){
        setMessage(e instanceof Error?e.message:"加载失败");
      }
    })();
  },[]);

  return <div className="portalShell">
    <header className="portalTop">
      <button className="iconOnly" onClick={()=>history.back()}><ArrowLeft/></button>
      <strong>我的申请</strong><span/>
    </header>
    <main className="portalMain">
      <div className="portalHero">
        <span className="miniBadge">Application Status</span>
        <h1>申请进度一眼看懂</h1>
        <p>报名、联系、面试、录用和到岗状态都集中在这里。</p>
      </div>
      {message&&<div className="errorBox">{message}</div>}
      <section className="applicantList">
        {!items.length&&<div className="portalCard centerState"><CheckCircle2/><h2>还没有申请记录</h2><p>找到合适的工作后，一键报名即可。</p></div>}
        {items.map(item=><article className="portalCard applicationHistory" key={item.id}>
          <div className="applicantHead">
            <div>
              <h2>{item.job_title_km||item.job_title_en||item.job_title_zh}</h2>
              <p>{item.employer_name}{item.employer_verified?" · ✓ 已认证":""}</p>
            </div>
            <span className={"applicationStatus "+item.status}>{statusText[item.status]||item.status}</span>
          </div>
          <div className="historyMeta">
            <span>📍 {item.location||"未填写地区"}</span>
            <span>⏱ {item.available_date||"到岗时间未填写"}</span>
            {item.latest_interview_at&&<span><CalendarClock/> {new Date(item.latest_interview_at).toLocaleString()}</span>}
          </div>
          <button className="primaryWide small" onClick={()=>window.location.href="/application.html?id="+item.id}>
            <MessageCircle/> 查看消息与面试
          </button>
        </article>)}
      </section>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><CandidateApplications/></React.StrictMode>);
