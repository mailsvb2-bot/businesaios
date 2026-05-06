import React, { useMemo, useState } from "react";

function cx(...classes) {
  return classes.filter(Boolean).join(" ");
}

const statusMeta = {
  production_ready: { label: "Готово", tone: "green" },
  implemented: { label: "Реализовано", tone: "green" },
  partial: { label: "Частично", tone: "yellow" },
  contract_only: { label: "Контракт", tone: "blue" },
  not_implemented: { label: "Не реализовано", tone: "red" },
  not_found: { label: "Не найдено", tone: "red" },
};

function tone(t) {
  const map = {
    green: "border-emerald-200 bg-emerald-50 text-emerald-950",
    yellow: "border-amber-200 bg-amber-50 text-amber-950",
    red: "border-red-200 bg-red-50 text-red-950",
    blue: "border-sky-200 bg-sky-50 text-sky-950",
    dark: "border-slate-900 bg-slate-950 text-white",
    white: "border-white/70 bg-white/82 text-slate-950",
    soft: "border-slate-200 bg-slate-50 text-slate-950",
  };
  return map[t] || map.soft;
}

function Pill({ children, color = "soft" }) {
  return <span className={cx("inline-flex rounded-full border px-3 py-1 text-xs font-black", tone(color))}>{children}</span>;
}

function Button({ children, variant = "dark", className = "", ...props }) {
  const variants = {
    dark: "bg-slate-950 text-white hover:bg-black",
    green: "bg-emerald-600 text-white hover:bg-emerald-700",
    white: "border border-slate-200 bg-white text-slate-950 hover:bg-slate-50",
  };
  return <button className={cx("rounded-2xl px-5 py-3 text-sm font-black shadow-sm transition", variants[variant], className)} {...props}>{children}</button>;
}

function Panel({ children, className = "" }) {
  return <section className={cx("rounded-[2rem] border p-5 shadow-[0_24px_90px_rgba(15,23,42,0.08)] backdrop-blur", tone("white"), className)}>{children}</section>;
}

function SectionTitle({ eyebrow, title, subtitle, right }) {
  return (
    <div className="mb-7 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div>
        {eyebrow ? <div className="mb-2 text-xs font-black uppercase tracking-[0.2em] text-slate-400">{eyebrow}</div> : null}
        <h2 className="max-w-4xl text-4xl font-black tracking-tight md:text-5xl">{title}</h2>
        {subtitle ? <p className="mt-3 max-w-3xl text-lg font-bold leading-8 text-slate-500">{subtitle}</p> : null}
      </div>
      {right ? <div className="flex flex-wrap gap-2">{right}</div> : null}
    </div>
  );
}

function fallbackLanding() {
  return {
    sections: {
      hero: {
        eyebrow: "Business AI OS",
        title: "BusinesAIOS управляет продажами, рисками и повторными деньгами микробизнеса.",
        subtitle: "Публичный сайт показывает только то, что подтверждено backend capability catalog.",
        canonical_flow: "world_state → DecisionCore → guard → execution → verification → evidence",
      },
      use_cases: [],
      products: [],
      capabilities: { summary: {}, cards: [], policy: {} },
      canon_flow: [],
      roadmap: [],
      cta: { title: "Начать с одного доказанного живого контура.", text: "Сначала e2e, потом масштабирование." },
    },
    publication: { safe_to_publish: true, violations: [] },
  };
}

