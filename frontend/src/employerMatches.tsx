import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, Sparkles, UserRound } from "lucide-react";
import { CandidateMatch, getJobMatches, getMyEmployers } from "./api";
import "./portal.css";

const factorLabel:Record<string,string>={
  distance:"距离",languages:"语言",skills:"技能",availability:"到岗时间"
};

function EmployerMatches(){
  const jobId=Number(new URLSearchParams(location.search).get("job"));
  const [items,setItems]=useState<CandidateMatch[]>([]);
  const [message,setMessage]=useState("");

  useEffect(()=>{
    (async()=>{
      try{
        const employers=await getMyEmployers();
        if(!employers.length){window.location.href="/auth.html";return;}
        if(!jobId){setMessage("缺少职位编号");return;}
        setItems(await getJobMatches(jobId));
      }catch(e){setMessage(e instanceof Error?e.message:"加载失败");}
    })();
  },[]);

  return <div className="portalShell">
    <header className="portalTop"><button className="iconOnly" onClick={()=>history.back()}><ArrowLeft/></button><strong>AI 人才推荐</strong><span/></header>
    <main className="portalMain">
      <div className="portalHero">
        <span className="miniBadge"><Sparkles/> Explainable Match</span>
        <h1>为什么推荐这个人</h1>
        <p>先用可解释规则排序：距离、语言、技能关键词和到岗时间。后续再叠加行为数据与模型评分。</p>
      </div>
      {message&&<div className="errorBox">{message}</div>}
      <section className="matchList">
        {!items.length&&!message&&<div className="portalCard compactMuted">暂时没有足够的候选人资料用于匹配</div>}
        {items.map((item,index)=><article className="portalCard matchCard" key={item.candidate_user_id}>
          <div className="matchHead">
            <div className="candidateAvatar"><UserRound/></div>
            <div><b>{item.candidate_name||"Candidate"}</b><small>推荐排名 #{index+1}</small></div>
            <strong>{item.score}%</strong>
          </div>
          <div className="matchFactors">
            {item.factors.map(f=><div key={f.name}>
              <span>{factorLabel[f.name]||f.name}</span>
              <b>+{f.score}</b>
              <small>{f.detail}</small>
            </div>)}
          </div>
        </article>)}
      </section>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><EmployerMatches/></React.StrictMode>);
