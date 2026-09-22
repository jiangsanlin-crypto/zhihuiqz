import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, Phone, UserRound } from "lucide-react";
import {
  EmployerApplication,
  getEmployerApplications,
  getMe,
  getMyEmployers,
  updateApplicationStatus
} from "./api";
import "./portal.css";

const labels:Record<string,string>={
  applied:"新报名",contacted:"已联系",interview:"面试",offered:"已录用",joined:"已到岗",rejected:"不合适"
};
const statuses=["all","applied","contacted","interview","offered","joined","rejected"];

function EmployerApplicants(){
  const [employerId,setEmployerId]=useState<number|null>(null);
  const [items,setItems]=useState<EmployerApplication[]>([]);
  const [filter,setFilter]=useState("all");
  const [message,setMessage]=useState("");

  async function load(id:number,status=filter){
    try{
      const data=await getEmployerApplications(id,status==="all"?undefined:status);
      setItems(data);
    }catch(e){setMessage(e instanceof Error?e.message:"加载失败");}
  }

  useEffect(()=>{
    (async()=>{
      try{
        const me=await getMe();
        if(me.role!=="employer_admin"&&me.role!=="platform_admin")throw new Error("unauthorized");
        const employers=await getMyEmployers();
        if(!employers.length){window.location.href="/employer-onboarding.html";return;}
        setEmployerId(employers[0].id);
        await load(employers[0].id,"all");
      }catch{window.location.href="/auth.html";}
    })();
  },[]);

  async function setStatus(id:number,status:string){
    if(!employerId)return;
    try{
      await updateApplicationStatus(id,status);
      await load(employerId,filter);
    }catch(e){setMessage(e instanceof Error?e.message:"更新失败");}
  }

  function actions(item:EmployerApplication){
    if(item.status==="applied")return <><button onClick={()=>setStatus(item.id,"contacted")}>标记已联系</button><button className="dangerBtn" onClick={()=>setStatus(item.id,"rejected")}>不合适</button></>;
    if(item.status==="contacted")return <><button onClick={()=>setStatus(item.id,"interview")}>进入面试</button><button className="dangerBtn" onClick={()=>setStatus(item.id,"rejected")}>不合适</button></>;
    if(item.status==="interview")return <><button onClick={()=>setStatus(item.id,"offered")}>录用</button><button className="dangerBtn" onClick={()=>setStatus(item.id,"rejected")}>不合适</button></>;
    if(item.status==="offered")return <><button onClick={()=>setStatus(item.id,"joined")}>确认到岗</button><button className="dangerBtn" onClick={()=>setStatus(item.id,"rejected")}>未到岗</button></>;
    return null;
  }

  async function changeFilter(next:string){
    setFilter(next);
    if(employerId)await load(employerId,next);
  }

  return <div className="portalShell">
    <header className="portalTop"><button className="iconOnly" onClick={()=>history.back()}><ArrowLeft/></button><strong>候选人管理</strong><span/></header>
    <main className="portalMain">
      <div className="portalHero"><span className="miniBadge">Recruiting Pipeline</span><h1>从报名到到岗</h1><p>让 HR 用最少步骤完成联系、面试、录用和到岗确认。</p></div>
      <div className="pipelineTabs">{statuses.map(s=><button key={s} className={filter===s?"active":""} onClick={()=>changeFilter(s)}>{s==="all"?"全部":labels[s]}</button>)}</div>
      {message&&<div className="errorBox">{message}</div>}
      <section className="applicantList">
        {!items.length&&<div className="portalCard centerState"><UserRound/><h2>暂无候选人</h2><p>职位收到报名后会出现在这里。</p></div>}
        {items.map(item=><article className="portalCard applicantCard" key={item.id}>
          <div className="applicantHead">
            <div><h2>{item.candidate_name}</h2><p>{item.job_title_zh||item.job_title_en||item.job_title_km}</p></div>
            <span className={"applicationStatus "+item.status}>{labels[item.status]||item.status}</span>
          </div>
          <div className="applicantMeta">
            <span><Phone/> {item.phone}</span>
            <span>📍 {item.location||"未填写地区"}</span>
            <span>⏱ {item.available_date||"未填写到岗时间"}</span>
          </div>
          {item.cv_url&&<a className="cvLink" href={item.cv_url} target="_blank" rel="noreferrer">查看简历 / CV</a>}
          <div className="pipelineActions">{actions(item)}</div>
        </article>)}
      </section>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><EmployerApplicants/></React.StrictMode>);
