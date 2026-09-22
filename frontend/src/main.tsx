import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BriefcaseBusiness,
  Building2,
  ChevronRight,
  Clock3,
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
type CategoryId =
  | "factory"
  | "retail"
  | "logistics"
  | "technical"
  | "hospitality"
  | "office"
  | "professional"
  | "education_health"
  | "security_cleaning"
  | "agriculture_other";

type Job = {
  id: number;
  company: string;
  category: CategoryId;
  title: Record<Lang, string>;
  location: Record<Lang, string>;
  distance: string;
  salary: string;
  headcount?: number;
  tags: Record<Lang, string[]>;
  urgent?: boolean;
  posted: Record<Lang, string>;
};

const copy = {
  km: {
    hero: "រកការងារដែលសមនឹងអ្នក",
    subhero: "ការងារគ្រប់ប្រភេទ ទូទាំងកម្ពុជា — ងាយស្វែងរក ងាយដាក់ពាក្យ",
    search: "ស្វែងរកមុខតំណែង / ក្រុមហ៊ុន",
    location: "ទីតាំង",
    categories: "ជ្រើសរើសប្រភេទការងារ",
    allJobs: "ការងារទាំងអស់",
    nearby: "ការងារជិតខ្ញុំ",
    recommended: "ណែនាំសម្រាប់អ្នក",
    apply: "ដាក់ពាក្យភ្លាម",
    details: "មើលការងារ",
    noCv: "មុខតំណែងជាច្រើន មិនចាំបាច់ CV • ដាក់ពាក្យលឿន",
    navHome: "ទំព័រដើម",
    navNearby: "ជិតខ្ញុំ",
    navChat: "សារ",
    navApps: "ពាក្យសុំ",
    navMe: "ខ្ញុំ",
    urgent: "ជ្រើសរើសបន្ទាន់",
    verified: "ក្រុមហ៊ុនបានផ្ទៀងផ្ទាត់",
    quick: ["បន្ទាន់", "គ្មានបទពិសោធន៍", "$300+", "មានឡាន"]
  },
  en: {
    hero: "Find work that fits you",
    subhero: "Simple job search across Cambodia — from factory work to office and professional roles",
    search: "Search job / company",
    location: "Location",
    categories: "Browse job categories",
    allJobs: "All jobs",
    nearby: "Jobs near me",
    recommended: "Recommended for you",
    apply: "Apply now",
    details: "View job",
    noCv: "Many roles need no CV • Apply fast",
    navHome: "Home",
    navNearby: "Nearby",
    navChat: "Messages",
    navApps: "Applications",
    navMe: "Me",
    urgent: "Urgent",
    verified: "Verified employers",
    quick: ["Urgent", "No experience", "$300+", "Factory bus"]
  },
  zh: {
    hero: "找到真正适合你的工作",
    subhero: "覆盖柬埔寨全境，从工厂岗位到门店、办公室和专业职位",
    search: "搜索职位 / 公司",
    location: "地区",
    categories: "你想找什么工作？",
    allJobs: "全部职位",
    nearby: "附近工作",
    recommended: "为你推荐",
    apply: "一键申请",
    details: "查看职位",
    noCv: "大量岗位无需简历 • 快速完成报名",
    navHome: "首页",
    navNearby: "附近",
    navChat: "消息",
    navApps: "申请",
    navMe: "我的",
    urgent: "急招",
    verified: "认证企业",
    quick: ["急招", "无经验也可以", "$300+ 工作", "有厂车"]
  }
} as const;

