import React from "react";
import { createRoot } from "react-dom/client";
import { Building2, CheckCircle2, Clock3, MapPin, MessageCircle, Search, UsersRound } from "lucide-react";
import "./styles.css";
import "./employer.css";

const metrics = [
  ["本月招聘目标", "500", "人"],
  ["已报名", "863", "人"],
  ["待联系", "286", "人"],
  ["已面试", "175", "人"],
  ["已录用", "118", "人"],
  ["已到岗", "96", "人"]
];

const roles = [
  { title:"缝纫工", target:200, joined:68 },
  { title:"普工", target:200, joined:20 },
  { title:"质检员", target:50, joined:8 }
];

const candidates = [
  { name:"Sok Dara", role:"Full-line sewing worker", distance:"4.3 km", exp:"制衣厂 2年", available:"立即", score:94 },
  { name:"Chan Srey", role:"QC / Production", distance:"6.1 km", exp:"电子厂 1年", available:"明天", score:91 },
  { name:"Vannak", role:"General worker", distance:"2.8 km", exp:"无需经验", available:"立即", score:89 }
];

function EmployerDashboard(){
  return <div className="employerApp">
    <header className="employerTop">
      <div><small>KhmerHire AI</small><h1>Factory Recruitment</h1></div>
      <button className="employerSwitch">中文 / EN / ខ្មែរ</button>
    </header>

    <main className="employerMain">
      <section className="factoryHero">
        <div className="factoryHeroIcon"><Building2/></div>
        <div><h2>ABC Garment Factory</h2><p><MapPin size={14}/> Phnom Penh · 已认证工厂</p></div>
        <span className="factoryVerified"><CheckCircle2 size={15}/> Verified</span>
      </section>

      <section>
        <div className="employerSectionTitle"><h2>招聘总览</h2><span>September 2026</span></div>
        <div className="metricGrid">
          {metrics.map(([label,value,unit],i)=><article key={label} className={i===0?"metricCard metricPrimary":"metricCard"}>
            <small>{label}</small><strong>{value}</strong><span>{unit}</span>
          </article>)}
        </div>
      </section>

      <section>
        <div className="employerSectionTitle"><h2>岗位进度</h2><button>+ 发布岗位</button></div>
        <div className="roleList">
          {roles.map(r=>{
            const pct=Math.round(r.joined/r.target*100);
            return <article className="roleCard" key={r.title}>
              <div className="roleTop"><strong>{r.title}</strong><span>{r.joined}/{r.target} 已到岗</span></div>
              <div className="progress"><i style={{width:pct+"%"}}/></div>
              <small>完成 {pct}%</small>
            </article>
          })}
        </div>
      </section>

      <section>
        <div className="employerSectionTitle"><h2>AI 推荐候选人</h2><button className="ghostBtn"><Search size={15}/>筛选</button></div>
        <div className="candidateList">
          {candidates.map(c=><article className="candidateCard" key={c.name}>
            <div className="candidateAvatar"><UsersRound/></div>
            <div className="candidateInfo">
              <div className="candidateName"><strong>{c.name}</strong><b>{c.score}% 匹配</b></div>
              <p>{c.role}</p>
              <div className="candidateMeta">
                <span><MapPin size={13}/>{c.distance}</span>
                <span>{c.exp}</span>
                <span><Clock3 size={13}/>{c.available}可上班</span>
              </div>
            </div>
            <button className="messageBtn"><MessageCircle size={17}/></button>
          </article>)}
        </div>
      </section>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><EmployerDashboard/></React.StrictMode>);
