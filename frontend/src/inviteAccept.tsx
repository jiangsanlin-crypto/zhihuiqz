import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { CheckCircle2, UserPlus } from "lucide-react";
import { acceptEmployerInvitation, getMe } from "./api";
import "./portal.css";

function InviteAccept(){
  const token=new URLSearchParams(location.search).get("token")||"";
  const [message,setMessage]=useState("");
  const [done,setDone]=useState(false);

  async function accept(){
    try{
      await getMe();
      await acceptEmployerInvitation(token);
      setDone(true);
    }catch(e){
      setMessage(e instanceof Error?e.message:"接受邀请失败。请先登录与邀请手机号一致的账号。");
    }
  }

  return <div className="portalShell">
    <main className="portalMain narrow inviteCenter">
      <div className="portalCard centerState">
        {done?<CheckCircle2/>:<UserPlus/>}
        <h1>{done?"已加入招聘团队":"HR 团队邀请"}</h1>
        <p>{done?"现在可以使用自己的账号进入企业招聘后台。":"请使用被邀请手机号登录后接受邀请，无需共享企业主账号密码。"}</p>
        {message&&<div className="errorBox">{message}</div>}
        {done
          ?<button className="primaryWide" onClick={()=>window.location.href="/employer.html"}>进入企业后台</button>
          :<><button className="primaryWide" onClick={accept}>接受邀请</button><button className="textAction" onClick={()=>window.location.href="/auth.html?next="+encodeURIComponent(window.location.pathname+window.location.search)}>先登录 / 注册</button></>
        }
      </div>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><InviteAccept/></React.StrictMode>);