const categories: Array<{ id: CategoryId; icon: string; label: Record<Lang, string> }> = [
  { id:"factory", icon:"🏭", label:{ km:"រោងចក្រ / ផលិតកម្ម", en:"Factory", zh:"工厂 / 制造" } },
  { id:"retail", icon:"🛒", label:{ km:"លក់ / ហាង / សេវា", en:"Sales & Retail", zh:"销售 / 门店" } },
  { id:"logistics", icon:"📦", label:{ km:"ឃ្លាំង / ដឹកជញ្ជូន", en:"Logistics", zh:"仓库 / 物流" } },
  { id:"technical", icon:"🔧", label:{ km:"ជាង / សំណង់", en:"Technical", zh:"技工 / 建筑" } },
  { id:"hospitality", icon:"🍜", label:{ km:"ភោជនីយដ្ឋាន / សណ្ឋាគារ", en:"Hospitality", zh:"餐饮 / 酒店" } },
  { id:"office", icon:"💼", label:{ km:"រដ្ឋបាល / គណនេយ្យ / HR", en:"Office", zh:"行政 / 财务 / HR" } },
  { id:"professional", icon:"💻", label:{ km:"IT / រចនា / វិស្វកម្ម", en:"IT & Engineering", zh:"IT / 设计 / 工程" } },
  { id:"education_health", icon:"🏫", label:{ km:"អប់រំ / សុខាភិបាល", en:"Education & Health", zh:"教育 / 医疗" } },
  { id:"security_cleaning", icon:"🛡️", label:{ km:"សន្តិសុខ / អនាម័យ", en:"Security & Cleaning", zh:"保安 / 清洁" } },
  { id:"agriculture_other", icon:"🌾", label:{ km:"កសិកម្ម / ផ្សេងៗ", en:"Agriculture & Other", zh:"农业 / 其他" } }
];

const jobs: Job[] = [
  {
    id:1, company:"ABC Garment Factory", category:"factory",
    title:{ km:"កម្មករដេរ / កម្មករទូទៅ", en:"Sewing / General Worker", zh:"缝纫工 / 普工" },
    location:{ km:"ភ្នំពេញ", en:"Phnom Penh", zh:"金边" }, distance:"3.2 km", salary:"$220–350 / month", headcount:200, urgent:true,
    tags:{ km:["អាហារ","ឡានរោងចក្រ","OT","NSSF"], en:["Meal","Factory bus","OT","NSSF"], zh:["工作餐","厂车","加班费","NSSF"] },
    posted:{ km:"ថ្ងៃនេះ", en:"Today", zh:"今天发布" }
  },
  {
    id:2, company:"Lucky Market", category:"retail",
    title:{ km:"បុគ្គលិកលក់ / គិតលុយ", en:"Sales Assistant / Cashier", zh:"门店销售 / 收银员" },
    location:{ km:"ភ្នំពេញ", en:"Phnom Penh", zh:"金边" }, distance:"2.1 km", salary:"$230–320 / month", urgent:true,
    tags:{ km:["ពេញម៉ោង","បណ្តុះបណ្តាល"], en:["Full-time","Training"], zh:["全职","提供培训"] },
    posted:{ km:"1 ម៉ោងមុន", en:"1 hour ago", zh:"1小时前" }
  },
  {
    id:3, company:"Kandal Logistics", category:"logistics",
    title:{ km:"បុគ្គលិកឃ្លាំង / អ្នកបើកបរ", en:"Warehouse / Driver", zh:"仓库管理员 / 司机" },
    location:{ km:"កណ្ដាល", en:"Kandal", zh:"干拉" }, distance:"8.6 km", salary:"$260–420 / month", headcount:25,
    tags:{ km:["OT","NSSF"], en:["OT","NSSF"], zh:["加班费","NSSF"] },
    posted:{ km:"ថ្ងៃនេះ", en:"Today", zh:"今天发布" }
  },
  {
    id:4, company:"Mekong Repair & Engineering", category:"technical",
    title:{ km:"ជាងអគ្គិសនី / ជាងម៉ាស៊ីន", en:"Electrician / Mechanic", zh:"电工 / 机修工" },
    location:{ km:"ភ្នំពេញ", en:"Phnom Penh", zh:"金边" }, distance:"5.4 km", salary:"$350–650 / month",
    tags:{ km:["ជំនាញ","ពេញម៉ោង"], en:["Skilled","Full-time"], zh:["技能岗","全职"] },
    posted:{ km:"ម្សិលមិញ", en:"Yesterday", zh:"昨天" }
  },
  {
    id:5, company:"Riverside Hotel", category:"hospitality",
    title:{ km:"បុគ្គលិកភោជនីយដ្ឋាន / ផ្នែកទទួលភ្ញៀវ", en:"Restaurant / Front Desk", zh:"餐厅服务员 / 酒店前台" },
    location:{ km:"ភ្នំពេញ", en:"Phnom Penh", zh:"金边" }, distance:"4.7 km", salary:"$240–380 / month",
    tags:{ km:["អាហារ","វេន"], en:["Meal","Shift"], zh:["工作餐","轮班"] },
    posted:{ km:"3 ម៉ោងមុន", en:"3 hours ago", zh:"3小时前" }
  },
  {
    id:6, company:"Golden Cambodia Trading", category:"office",
    title:{ km:"រដ្ឋបាល / គណនេយ្យ", en:"Admin / Accountant", zh:"行政文员 / 会计" },
    location:{ km:"ភ្នំពេញ", en:"Phnom Penh", zh:"金边" }, distance:"6.5 km", salary:"$350–650 / month",
    tags:{ km:["Office","English"], en:["Office","English"], zh:["办公室","英语优先"] },
    posted:{ km:"ថ្ងៃនេះ", en:"Today", zh:"今天发布" }
  },
  {
    id:7, company:"Cambodia Tech Hub", category:"professional",
    title:{ km:"IT Support / Web Developer", en:"IT Support / Web Developer", zh:"IT支持 / Web开发" },
    location:{ km:"ភ្នំពេញ", en:"Phnom Penh", zh:"金边" }, distance:"7.0 km", salary:"$500–1200 / month",
    tags:{ km:["IT","Hybrid"], en:["IT","Hybrid"], zh:["IT","混合办公"] },
    posted:{ km:"ថ្ងៃនេះ", en:"Today", zh:"今天发布" }
  },
  {
    id:8, company:"Bright Future School", category:"education_health",
    title:{ km:"គ្រូបង្រៀនភាសាអង់គ្លេស", en:"English Teacher", zh:"英语教师" },
    location:{ km:"ភ្នំពេញ", en:"Phnom Penh", zh:"金边" }, distance:"3.9 km", salary:"$400–800 / month",
    tags:{ km:["English","Teaching"], en:["English","Teaching"], zh:["英语","教学"] },
    posted:{ km:"2 ថ្ងៃមុន", en:"2 days ago", zh:"2天前" }
  }
];

