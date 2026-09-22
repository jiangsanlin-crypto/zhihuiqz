import React, { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, Building2, CheckCircle2, FileCheck2, MapPin } from "lucide-react";
import {
  Employer,
  createEmployer,
  getEmployerVerification,
  getMe,
  getMyEmployers,
  submitEmployerVerification
} from "./api";
import "./portal.css";

function EmployerOnboarding() {
  const [employer, setEmployer] = useState<Employer | null>(null);
  const [status, setStatus] = useState("not_submitted");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(true);
  const [name, setName] = useState("");
  const [location, setLocation] = useState("Phnom Penh");
  const [legalName, setLegalName] = useState("");
  const [registration, setRegistration] = useState("");
  const [documentUrl, setDocumentUrl] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe();
        if (me.role !== "employer_admin" && me.role !== "platform_admin") {
          window.location.href = "/auth.html";
          return;
        }
        const employers = await getMyEmployers();
        const first = employers[0] || null;
        setEmployer(first);
        if (first) {
          try {
            const verification = await getEmployerVerification(first.id);
            setStatus(verification.status);
          } catch {
            setStatus("not_submitted");
          }
        }
      } catch {
        window.location.href = "/auth.html";
      } finally {
        setBusy(false);
      }
    })();
  }, []);

  async function createCompany(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setBusy(true);
    try {
      const created = await createEmployer({
        name,
        employer_type: "general",
        location,
        latitude: null,
        longitude: null
      });
      setEmployer(created);
      setLegalName(name);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitVerification(event: FormEvent) {
    event.preventDefault();
    if (!employer) return;
    setMessage("");
    setBusy(true);
    try {
      const result = await submitEmployerVerification(employer.id, {
        legal_name: legalName,
        registration_number: registration,
        document_url: documentUrl
      });
      setStatus(result.status);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  if (busy && !employer) return <div className="loadingScreen">KhmerHire AI...</div>;

  return (
    <div className="portalShell">
      <header className="portalTop">
        <button className="iconOnly" onClick={() => history.back()}><ArrowLeft/></button>
        <strong>企业入驻与认证</strong>
        <span/>
      </header>
      <main className="portalMain narrow">
        <section className="portalHero">
          <span className="miniBadge">Verified Employer</span>
          <h1>先认证，再招聘</h1>
          <p>减少虚假职位。企业认证通过后才能正式发布职位。</p>
        </section>

        {!employer ? (
          <form className="portalCard formGrid" onSubmit={createCompany}>
            <div className="stepTitle"><Building2/> 1. 创建企业</div>
            <label>企业名称<input value={name} onChange={(e) => setName(e.target.value)} required placeholder="ABC Garment Factory"/></label>
            <label>所在地区<input value={location} onChange={(e) => setLocation(e.target.value)} required/></label>
            <button className="primaryWide" disabled={busy}>创建企业</button>
          </form>
        ) : (
          <>
            <section className="portalCard companySummary">
              <Building2/>
              <div><b>{employer.name}</b><small><MapPin/> {employer.location}</small></div>
              <span className={employer.verified ? "status approved" : "status"}>{employer.verified ? "已认证" : "未认证"}</span>
            </section>

            {status === "not_submitted" && (
              <form className="portalCard formGrid" onSubmit={submitVerification}>
                <div className="stepTitle"><FileCheck2/> 2. 提交认证资料</div>
                <label>企业法定名称<input value={legalName} onChange={(e) => setLegalName(e.target.value)} required/></label>
                <label>注册号 / Registration No.<input value={registration} onChange={(e) => setRegistration(e.target.value)} placeholder="可留空，后续人工核验"/></label>
                <label>证明文件链接<input value={documentUrl} onChange={(e) => setDocumentUrl(e.target.value)} required placeholder="https://..."/></label>
                {message && <div className="errorBox">{message}</div>}
                <button className="primaryWide" disabled={busy}>提交审核</button>
              </form>
            )}

            {status === "pending" && (
              <section className="portalCard centerState">
                <FileCheck2/>
                <h2>资料审核中</h2>
                <p>审核通过后即可发布正式职位。请勿重复提交。</p>
              </section>
            )}

            {status === "approved" && (
              <section className="portalCard centerState success">
                <CheckCircle2/>
                <h2>企业已认证</h2>
                <p>现在可以进入企业招聘后台发布职位。</p>
                <button className="primaryWide" onClick={() => window.location.href = "/employer.html"}>进入招聘后台</button>
              </section>
            )}

            {status === "rejected" && (
              <section className="portalCard centerState">
                <FileCheck2/>
                <h2>认证未通过</h2>
                <p>请联系平台客服，根据审核说明补充资料。</p>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><EmployerOnboarding/></React.StrictMode>);
