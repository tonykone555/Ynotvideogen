"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Aperture,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleDot,
  Clapperboard,
  Download,
  Film,
  Gauge,
  ImagePlus,
  Layers3,
  LoaderCircle,
  Lock,
  Menu,
  MonitorPlay,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  WandSparkles,
  X,
  Zap,
} from "lucide-react";

type ShotStatus = "planned" | "queued" | "generating" | "generated" | "failed";

type AdShot = {
  id: string;
  purpose: "hook" | "hero" | "benefit" | "cta";
  duration_seconds: number;
  prompt: string;
  negative_prompt: string;
  camera_style: string;
  continuity_note: string;
  status: ShotStatus;
  assets: string[];
  error?: string | null;
};

type AdPlan = {
  concept: string;
  platform: string;
  style: string;
  angle: string;
  aspect_ratio: "9:16";
  mobile_safe_area: string;
  shots: AdShot[];
};

type AdJob = {
  id: string;
  status: "planned" | "queued" | "generating" | "ready_to_stitch" | "stitching" | "generated" | "failed";
  plan: AdPlan;
  final_asset?: string | null;
  error?: string | null;
};

const API = process.env.NEXT_PUBLIC_YNOT_API_BASE_URL || "http://127.0.0.1:8000";

const STYLE_OPTIONS = [
  ["Natural UGC", "Creator-shot, believable, lightly imperfect"],
  ["Premium", "Polished without feeling over-produced"],
  ["Luxury", "Rich lighting, tactile detail, restrained motion"],
  ["Clean Ecommerce", "Product-forward, bright and controlled"],
  ["Cinematic", "Atmospheric movement, depth and texture"],
  ["Editorial", "Fashion-led framing and composition"],
];

const ANGLES = [
  "Aesthetic",
  "Problem / Solution",
  "Lifestyle",
  "Feature-led",
  "Scroll-stopper",
  "Gift-worthy",
  "Transformation",
];

const TONES = ["Casual", "Aspirational", "Elegant", "Bold", "Playful", "Polished"];
const CAMERAS = ["Handheld", "Soft push-in", "Macro detail", "Tracking", "Locked-off", "Orbit"];
const PRESENCE = ["Hands only", "Full person", "No person", "POV", "Environment-led"];

const defaultPlan: AdPlan = {
  concept: "Natural premium mobile-first product ad",
  platform: "tiktok",
  style: "Natural UGC",
  angle: "Aesthetic",
  aspect_ratio: "9:16",
  mobile_safe_area: "Keep product/action in center 70%; reserve upper/lower edges for UI/text.",
  shots: [
    {
      id: "shot_1",
      purpose: "hook",
      duration_seconds: 2,
      status: "planned",
      assets: [],
      camera_style: "handheld phone-like micro movement",
      continuity_note: "Same product identity and lighting language across all shots.",
      negative_prompt: "stiff acting, stock-footage smile, warped product, fake CGI gloss",
      prompt: "Open mid-action with a believable human interaction in the first half-second. Product should read instantly on a phone.",
    },
    {
      id: "shot_2",
      purpose: "hero",
      duration_seconds: 2,
      status: "planned",
      assets: [],
      camera_style: "slow natural push-in",
      continuity_note: "Preserve shape, colour, material and logo placement.",
      negative_prompt: "catalogue spin, geometry drift, overdramatic movement",
      prompt: "Let the product become clearly readable with one tactile detail and premium real-world lighting.",
    },
    {
      id: "shot_3",
      purpose: "benefit",
      duration_seconds: 2,
      status: "planned",
      assets: [],
      camera_style: "observational lifestyle",
      continuity_note: "Show the payoff naturally without jumping into an unrelated world.",
      negative_prompt: "forced pose, fake reaction, disconnected setting",
      prompt: "Show why someone would want it through a natural action or consequence, not a literal demonstration pose.",
    },
    {
      id: "shot_4",
      purpose: "cta",
      duration_seconds: 2,
      status: "planned",
      assets: [],
      camera_style: "settled premium framing",
      continuity_note: "Finish in the same visual language and preserve exact product identity.",
      negative_prompt: "baked-in text, fake logos, abrupt freeze frame",
      prompt: "End on a satisfying natural final moment with clean space for YNOT to add CTA text later.",
    },
  ],
};