function App() {
  const [lang, setLang] = useState<Lang>("km");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CategoryId | "all">("all");
  const t = copy[lang];

  const visibleJobs = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((job) => {
      const categoryMatch = category === "all" || job.category === category;
      const textMatch = !q || [job.company, job.title[lang], job.location[lang], ...job.tags[lang]].join(" ").toLowerCase().includes(q);
      return categoryMatch && textMatch;
    });
  }, [query, category, lang]);

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
          <button className="locationChip" onClick={() => window.location.href = "/nearby.html"}><MapPin size={17}/> {t.location}: Phnom Penh <ChevronRight size={16}/></button>
          <div className="filterChips">
            {t.quick.map((label) => <button key={label}>{label}</button>)}
          </div>
        </section>

        <section className="section">
          <div className="quickHeader">
            <h2>{t.categories}</h2>
            <span className="verified"><ShieldCheck size={16}/> {t.verified}</span>
          </div>
          <div className="categoryGrid">
            {categories.slice(0,8).map((item) => (
              <button
                className={`category ${category === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => setCategory(category === item.id ? "all" : item.id)}
              >
                <span>{item.icon}</span><small>{item.label[lang]}</small>
              </button>
            ))}
          </div>
          <button className="allCategories" onClick={() => setCategory("all")}>{t.allJobs} <ChevronRight size={16}/></button>
        </section>

        <section className="section jobs">
          <div className="sectionTitle"><h2>{category === "all" ? t.recommended : categories.find(c => c.id === category)?.label[lang]}</h2><span>{visibleJobs.length} jobs</span></div>
          {visibleJobs.map((job) => (
            <article className="jobCard" key={job.id}>
              <div className="jobTop">
                <div className="factoryIcon"><Building2 size={24}/></div>
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
                {job.urgent && <span className="urgent">{t.urgent}{job.headcount ? ` · ${job.headcount}` : ""}</span>}
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
        <button onClick={() => window.location.href = "/nearby.html"}><MapPin/><span>{t.navNearby}</span></button>
        <button><MessageCircle/><span>{t.navChat}</span></button>
        <button><Building2/><span>{t.navApps}</span></button>
        <button onClick={() => window.location.href = "/auth.html"}><UserRound/><span>{t.navMe}</span></button>
      </nav>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
