import React, { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, LocateFixed } from "lucide-react";
import { Employer, createJob, getDistricts, getMe, getMyEmployers, getProvinces } from "./api";
import "./portal.css";

const categories = [
  ["factory","工厂 / 制造"],["retail","销售 / 门店 / 客服"],["logistics","仓库 / 物流 / 司机"],
  ["technical","技工 / 建筑 / 维修"],["hospitality","餐饮 / 酒店 / 服务"],["office","行政 / 财务 / HR"],
  ["professional","IT / 设计 / 工程"],["education_health","教育 / 医疗"],["security_cleaning","保安 / 清洁 / 家政"],
  ["agriculture_other","农业 / 其他"]
];

function EmployerJobPage(){
  const [employer,setEmployer]=useState<Employer|null>(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [category,setCategory]=useState("factory");
  const [titleKm,setTitleKm]=useState("");
  const [titleEn,setTitleEn]=useState("");
  const [titleZh,setTitleZh]=useState("");
  const [location,setLocation]=useState("Phnom Penh");
  const [lat,setLat]=useState<number|null>(null);
  const [lon,setLon]=useState<number|null>(null);
  const [salaryMin,setSalaryMin]=useState("");
  const [salaryMax,setSalaryMax]=useState("");
  const [headcount,setHeadcount]=useState("1");
  const [benefits,setBenefits]=useState("");
  const [benefitCodes,setBenefitCodes]=useState<string[]>([]);
  const [shift,setShift]=useState("day");
  const [languagesRequired,setLanguagesRequired]=useState("");
  const [experienceLevel,setExperienceLevel]=useState("any");
  const [provinceCode,setProvinceCode]=useState("phnom_penh");
  const [districtCode,setDistrictCode]=useState("");
  const [provinces,setProvinces]=useState<Array<{code:string;km:string;en:string;zh:string}>>([]);
  const [districts,setDistricts]=useState<Array<{code:string;en:string;zh:string}>>([]);
  const [description,setDescription]=useState("");
  const [requiresCv,setRequiresCv]=useState(false);

  useEffect(()=>{
    (async()=>{
      try{
        const me=await getMe();
        const employers=await getMyEmployers();
        const current=employers[0];
        if(!current){window.location.href=me.role==="employer_admin"||me.role==="platform_admin"?"/employer-onboarding.html":"/";return;}
        if(!current.verified){window.location.href="/employer-onboarding.html";return;}
        setEmployer(current);
        setLocation(current.location||"Phnom Penh");
        setLat(current.latitude);
        setLon(current.longitude);
        const provinceRows=await getProvinces();
        setProvinces(provinceRows);
        const districtRows=await getDistricts("phnom_penh");
        setDistricts(districtRows);
      }catch{
        window.location.href="/auth.html";
      }
    })();
  },[]);

  async function changeProvince(code:string){
    setProvinceCode(code);
    setDistrictCode("");
    try{setDistricts(await getDistricts(code));}catch{setDistricts([]);}
  }

  function toggleBenefit(code:string){
    setBenefitCodes(current=>current.includes(code)?current.filter(x=>x!==code):[...current,code]);
  }

  function locate(){
    if(!navigator.geolocation){setMessage("当前浏览器不支持定位");return;}
    navigator.geolocation.getCurrentPosition((p)=>{
      setLat(p.coords.latitude);
      setLon(p.coords.longitude);
      setMessage("已记录职位位置，可用于附近工作搜索");
    },()=>setMessage("定位失败，可继续发布，但附近搜索不会按距离显示"));
  }

  async function submit(e:FormEvent){
    e.preventDefault();
    if(!employer)return;
    setBusy(true);setMessage("");
    try{
      const fallback=titleZh||titleEn||titleKm;
      await createJob({
        employer_id:employer.id,
        category,
        title_km:titleKm||fallback,
        title_en:titleEn||fallback,
        title_zh:titleZh||fallback,
        location,
        latitude:lat,
        longitude:lon,
        salary_min:salaryMin?Number(salaryMin):null,
        salary_max:salaryMax?Number(salaryMax):null,
        currency:"USD",
        headcount:Math.max(1,Number(headcount)||1),
        job_type:"full_time",
        experience_required:false,
        requires_cv:requiresCv,
        benefits,
        benefit_codes:benefitCodes.join(","),
        shift,
        languages_required:languagesRequired,
        experience_level:experienceLevel,
        province_code:provinceCode,
        district_code:districtCode,
        description
      });
      window.location.href="/employer.html";
    }catch(error){
      setMessage(error instanceof Error?error.message:"发布失败");
    }finally{setBusy(false);}
  }

  return <div className="portalShell">
    <header className="portalTop">
      <button className="iconOnly" onClick={()=>history.back()}><ArrowLeft/></button>
      <strong>发布职位</strong><span/>
    </header>
    <main className="portalMain narrow">
      <div className="portalHero"><span className="miniBadge">Employer</span><h1>快速发布招聘</h1><p>只保留求职者最关心的信息：岗位、工资、地点、人数和福利。</p></div>
      <form className="portalCard formGrid" onSubmit={submit}>
        <label>职位分类<select value={category} onChange={(e)=>setCategory(e.target.value)}>{categories.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
        <label>高棉语职位名<input value={titleKm} onChange={(e)=>setTitleKm(e.target.value)} placeholder="可填写高棉语"/></label>
        <label>英文职位名<input value={titleEn} onChange={(e)=>setTitleEn(e.target.value)} placeholder="General Worker"/></label>
        <label>中文职位名<input value={titleZh} onChange={(e)=>setTitleZh(e.target.value)} required placeholder="普工"/></label>
        <div className="twoCol">
          <label>省 / 市<select value={provinceCode} onChange={(e)=>changeProvince(e.target.value)}>
            {provinces.map(p=><option key={p.code} value={p.code}>{p.zh} / {p.en}</option>)}
          </select></label>
          <label>区 / 县<select value={districtCode} onChange={(e)=>setDistrictCode(e.target.value)}>
            <option value="">不指定</option>
            {districts.map(d=><option key={d.code} value={d.code}>{d.zh} / {d.en}</option>)}
          </select></label>
        </div>
        <label>工作地点<input value={location} onChange={(e)=>setLocation(e.target.value)} required/></label>
        <button type="button" className="secondaryWide" onClick={locate}><LocateFixed/> 使用当前位置作为工作地点</button>
        <div className="twoCol">
          <label>最低工资 USD<input value={salaryMin} onChange={(e)=>setSalaryMin(e.target.value)} inputMode="decimal"/></label>
          <label>最高工资 USD<input value={salaryMax} onChange={(e)=>setSalaryMax(e.target.value)} inputMode="decimal"/></label>
        </div>
        <label>招聘人数<input value={headcount} onChange={(e)=>setHeadcount(e.target.value)} inputMode="numeric"/></label>
        <div className="twoCol">
          <label>班次<select value={shift} onChange={(e)=>setShift(e.target.value)}>
            <option value="day">白班</option><option value="night">夜班</option><option value="rotating">轮班</option><option value="flexible">灵活</option>
          </select></label>
          <label>经验<select value={experienceLevel} onChange={(e)=>setExperienceLevel(e.target.value)}>
            <option value="any">不限</option><option value="entry">可无经验</option><option value="experienced">需要经验</option><option value="senior">资深</option>
          </select></label>
        </div>
        <label>语言要求<input value={languagesRequired} onChange={(e)=>setLanguagesRequired(e.target.value)} placeholder="km,en,zh"/></label>
        <label>福利说明<input value={benefits} onChange={(e)=>setBenefits(e.target.value)} placeholder="工作餐, 厂车, NSSF, 住宿"/></label>
        <div className="benefitPicker">
          {[["meal","工作餐"],["bus","厂车"],["nssf","NSSF"],["dorm","住宿"],["ot","加班费"]].map(([code,label])=>
            <button type="button" key={code} className={benefitCodes.includes(code)?"active":""} onClick={()=>toggleBenefit(code)}>{label}</button>
          )}
        </div>
        <label>职位说明<textarea value={description} onChange={(e)=>setDescription(e.target.value)} rows={4} placeholder="简单说明工作内容和要求"/></label>
        <label className="checkRow"><input type="checkbox" checked={requiresCv} onChange={(e)=>setRequiresCv(e.target.checked)}/> 此岗位必须上传简历/作品集</label>
        {message&&<div className="infoBox">{message}</div>}
        <button className="primaryWide" disabled={busy}>{busy?"发布中...":"发布职位"}</button>
      </form>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><EmployerJobPage/></React.StrictMode>);
