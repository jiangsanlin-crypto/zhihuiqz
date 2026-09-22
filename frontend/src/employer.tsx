import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Building2, CheckCircle2, MapPin, UsersRound } from "lucide-react";
import {
  Employer,
  EmployerApplication,
  PipelineSummary,
  getEmployerApplications,
  getEmployerPipeline,
  getMe,
  getMyEmployers
} from "./api";
import "./styles.css";
import "./employer.css";

const emptyPipeline: PipelineSummary = {
  employer_id: 0,
  total_jobs: 0,
  target_headcount: 0,
  counts: { applied:0, contacted:0, interview:0, offered:0, joined:0, rejected:0 },
  by_job: []
};

function EmployerDashboard(){
  const [employer,setEmployer]=useState<Employer|null>(null);
  const [pipeline,setPipeline]=useState<PipelineSummary>(emptyPipeline);
  const [recent,setRecent]=useState<EmployerApplication[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");

  useEffect(()=>{
    (async()=>{
      try{
        const me=await getMe();
        const employers=await getMyEmployers();
        if(!employers.length){
          window.location.href=me.role==="employer_admin"||me.role==="platform_admin"?"/employer-onboarding.html":"/";
          return;
        }
        const current=employers[0];
        setEmployer(current);
        const [p,a]=await Promise.all([
          getEmployerPipeline(current.id),
          getEmployerApplications(current.id)
        ]);
        setPipeline(p);
        setRecent(a.slice(0,3));
      }catch(e){
        setError(e instanceof Error?e.message:"加载失败");
      }finally{
        setLoading(false);
      }
    })();
  },[]);

  const metrics=useMemo(()=>[
    ["招聘目标",pipeline.target_headcount,"人"],
    ["已报名",pipeline.counts.applied,"人"],
    ["已联系",pipeline.counts.contacted,"人"],
    ["已面试",pipeline.counts.interview,"人"],
    ["已录用",pipeline.counts.offered,"人"],
    ["已到岗",pipeline.counts.joined,"人"]
  ],[pipeline]);

  if(loading) return <div className="loadingScreen">KhmerHire AI...</div>;

  return <div className="employerApp">
    <header className="employerTop">
      <div><small>KhmerHire AI</small><h1>招聘中心</h1></div>
      <button className="employerSwitch" onClick={()=>window.location.href="/employer-onboarding.html"}>企业设置</button>
    </header>

    <main className="employerMain">
      {error && <div className="dashboardError">{error}</div>}
      {employer && <section className="factoryHero">
        <div className="factoryHeroIcon"><Building2/></div>
        <div><h2>{employer.name}</h2><p><MapPin size={14}/> {employer.location}</p></div>
        <span className={employer.verified?"factoryVerified":"factoryPending"}>
          {employer.verified?<><CheckCircle2 size={15}/> 已认证</>:"待认证"}
        </span>
      </section>}

      <section className="dashboardActions">
        <button onClick={()=>window.location.href=employer?.verified?"/employer-job.html":"/employer-onboarding.html"}>+ 发布职位</button>
        <button className="outline" onClick={()=>window.location.href="/employer-applicants.html"}>管理候选人</button>
        <button className="outline" onClick={()=>window.location.href="/employer-team.html"}>HR 团队</button>
      </section>

      <section>
        <div className="employerSectionTitle"><h2>招聘总览</h2><span>{pipeline.total_jobs} 个职位</span></div>
        <div className="metricGrid">
          {metrics.map(([label,value,unit],i)=><article key={String(label)} className={i===0?"metricCard metricPrimary":"metricCard"}>
            <small>{label}</small><strong>{value}</strong><span>{unit}</span>
          </article>)}
        </div>
      </section>

      <section>
        <div className="employerSectionTitle"><h2>岗位进度</h2><button onClick={()=>window.location.href="/employer-job.html"}>+ 新职位</button></div>
        <div className="roleList">
          {!pipeline.by_job.length && <div className="emptyState">还没有发布职位</div>}
          {pipeline.by_job.map(r=>{
            const joined=r.counts.joined;
            const pct=r.headcount?Math.min(100,Math.round(joined/r.headcount*100)):0;
            return <article className="roleCard" key={r.job_id}>
              <div className="roleTop"><strong>{r.title_zh||r.title_en||r.title_km}</strong><span>{joined}/{r.headcount} 已到岗</span></div>
              <div className="progress"><i style={{width:pct+"%"}}/></div>
              <small>报名 {r.counts.applied} · 联系 {r.counts.contacted} · 面试 {r.counts.interview} · 录用 {r.counts.offered}</small>
            </article>
          })}
        </div>
      </section>

      <section>
        <div className="employerSectionTitle"><h2>最新报名</h2><button onClick={()=>window.location.href="/employer-applicants.html"}>查看全部</button></div>
        <div className="candidateList">
          {!recent.length && <div className="emptyState">暂时还没有求职者报名</div>}
          {recent.map(c=><article className="candidateCard" key={c.id}>
            <div className="candidateAvatar"><UsersRound/></div>
            <div className="candidateInfo">
              <div className="candidateName"><strong>{c.candidate_name}</strong><b>{c.status}</b></div>
              <p>{c.job_title_zh||c.job_title_en}</p>
              <div className="candidateMeta">
                <span>{c.location||"未填写地区"}</span>
                <span>{c.available_date||"到岗时间未填"}</span>
                <span>{c.phone}</span>
              </div>
            </div>
          </article>)}
        </div>
      </section>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><EmployerDashboard/></React.StrictMode>);
