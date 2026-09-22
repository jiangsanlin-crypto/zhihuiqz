import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BriefcaseBusiness,
  Building2,
  ChevronRight,
  Clock3,
  Factory,
  Heart,
  Home,
  Languages,
  MapPin,
  MessageCircle,
  Search,
  ShieldCheck,
  Sparkles,
  UserRound
} from "lucide-react";
import "./styles.css";

type Lang = "km" | "en" | "zh";

type Job = {
  id: number;
  company: string;
  title: Record<Lang, string>;
  location: Record<Lang, string>;
  distance: string;
  salary: string;
  headcount: number;
  tags: Record<Lang, string[]>;
  urgent?: boolean;
  posted: Record<Lang, string>;
};

const copy = {
  km: {
    hero: "រកការងារដែលសមនឹងអ្នក",
    subhero: "ការងាររោងចក្រ និងការងារជិតអ្នក ទូទាំងកម្ពុជា",
    search: "ស្វែងរកការងារ / រោងចក្រ",
    location: "ទីតាំង",
    nearby: "ការងារជិតខ្ញុំ",
    recommended: "ណែនាំសម្រាប់អ្នក",
    apply: "ដាក់ពាក្យភ្លាម",
    details: "មើលការងារ",
    noCv: "មិនចាំបាច់ CV • 30 វិនាទីដាក់ពាក្យ",
    navHome: "ទំព័រដើម",
    navNearby: "ជិតខ្ញុំ",
    navChat: "សារ",
    navApps: "ពាក្យសុំ",
    navMe: "ខ្ញុំ",
    urgent: "ជ្រើសរើសបន្ទាន់"
  },
  en: {
    hero: "Find work that fits you",
    subhero: "Factory and nearby jobs across Cambodia",
    search: "Search job / factory",
    location: "Location",
    nearby: "Jobs near me",
    recommended: "Recommended for you",
    apply: "Apply now",
    details: "View job",
    noCv: "No CV required • Apply in 30 seconds",
    navHome: "Home",
    navNearby: "Nearby",
    navChat: "Messages",
    navApps: "Applications",
    navMe: "Me",
    urgent: "Urgent hiring"
  },
  zh: {
    hero: "找到真正适合你的工作",
    subhero: "覆盖柬埔寨全境的工厂与附近岗位",
    search: "搜索职位 / 工厂",
    location: "地区",
    nearby: "附近工作",
    recommended: "为你推荐",
    apply: "一键申请",
    details: "查看职位",
    noCv: "无需简历 • 30秒完成报名",
    navHome: "首页",
    navNearby: "附近",
    navChat: "消息",
    navApps: "申请",
    navMe: "我的",
    urgent: "急招"
  }
} as const;

const jobs: Job[] = [
  {
    id: 1,
    company: "ABC Garment Factory",
    title: { km: "កម្មករដេរ / កម្មករទូទៅ", en: "Sewing / General Worker", zh: "缝纫工 / 普工" },
    location: { km: "ភ្នំពេញ", en: "Phnom Penh", zh: "金边" },
    distance: "3.2 km",
    salary: "$220–350 / ខែ",
    headcount: 200,
    urgent: true,
    tags: {
      km: ["អាហារ", "ឡានរោងចក្រ", "OT", "NSSF"],
      en: ["Meal", "Factory bus", "OT", "NSSF"],
      zh: ["工作餐", "厂车", "加班费", "NSSF"]
    },
    posted: { km: "ថ្ងៃនេះ", en: "Today", zh: "今天发布" }
  },
  {
    id: 2,
    company: "Kandal Electronics",
    title: { km: "កម្មករផលិត / QC", en: "Production / QC Worker", zh: "生产普工 / 质检" },
    location: { km: "កណ្ដាល", en: "Kandal", zh: "干拉" },
    distance: "7.8 km",
    salary: "$230–380 / ខែ",
    headcount: 80,
    tags: {
      km: ["គ្មានបទពិសោធន៍", "OT", "NSSF"],
      en: ["No experience", "OT", "NSSF"],
      zh: ["无需经验", "加班费", "NSSF"]
    },
    posted: { km: "2 ម៉ោងមុន", en: "2 hours ago", zh: "2小时前" }
  },
  {
    id: 3,
    company: "Kampong Speu Footwear",
    title: { km: "កម្មករស្បែកជើង", en: "Footwear Worker", zh: "鞋厂普工" },
    location: { km: "កំពង់ស្ពឺ", en: "Kampong Speu", zh: "磅士卑" },
    distance: "29 km",
    salary: "$215–330 / ខែ",
    headcount: 300,
    tags: {
      km: ["ស្នាក់នៅ", "អាហារ", "ឡានរោងចក្រ"],
      en: ["Dorm", "Meal", "Factory bus"],
      zh: ["住宿", "工作餐", "厂车"]
    },
    posted: { km: "ថ្ងៃនេះ", en: "Today", zh: "今天发布" }
  }
];

