import React, { FormEvent, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, BriefcaseBusiness, UserRound } from "lucide-react";
import { getMe, loginAccount, registerAccount } from "./api";
import "./portal.css";

type Role = "candidate" | "employer_admin";

function AuthPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [role, setRole] = useState<Role>("candidate");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      if (mode === "register") {
        await registerAccount({ phone, password, role, display_name: name });
      }
      await loginAccount(phone, password);
      const me = await getMe();
      window.location.href = me.role === "employer_admin" ? "/employer-onboarding.html" : "/";
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="portalShell">
      <header className="portalTop">
        <button className="iconOnly" onClick={() => history.back()}><ArrowLeft/></button>
        <strong>KhmerHire AI</strong>
        <span/>
      </header>
      <main className="portalMain narrow">
        <div className="portalHero">
          <span className="miniBadge">ខ្មែរ · English · 中文</span>
          <h1>{mode === "login" ? "ចូលគណនី / Sign in" : "បង្កើតគណនី / Register"}</h1>
          <p>求职者免费使用；企业账号用于发布职位和管理招聘。</p>
        </div>

        <div className="rolePicker">
          <button className={role === "candidate" ? "role active" : "role"} onClick={() => setRole("candidate")}>
            <UserRound/><b>找工作</b><small>Candidate</small>
          </button>
          <button className={role === "employer_admin" ? "role active" : "role"} onClick={() => setRole("employer_admin")}>
            <BriefcaseBusiness/><b>企业招聘</b><small>Employer</small>
          </button>
        </div>

        <form className="portalCard formGrid" onSubmit={submit}>
          {mode === "register" && (
            <label>姓名 / Name<input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Sok Dara"/></label>
          )}
          <label>手机号 / Phone<input value={phone} onChange={(e) => setPhone(e.target.value)} required placeholder="012345678"/></label>
          <label>密码 / Password<input value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} type="password" placeholder="8+ characters"/></label>
          {message && <div className="errorBox">{message}</div>}
          <button className="primaryWide" disabled={busy}>{busy ? "..." : mode === "login" ? "登录" : "注册并继续"}</button>
        </form>

        <button className="textAction" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "没有账号？立即注册" : "已有账号？登录"}
        </button>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><AuthPage/></React.StrictMode>);
