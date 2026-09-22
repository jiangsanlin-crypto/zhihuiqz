import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, LocateFixed, MapPin, ShieldCheck } from "lucide-react";
import { JobResult, searchNearbyJobs } from "./api";
import "./portal.css";

function salary(job: JobResult) {
  if (job.salary_min == null && job.salary_max == null) return "Salary negotiable";
  const min = job.salary_min == null ? "" : "$" + job.salary_min;
  const max = job.salary_max == null ? "" : "$" + job.salary_max;
  return min && max ? min + "–" + max + " / month" : (min || max);
}

function NearbyPage() {
  const [jobs, setJobs] = useState<JobResult[]>([]);
  const [radius, setRadius] = useState(25);
  const [status, setStatus] = useState("点击定位，查看你附近的工作");
  const [busy, setBusy] = useState(false);

  function locate() {
    if (!navigator.geolocation) {
      setStatus("当前浏览器不支持定位");
      return;
    }
    setBusy(true);
    setStatus("正在获取位置...");
    navigator.geolocation.getCurrentPosition(async (position) => {
      try {
        const result = await searchNearbyJobs(position.coords.latitude, position.coords.longitude, radius);
        setJobs(result);
        setStatus("已找到 " + result.length + " 个附近职位");
      } catch (error) {
        setStatus(error instanceof Error ? error.message : "加载失败");
      } finally {
        setBusy(false);
      }
    }, () => {
      setStatus("定位失败，请允许浏览器使用位置");
      setBusy(false);
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  }

  return (
    <div className="portalShell">
      <header className="portalTop">
        <button className="iconOnly" onClick={() => history.back()}><ArrowLeft/></button>
        <strong>附近工作</strong>
        <span/>
      </header>
      <main className="portalMain">
        <section className="nearbyHero">
          <div>
            <span className="miniBadge">📍 Jobs near me</span>
            <h1>离你近，通勤更轻松</h1>
            <p>只在你授权后使用当前定位，不保存浏览器的精确位置。</p>
          </div>
          <div className="radiusRow">
            {[10,25,50].map((value) => (
              <button key={value} className={radius === value ? "chip active" : "chip"} onClick={() => setRadius(value)}>{value} km</button>
            ))}
          </div>
          <button className="primaryWide" onClick={locate} disabled={busy}><LocateFixed/> {busy ? "定位中..." : "使用我的位置"}</button>
          <small className="statusText">{status}</small>
        </section>

        <section className="resultList">
          {jobs.map((job) => (
            <article className="nearJob" key={job.id}>
              <div className="jobHeader">
                <div>
                  <h2>{job.title_km || job.title_en}</h2>
                  <p>{job.location}</p>
                </div>
                {job.employer_verified && <span className="verifiedTag"><ShieldCheck/> 已认证</span>}
              </div>
              <div className="distance"><MapPin/> {job.distance_km == null ? "" : job.distance_km + " km"} · {salary(job)}</div>
              <div className="jobTags">
                <span>{job.category}</span>
                <span>招 {job.headcount} 人</span>
                {job.requires_cv ? <span>需要简历</span> : <span>可快速报名</span>}
              </div>
              <button className="primaryWide small">查看并申请</button>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><NearbyPage/></React.StrictMode>);
