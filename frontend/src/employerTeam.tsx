import React, { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, Copy, UserPlus, UsersRound } from "lucide-react";
import {
  Employer,
  EmployerTeamMember,
  getEmployerTeam,
  getMe,
  getMyEmployers,
  inviteEmployerTeamMember
} from "./api";
import "./portal.css";

function EmployerTeam(){
  const [meId,setMeId]=useState<number|null>(null);
  const [employer,setEmployer]=useState<Employer|null>(null);
  const [team,setTeam]=useState<EmployerTeamMember[]>([]);
  const [phone,setPhone]=useState("");
  const [inviteLink,setInviteLink]=useState("");
  const [message,setMessage]=useState("");

  async function load(){
    const me=await getMe();
    setMeId(me.id);
    const employers=await getMyEmployers();
    if(!employers.length){window.location.href="/employer-onboarding.html";return;}
    setEmployer(employers[0]);
    setTeam(await getEmployerTeam(employers[0].id));
  }

  useEffect(()=>{load().catch(()=>window.location.href="/auth.html");},[]);

  async function invite(e:FormEvent){
    e.preventDefault();
    if(!employer)return;
    setMessage("");
    try{
      const result=await inviteEmployerTeamMember(employer.id,phone,"hr");
      const link=location.origin+"/invite.html?token="+encodeURIComponent(result.token);
      setInviteLink(link);
      setPhone("");
      await load();
    }catch(e){setMessage(e instanceof Error?e.message:"邀请失败");}
  }

  async function copy(){
    if(inviteLink)await navigator.clipboard.writeText(inviteLink);
  }

  const owner=employer&&meId===employer.owner_user_id;

  return <div className="portalShell">
    <header className="portalTop"><button className="iconOnly" onClick={()=>history.back()}><ArrowLeft/></button><strong>HR 团队</strong><span/></header>
    <main className="portalMain narrow">
      <div className="portalHero"><span className="miniBadge">Team</span><h1>多人一起招聘</h1><p>每个 HR 使用自己的账号，不需要共享企业主密码。</p></div>

      {owner&&<form className="portalCard formGrid" onSubmit={invite}>
        <div className="stepTitle"><UserPlus/> 邀请 HR</div>
        <label>HR 手机号<input value={phone} onChange={(e)=>setPhone(e.target.value)} placeholder="012345678" required/></label>
        <button className="primaryWide">生成邀请链接</button>
        {message&&<div className="errorBox">{message}</div>}
        {inviteLink&&<div className="inviteResult"><span>{inviteLink}</span><button type="button" onClick={copy}><Copy/></button></div>}
      </form>}

      <section>
        <div className="sectionMiniTitle"><UsersRound/> 团队成员</div>
        {!team.length&&<div className="portalCard compactMuted">还没有 HR 成员</div>}
        {team.map(member=><article className="portalCard teamMember" key={member.id}>
          <div className="candidateAvatar"><UsersRound/></div>
          <div><b>{member.display_name||member.phone}</b><small>{member.phone} · {member.role}</small></div>
          <span className={"status "+(member.status==="active"?"approved":"")}>{member.status}</span>
        </article>)}
      </section>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><EmployerTeam/></React.StrictMode>);