const purposeMeta = {
  hook: ["01", "HOOK", "Stop the scroll"],
  hero: ["02", "HERO", "Make the product readable"],
  benefit: ["03", "PAYOFF", "Make the desire obvious"],
  cta: ["04", "CLOSE", "Leave them with the product"],
} as const;

function Pill({active, children, onClick}:{active?:boolean; children:React.ReactNode; onClick?:()=>void}) {
  return <button type="button" onClick={onClick} className={"pill " + (active ? "pillActive" : "")}>{children}</button>;
}

function StatusDot({status}:{status: ShotStatus | AdJob["status"]}) {
  const label = status.replaceAll("_"," ");
  return <span className={"status status-" + status}><i />{label}</span>;
}

export default function StudioPage() {
  const [style, setStyle] = useState("Natural UGC");
  const [angle, setAngle] = useState("Aesthetic");
  const [tone, setTone] = useState("Casual");
  const [camera, setCamera] = useState("Handheld");
  const [presence, setPresence] = useState("Hands only");
  const [productTitle, setProductTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("Home & Living");
  const [platform, setPlatform] = useState("tiktok");
  const [duration, setDuration] = useState(2);
  const [productImage, setProductImage] = useState<string | null>(null);
  const [productFile, setProductFile] = useState<File | null>(null);
  const [remoteImageUrl, setRemoteImageUrl] = useState("");
  const [plan, setPlan] = useState<AdPlan>(defaultPlan);
  const [selectedShot, setSelectedShot] = useState(0);
  const [job, setJob] = useState<AdJob | null>(null);
  const [busy, setBusy] = useState<"plan"|"generate"|null>(null);
  const [error, setError] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(true);
  const [motion, setMotion] = useState(42);
  const [realism, setRealism] = useState(86);
  const [polish, setPolish] = useState(58);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const combination = useMemo(() => [style, angle, tone, camera, presence].join(" · "), [style, angle, tone, camera, presence]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (productImage?.startsWith("blob:")) URL.revokeObjectURL(productImage);
    };
  }, [productImage]);

  function onImage(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (productImage?.startsWith("blob:")) URL.revokeObjectURL(productImage);
    setProductFile(file);
    setProductImage(URL.createObjectURL(file));
    setRemoteImageUrl("");
  }

  async function uploadReference() {
    if (remoteImageUrl.trim()) return remoteImageUrl.trim();
    if (!productFile) throw new Error("Add a product image first.");
    const form = new FormData();
    form.append("file", productFile);
    const res = await fetch(API + "/v1/uploads", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Image upload failed.");
    const data = await res.json();
    setRemoteImageUrl(data.url);
    return data.url as string;
  }

  function requestBody(url: string) {
    return {
      product_title: productTitle || "Untitled product",
      product_description: description,
      category,
      platform,
      style: style.toLowerCase(),
      angle: angle.toLowerCase(),
      aspect_ratio: "9:16",
      shots: 4,
      shot_duration_seconds: duration,
      reference_images: [{ url, role: "product", lock_identity: true }],
      metadata: {
        tone: tone.toLowerCase(),
        camera_preference: camera.toLowerCase(),
        human_presence: presence.toLowerCase(),
        motion_strength: motion,
        realism_level: realism,
        polish_level: polish,
        studio_combination: combination,
      },
    };
  }

  async function makePlan() {
    setError("");
    setBusy("plan");
    try {
      const url = await uploadReference();
      const res = await fetch(API + "/v1/ads/plan", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(requestBody(url)),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Could not build storyboard.");
      setPlan(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not build storyboard.");
    } finally {
      setBusy(null);
    }
  }

  async function generate() {
    setError("");
    setBusy("generate");
    try {
      const url = await uploadReference();
      const res = await fetch(API + "/v1/ads/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(requestBody(url)),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Generation could not start.");
      const next: AdJob = await res.json();
      setJob(next);
      setPlan(next.plan);
      startPolling(next.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation could not start.");
    } finally {
      setBusy(null);
    }
  }

  function startPolling(id: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(API + "/v1/ads/" + id, { cache: "no-store" });
        if (!res.ok) return;
        const next: AdJob = await res.json();
        setJob(next);
        setPlan(next.plan);
        if (next.status === "generated" || next.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch {}
    }, 3500);
  }

  const selected = plan.shots[selectedShot] || plan.shots[0];

  return (
    <main className="appShell">
      <aside className="rail">
        <div className="brandMark">Y</div>
        <nav className="railNav">
          <button className="railBtn railBtnActive"><WandSparkles size={18}/></button>
          <button className="railBtn"><Layers3 size={18}/></button>
          <button className="railBtn"><Film size={18}/></button>
          <button className="railBtn"><Gauge size={18}/></button>
        </nav>
        <button className="railBtn railBottom"><Settings2 size={18}/></button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <div className="eyebrow">YNOT / GENERATIVE CREATIVE</div>
            <h1>Gen Studio <span className="beta">BETA</span></h1>
          </div>
          <div className="topActions">
            <div className="engineBadge"><span className="pulse"/> WAN 2.2 <b>READY PIPELINE</b></div>
            <button className="iconBtn"><Menu size={18}/></button>
          </div>
        </header>

        <div className="studioGrid">
          <section className="leftPanel panel">
            <div className="panelHeader">
              <div><span className="panelKicker">01</span><h2>Creative setup</h2></div>
              <button className="ghostBtn"><RefreshCw size={14}/> Reset</button>
            </div>

            <label className="uploadCard">
              {productImage ? (
                <>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={productImage} alt="Product preview"/>
                  <div className="uploadShade"/>
                  <span className="replace"><ImagePlus size={15}/> Replace</span>
                </>
              ) : (
                <div className="uploadEmpty">
                  <span className="uploadIcon"><ImagePlus size={21}/></span>
                  <strong>Drop product reference</strong>
                  <small>JPG, PNG or WebP · up to 25MB</small>
                </div>
              )}
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onImage}/>
            </label>

            <div className="fieldGrid">
              <label className="field fieldWide">
                <span>Product</span>
                <input value={productTitle} onChange={e=>setProductTitle(e.target.value)} placeholder="e.g. Sculpt lounge chair"/>
              </label>
              <label className="field">
                <span>Category</span>
                <select value={category} onChange={e=>setCategory(e.target.value)}>
                  <option>Home & Living</option><option>Fashion</option><option>Beauty</option><option>Tech</option><option>Fitness</option><option>Accessories</option>
                </select>
              </label>
              <label className="field">
                <span>Platform</span>
                <select value={platform} onChange={e=>setPlatform(e.target.value)}>
                  <option value="tiktok">TikTok</option><option value="instagram">Instagram Reels</option><option value="youtube">YouTube Shorts</option><option value="pinterest">Pinterest</option>
                </select>
              </label>
              <label className="field fieldWide">
                <span>Description</span>
                <textarea value={description} onChange={e=>setDescription(e.target.value)} placeholder="What should the model understand about this product?"/>
              </label>
            </div>

            <div className="sectionBlock">
              <div className="sectionTitle"><span>Creative direction</span><small>Choose the base language</small></div>
              <div className="styleCards">
                {STYLE_OPTIONS.map(([name,desc])=><button key={name} className={"styleCard "+(style===name?"active":"")} onClick={()=>setStyle(name)}>
                  <strong>{name}</strong><span>{desc}</span>{style===name&&<Check size={14}/>}
                </button>)}
              </div>
            </div>

            <div className="sectionBlock">
              <div className="sectionTitle"><span>Angle</span><small>What makes the idea work?</small></div>
              <div className="pills">{ANGLES.map(v=><Pill key={v} active={angle===v} onClick={()=>setAngle(v)}>{v}</Pill>)}</div>
            </div>

            <button className="advancedToggle" onClick={()=>setAdvancedOpen(v=>!v)}>
              <span><Settings2 size={15}/> Direction controls</span><ChevronDown size={16} className={advancedOpen?"turn":""}/>
            </button>

            {advancedOpen && <div className="advanced">
              <div className="miniGroup"><span>Tone</span><div className="pills mini">{TONES.map(v=><Pill key={v} active={tone===v} onClick={()=>setTone(v)}>{v}</Pill>)}</div></div>
              <div className="miniGroup"><span>Camera</span><div className="pills mini">{CAMERAS.map(v=><Pill key={v} active={camera===v} onClick={()=>setCamera(v)}>{v}</Pill>)}</div></div>
              <div className="miniGroup"><span>Presence</span><div className="pills mini">{PRESENCE.map(v=><Pill key={v} active={presence===v} onClick={()=>setPresence(v)}>{v}</Pill>)}</div></div>
              <div className="sliders">
                <label><span>Realism <b>{realism}%</b></span><input type="range" min="0" max="100" value={realism} onChange={e=>setRealism(+e.target.value)}/></label>
                <label><span>Motion <b>{motion}%</b></span><input type="range" min="0" max="100" value={motion} onChange={e=>setMotion(+e.target.value)}/></label>
                <label><span>Polish <b>{polish}%</b></span><input type="range" min="0" max="100" value={polish} onChange={e=>setPolish(+e.target.value)}/></label>
              </div>
            </div>}

            <div className="comboBar">
              <Sparkles size={15}/><div><small>ACTIVE COMBINATION</small><span>{combination}</span></div>
            </div>

            {error && <div className="errorBox"><CircleDot size={14}/><span>{error}</span></div>}

            <div className="actionRow">
              <button className="secondaryBtn" disabled={!!busy} onClick={makePlan}>{busy==="plan"?<LoaderCircle className="spin" size={16}/>:<Clapperboard size={16}/>} Build storyboard</button>
              <button className="primaryBtn" disabled={!!busy} onClick={generate}>{busy==="generate"?<LoaderCircle className="spin" size={17}/>:<Zap size={17}/>} Generate ad <ArrowUpRight size={15}/></button>
            </div>
          </section>

          <section className="centerPanel panel">
            <div className="panelHeader">
              <div><span className="panelKicker">02</span><h2>Storyboard lab</h2></div>
              <div className="variantTabs"><button className="variant active">A</button><button className="variant">B</button><button className="variant">C</button><button className="variant add"><Plus size={13}/></button></div>
            </div>

            <div className="conceptCard">
              <div className="conceptTop"><span>CONCEPT A</span><Lock size={13}/></div>
              <h3>{plan.concept}</h3>
              <p>{plan.mobile_safe_area}</p>
              <div className="conceptMeta"><span>9:16 PORTRAIT</span><span>4 SHOTS</span><span>{(duration*4).toFixed(0)} SEC</span></div>
            </div>

            <div className="shotStrip">
              {plan.shots.map((shot,index)=>{
                const [num,label,tagline]=purposeMeta[shot.purpose];
                return <button key={shot.id} onClick={()=>setSelectedShot(index)} className={"shotCard "+(selectedShot===index?"selected":"")}>
                  <div className="shotTop"><span>{num}</span><StatusDot status={shot.status}/></div>
                  <div className="portraitFrame">
                    {shot.assets?.[0] ? <video src={shot.assets[0]} muted playsInline/> : <><div className="frameGlow"/><Aperture size={20}/></>}
                    <span className="duration">{shot.duration_seconds}s</span>
                  </div>
                  <strong>{label}</strong><small>{tagline}</small>
                </button>
              })}
            </div>

            <div className="promptWorkspace">
              <div className="promptHead">
                <div><span className="panelKicker">{purposeMeta[selected.purpose][0]}</span><div><h3>{purposeMeta[selected.purpose][1]} prompt</h3><small>{selected.camera_style}</small></div></div>
                <div className="promptTools"><button><Lock size={13}/> Lock</button><button><RefreshCw size={13}/> Rewrite</button></div>
              </div>
              <textarea className="promptArea" value={selected.prompt} onChange={e=>{
                const copy={...plan,shots:[...plan.shots]}; copy.shots[selectedShot]={...copy.shots[selectedShot],prompt:e.target.value}; setPlan(copy);
              }}/>
              <div className="promptBands">
                <div><span>CONTINUITY</span><p>{selected.continuity_note}</p></div>
                <div><span>NEGATIVE</span><p>{selected.negative_prompt}</p></div>
              </div>
            </div>

            <div className="combinationMatrix">
              <div className="matrixHead"><div><Sparkles size={16}/><span>Combination builder</span></div><button><Plus size={13}/> Save as preset</button></div>
              <div className="matrixFlow">
                <span>{style}</span><i>+</i><span>{angle}</span><i>+</i><span>{camera}</span><i>+</i><span>{presence}</span>
              </div>
              <p>YNOT passes this combination into every shot while keeping product identity and mobile-safe framing locked.</p>
            </div>
          </section>

          <section className="rightPanel panel">
            <div className="panelHeader">
              <div><span className="panelKicker">03</span><h2>Render monitor</h2></div>
              {job ? <StatusDot status={job.status}/> : <span className="status status-planned"><i/>idle</span>}
            </div>

            <div className="renderStage">
              <div className="device">
                <div className="deviceIsland"/>
                {job?.final_asset ? (
                  <video className="finalVideo" src={job.final_asset} controls playsInline autoPlay loop/>
                ) : (
                  <div className="deviceEmpty">
                    <div className="orb"><Sparkles size={22}/></div>
                    <strong>Your final ad lives here</strong>
                    <p>Four generated moments. One clean vertical story.</p>
                    <div className="safeGuide"><span/><span/></div>
                  </div>
                )}
              </div>
              <div className="renderMeta">
                <span>1080 × 1920</span><span>30 FPS</span><span>H.264</span>
              </div>
            </div>

            <div className="queue">
              <div className="queueHead"><span>SHOT QUEUE</span><small>{plan.shots.filter(s=>s.status==="generated").length}/4 complete</small></div>
              {plan.shots.map((shot,index)=>{
                const meta=purposeMeta[shot.purpose];
                return <div className="queueItem" key={shot.id}>
                  <span className="queueNo">{meta[0]}</span>
                  <div className="queueText"><strong>{meta[1]}</strong><small>{shot.camera_style}</small></div>
                  <StatusDot status={shot.status}/>
                  <button className="tinyBtn" title="Regenerate shot" disabled><RefreshCw size={13}/></button>
                </div>
              })}
            </div>

            <div className="stitchCard">
              <div className="stitchIcon"><MonitorPlay size={18}/></div>
              <div><strong>Auto stitch</strong><p>{job?.status==="stitching"?"Normalizing and stitching the four portrait shots…":"Starts automatically after every shot is ready."}</p></div>
              {job?.status==="stitching"?<LoaderCircle className="spin" size={18}/>:<Check size={16}/>}
            </div>

            <div className="outputActions">
              <button className="outputPrimary" disabled={!job?.final_asset} onClick={()=>job?.final_asset && window.open(job.final_asset,"_blank")}><Download size={16}/> Download final MP4</button>
              <button className="outputSecondary" disabled={!job?.final_asset}><Layers3 size={16}/> Create variant</button>
            </div>

            <div className="providerCard">
              <div><span className="providerDot"/><div><strong>Generation engine</strong><small>Modal · Wan 2.2 · L40S</small></div></div>
              <span className="providerTag">AUTO</span>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