function Hero({ hero }) {
  return (
    <div className="overflow-hidden rounded-[2.5rem] border border-slate-900 bg-slate-950 p-6 text-white shadow-[0_30px_120px_rgba(15,23,42,0.28)] md:p-10">
      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[1.15fr_0.85fr] xl:items-center">
        <div>
          <div className="mb-6 flex flex-wrap gap-2">
            <span className="rounded-full bg-white px-4 py-2 text-xs font-black uppercase tracking-wide text-slate-950">{hero.eyebrow}</span>
            <span className="rounded-full bg-emerald-400/15 px-4 py-2 text-xs font-black text-emerald-100">автопилот микробизнеса</span>
            <span className="rounded-full bg-amber-400/15 px-4 py-2 text-xs font-black text-amber-100">без ложных обещаний</span>
          </div>
          <h1 className="max-w-5xl text-5xl font-black leading-[0.98] tracking-tight md:text-7xl">{hero.title}</h1>
          <p className="mt-6 max-w-3xl text-xl font-black leading-9 text-white/72">{hero.subtitle}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button variant="green">Посмотреть cockpit</Button>
            <Button variant="white">Карта подключений</Button>
          </div>
        </div>
        <div className="rounded-[2rem] border border-white/10 bg-white/10 p-5">
          <div className="text-xs font-black uppercase tracking-wide text-white/50">Канонический путь</div>
          <div className="mt-2 text-2xl font-black leading-9">{hero.canonical_flow}</div>
          <div className="mt-5 rounded-2xl bg-amber-400/12 p-4 text-amber-100">
            <div className="text-xs font-black uppercase tracking-wide opacity-70">Важно</div>
            <div className="mt-1 text-base font-black leading-6">Реклама, деньги, скидки и доступы не работают без guardrails и evidence.</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Capabilities({ capabilities }) {
  const [filter, setFilter] = useState("all");
  const cards = capabilities.cards || [];
  const statuses = useMemo(() => ["all", ...Object.keys(statusMeta)], []);
  const visible = useMemo(() => (filter === "all" ? cards : cards.filter((item) => item.status === filter)), [cards, filter]);
  const count = (status) => cards.filter((item) => item.status === status).length;

  return (
    <Panel>
      <SectionTitle
        eyebrow="Подключения"
        title="Карта каналов берётся из backend capability catalog."
        subtitle="Не готовые каналы не должны выглядеть как подключаемые. Это защита от ложного маркетинга и второго источника истины."
        right={
          <>
            <Pill color="green">{count("implemented") + count("production_ready")} реализовано</Pill>
            <Pill color="yellow">{count("partial")} частично</Pill>
            <Pill color="blue">{count("contract_only")} контракт</Pill>
            <Pill color="red">{count("not_implemented") + count("not_found")} roadmap</Pill>
          </>
        }
      />
      <div className="mb-5 flex flex-wrap gap-2">
        {statuses.map((status) => (
          <button key={status} onClick={() => setFilter(status)} className={cx("rounded-full border px-4 py-2 text-xs font-black transition", filter === status ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}>
            {status === "all" ? "Все" : statusMeta[status].label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {visible.map((item) => {
          const meta = statusMeta[item.status] || statusMeta.not_found;
          return (
            <div key={item.id} className={cx("rounded-[1.75rem] border p-5", tone(meta.tone))}>
              <div className="flex flex-wrap gap-2"><Pill color={meta.tone}>{meta.label}</Pill><Pill>{item.group}</Pill></div>
              <h3 className="mt-4 text-2xl font-black">{item.title}</h3>
              <p className="mt-3 text-sm font-bold leading-6 opacity-75">{item.owner_text}</p>
              <div className="mt-4 rounded-2xl bg-white/70 p-3 text-sm font-black">Следующий шаг: {item.next_required_step}</div>
              <Button variant={item.connectable ? "green" : "white"} className="mt-4 w-full" disabled={!item.connectable}>{item.connectable ? "Открыть подключение" : "Пока roadmap"}</Button>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

export default function BusinesAIOSLanding({ landing }) {
  const data = landing || fallbackLanding();
  const sections = data.sections;
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,#ffedd5,transparent_28%),radial-gradient(circle_at_top_right,#dbeafe,transparent_30%),linear-gradient(135deg,#f8fafc_0%,#f6f1e8_46%,#eef2ff_100%)] p-4 text-slate-950 md:p-7">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-4 rounded-[2rem] border border-white/70 bg-white/82 p-4 shadow-[0_24px_90px_rgba(15,23,42,0.08)] backdrop-blur md:flex-row md:items-center md:justify-between md:p-5">
          <div className="flex items-center gap-3"><div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-xl font-black text-white">B</div><div><div className="text-2xl font-black tracking-tight">BusinesAIOS</div><div className="text-sm font-bold text-slate-500">Behavioral Operating System для автономного микробизнеса</div></div></div>
          <nav className="flex flex-wrap gap-2"><Button variant="white">Возможности</Button><Button variant="white">Канон</Button><Button variant="dark">Owner Cockpit</Button></nav>
        </header>
        <Hero hero={sections.hero} />
        <Panel><SectionTitle eyebrow="Что это даёт" title="Владелец видит деньги, решения и риски." /> <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">{(sections.use_cases || []).map((item) => <div key={item.title} className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5"><h3 className="text-2xl font-black">{item.title}</h3><p className="mt-3 text-sm font-bold leading-6 text-slate-600">{item.text}</p></div>)}</div></Panel>
        <Panel><SectionTitle eyebrow="Экосистема" title="Один BusinesAIOS — несколько подключаемых бизнесов." /> <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">{(sections.products || []).map((item) => <div key={item.name} className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5"><h3 className="text-3xl font-black">{item.name}</h3><p className="mt-3 text-base font-bold leading-7 text-slate-600">{item.text}</p></div>)}</div></Panel>
        <Capabilities capabilities={sections.capabilities || { cards: [] }} />
        <Panel><SectionTitle eyebrow="Канон" title="Система не должна иметь второй мозг." /> <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">{(sections.canon_flow || []).map((item) => <div key={item.step} className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5"><div className="text-xs font-black text-slate-400">{item.step}</div><h3 className="mt-3 text-2xl font-black">{item.title}</h3><p className="mt-3 text-sm font-bold leading-6 text-slate-600">{item.text}</p></div>)}</div></Panel>
        <Panel><SectionTitle eyebrow="Что дальше" title="Сначала доказать полезные контуры, потом расширять каналы." /> <div className="space-y-3">{(sections.roadmap || []).map((item) => <div key={item.title} className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4"><div className="text-xl font-black">{item.title}</div><div className="mt-1 text-sm font-bold leading-6 text-slate-600">{item.text}</div></div>)}</div></Panel>
        <div className="rounded-[2.5rem] border border-emerald-900 bg-gradient-to-br from-emerald-900 via-slate-950 to-slate-950 p-7 text-white shadow-[0_30px_120px_rgba(15,23,42,0.25)] md:p-10"><h2 className="max-w-4xl text-4xl font-black leading-tight md:text-6xl">{sections.cta?.title}</h2><p className="mt-5 max-w-3xl text-lg font-bold leading-8 text-white/70">{sections.cta?.text}</p></div>
      </div>
    </div>
  );
}