const categories = [
  ["🏭", { km: "កម្មករទូទៅ", en: "General", zh: "普工" }],
  ["🧵", { km: "ដេរ", en: "Sewing", zh: "缝纫" }],
  ["📦", { km: "ឃ្លាំង", en: "Warehouse", zh: "仓库" }],
  ["🔧", { km: "បច្ចេកទេស", en: "Technician", zh: "技工" }],
  ["🚚", { km: "អ្នកបើកបរ", en: "Driver", zh: "司机" }],
  ["🧹", { km: "អនាម័យ", en: "Cleaner", zh: "清洁" }],
  ["👟", { km: "រោងចក្រស្បែកជើង", en: "Footwear", zh: "鞋厂" }],
  ["👷", { km: "មេក្រុម", en: "Leader", zh: "组长" }]
] as const;

function App() {
  const [lang, setLang] = useState<Lang>("km");
  const [query, setQuery] = useState("");
  const t = copy[lang];

  const visibleJobs = useMemo(
    () =>
      jobs.filter((job) =>
        [job.company, job.title[lang], job.location[lang]].join(" ").toLowerCase().includes(query.toLowerCase())
      ),
    [query, lang]
  );

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="brandMark">K</span><span>KhmerHire <b>AI</b></span></div>
        <button className="langButton" onClick={() => setLang(lang === "km" ? "en" : lang === "en" ? "zh" : "km")}>
          <Languages size={18}/>{lang === "km" ? "ខ្មែរ" : lang === "en" ? "EN" : "中文"}
        </button>
      </header>

      <main>
        <section className="hero">
          <div className="eyebrow"><Sparkles size={16}/> AI Job Match</div>
          <h1>{t.hero}</h1>
          <p>{t.subhero}</p>
          <div className="searchBox">
            <Search size={20}/>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.search}/>
          </div>
          <button className="locationChip"><MapPin size={17}/> {t.location}: Phnom Penh <ChevronRight size={16}/></button>
        </section>

        <section className="section">
          <div className="quickHeader">
            <h2>{t.nearby}</h2>
            <span className="verified"><ShieldCheck size={16}/> Verified factories</span>
          </div>
          <div className="categoryGrid">
            {categories.map(([icon, label]) => (
              <button className="category" key={label.en}>
                <span>{icon}</span><small>{label[lang]}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="section jobs">
          <div className="sectionTitle"><h2>{t.recommended}</h2><span>{visibleJobs.length} jobs</span></div>
          {visibleJobs.map((job) => (
            <article className="jobCard" key={job.id}>
              <div className="jobTop">
                <div className="factoryIcon"><Factory size={24}/></div>
                <div className="jobIdentity">
                  <div className="jobTitleLine">
                    <h3>{job.title[lang]}</h3>
                    <button className="heart" aria-label="save"><Heart size={19}/></button>
                  </div>
                  <p className="company">{job.company}</p>
                </div>
              </div>
              <div className="meta">
                <span><MapPin size={15}/>{job.location[lang]} · {job.distance}</span>
                <span><Clock3 size={15}/>{job.posted[lang]}</span>
              </div>
              <div className="jobHighlight">
                {job.urgent && <span className="urgent">{t.urgent} {job.headcount}</span>}
                <strong>{job.salary}</strong>
              </div>
              <div className="tags">{job.tags[lang].map(tag => <span key={tag}>✓ {tag}</span>)}</div>
              <div className="jobActions">
                <button className="secondary">{t.details}</button>
                <button className="primary">{t.apply}</button>
              </div>
            </article>
          ))}
        </section>

        <section className="fastApply">
          <BriefcaseBusiness size={24}/>
          <div><strong>{t.noCv}</strong><small>Phone · Name · Location · Job type · Available date</small></div>
          <ChevronRight size={20}/>
        </section>
      </main>

      <nav className="bottomNav">
        <button className="active"><Home/><span>{t.navHome}</span></button>
        <button><MapPin/><span>{t.navNearby}</span></button>
        <button><MessageCircle/><span>{t.navChat}</span></button>
        <button><Building2/><span>{t.navApps}</span></button>
        <button><UserRound/><span>{t.navMe}</span></button>
      </nav>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App/></React.StrictMode>
);
