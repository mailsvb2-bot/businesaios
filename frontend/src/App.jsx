import { useCallback, useEffect, useMemo, useState } from "react";
import { AcquisitionPlanner } from "./AcquisitionPlanner.jsx";
import { BusinessIntelligencePanel } from "./BusinessIntelligencePanel.jsx";

const DEFAULT_API = import.meta.env.VITE_API_BASE || "https://api.businessaios.ru";

const GOALS = [
  { value: "growth", title: "Больше клиентов", text: "Найти потери в воронке и точки роста продаж." },
  { value: "retention", title: "Возвращать клиентов", text: "Находить клиентов, которых стоит реактивировать." },
  { value: "ads_efficiency", title: "Эффективнее реклама", text: "Искать неэффективный расход и проблемы атрибуции." },
  { value: "sales", title: "Сильнее продажи", text: "Показывать зависшие сделки и пропущенные повторные контакты с клиентом." },
  { value: "operations", title: "Меньше рутины", text: "Находить повторяющиеся операции и задержки исполнения." }
];

const AUTONOMY = [
  { value: "advisor", title: "Советник", badge: "Самый безопасный старт", text: "Анализирует бизнес и предлагает действия. Ничего сам не отправляет и не тратит." },
  { value: "assistant", title: "Помощник", badge: "Рекомендуем после знакомства", text: "Автоматизирует безопасные шаги, а важные действия отправляет вам на подтверждение." },
  { value: "autopilot", title: "Автопилот", badge: "После проверки интеграций", text: "Целевой режим автономной работы в заданных лимитах. Включается только после проверок безопасности." }
];

const STEP_LABELS = ["О бизнесе", "Цель", "Интеграции", "Режим"];

const INITIAL_FORM = {
  email: "",
  business_name: "",
  website: "",
  industry: "",
  city: "",
  business_model: "services",
  goal: "growth",
  autonomy_mode: "advisor"
};

async function readResponse(resp) {
  const text = await resp.text();
  let parsed;
  try {
    parsed = text ? JSON.parse(text) : {};
  } catch {
    parsed = { raw: text };
  }
  if (!resp.ok) {
    const error = new Error(parsed?.detail || `HTTP ${resp.status}`);
    error.httpStatus = Number(resp.status || 0);
    error.serverResponded = true;
    throw error;
  }
  return parsed;
}

async function getJson(url, headers = {}) {
  return readResponse(await fetch(url, { headers, credentials: "include" }));
}

async function postJson(url, payload, headers = {}) {
  return readResponse(await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(payload),
    credentials: "include"
  }));
}

function initialIntakeId() {
  try {
    return new URLSearchParams(window.location.search).get("intake_id") || "";
  } catch {
    return "";
  }
}

function isValidEmail(value) {
  const email = String(value || "").trim();
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function providerInitial(title) {
  return String(title || "?").trim().slice(0, 2).toUpperCase();
}

function statusClass(item) {
  if (item.availability === "available_read_only") return "ready";
  if (item.availability === "preparing") return "preparing";
  return "roadmap";
}

function IntegrationCard({ item, selected, onToggle }) {
  return (
    <button type="button" disabled={!item.selectable} className={`integration-card ${selected ? "selected" : ""} ${!item.selectable ? "disabled" : ""}`} aria-pressed={selected} onClick={item.selectable ? () => onToggle(item) : undefined}>
      <div className="integration-card-head"><span className="provider-logo">{providerInitial(item.title)}</span>{item.recommended ? <span className="recommended">Рекомендуем</span> : null}</div>
      <strong>{item.title}</strong>
      <small>{item.description}</small>
      <span className={`status-pill ${statusClass(item)}`}>{selected ? "Выбрано ✓" : item.availability_label}</span>
    </button>
  );
}

const PROVIDER_CONNECTION_GUIDANCE = {
  vk_messaging: { label: "Сообщество VK", placeholder: "Например, ID или ссылка на сообщество", truth: "Чтение сообщений VK готово. Отправка сообщений остаётся выключенной, пока вы отдельно её не разрешите.", help: "Для нативного чтения укажите Group Access Token. Group ID и Callback Confirmation Code — обычные настройки; Bridge Webhook Secret нужен для совместимого защищённого bridge-пути." },
  max_messaging: { label: "Бот MAX", placeholder: "Например, ID или имя бота", truth: "Чтение сообщений MAX готово. Отправка сообщений остаётся выключенной, пока вы отдельно её не разрешите.", help: "Укажите Bot Access Token для нативного чтения. Bridge Webhook Secret сохраняет совместимость с защищённым webhook-путём." },
  slack_messaging: { label: "Рабочее пространство Slack", placeholder: "Например, имя или ID workspace", truth: "Входящие события Slack принимаются с проверкой подлинности. Отправка сообщений выключена.", help: "В Slack Event Subscriptions укажите Webhook URL ниже. Поле Slack Signing Secret хранится как секрет и используется для проверки каждого входящего запроса." },
  discord_messaging: { label: "Приложение Discord", placeholder: "Например, Application ID или имя сервера", truth: "Входящие HTTP-события Discord принимаются с проверкой подлинности. Постоянное Gateway-подключение и отправка сообщений этим подключением пока не включены.", help: "В Discord Developer Portal укажите Webhook URL ниже. Application Public Key — публичная настройка для Ed25519; Bridge Webhook Secret остаётся обязательным для совместимого bridge-пути." },
  instagram_messaging: { label: "Instagram Professional", placeholder: "Например, имя профессионального аккаунта", truth: "Входящие сообщения проверяются по Meta App Secret. Нативная отправка идёт только через подтверждаемую очередь и не объявляет канал полностью live-ready без внешней проверки Meta.", help: "Укажите Webhook URL ниже в настройках Meta App. Для нативной отправки нужны Instagram Access Token и Instagram Professional User ID; получатель должен сначала написать вашему профессиональному аккаунту." },
  messenger_messaging: { label: "Facebook Page", placeholder: "Например, название или ID страницы", truth: "Входящие сообщения проверяются по Meta App Secret. Нативная отправка идёт только через подтверждаемую очередь и не объявляет канал полностью live-ready без внешней проверки Meta.", help: "Укажите Webhook URL ниже в настройках Meta App. Для нативной отправки нужны Page Access Token и Facebook Page ID; действуют правила Messenger по разрешённому окну сообщений." },
  line_messaging: { label: "LINE Official Account", placeholder: "Например, имя официального аккаунта", truth: "Входящие события LINE проверяются по Channel Secret. Нативная отправка идёт только через подтверждаемую очередь; чтение истории через API не заявляется.", help: "Укажите Webhook URL ниже в LINE Developers Console. Для нативной отправки нужен Channel Access Token; получатель должен быть user/group/room ID, полученным от LINE webhook." },
  viber_messaging: { label: "Viber Bot", placeholder: "Например, имя бота", truth: "Входящие события Viber проверяются по Bot Auth Token. Нативная отправка идёт только через подтверждаемую очередь; произвольная отправка неподписанным пользователям не заявляется.", help: "Укажите Webhook URL ниже в настройках Viber Bot. Для нативной отправки нужны Bot Auth Token и Sender Name; receiver должен быть ID подписанного пользователя, полученным от Viber." },
};

function connectionIdentityCopy(provider) {
  const key = String(provider?.provider_key || "").toLowerCase();
  if (PROVIDER_CONNECTION_GUIDANCE[key]) return PROVIDER_CONNECTION_GUIDANCE[key];
  if (key.includes("website") || key.includes("wordpress") || key.includes("webflow")) {
    return { label: "Сайт или проект", placeholder: "Например, https://example.ru" };
  }
  if (key.includes("marketplace") || key.includes("ozon") || key.includes("wildberries")) {
    return { label: "Кабинет или магазин", placeholder: "Например, ID кабинета продавца" };
  }
  return { label: "Аккаунт или кабинет", placeholder: "Например, ID аккаунта или адрес кабинета" };
}

function credentialInputType(field) {
  return new Set(["config", "url", "username", "oauth_client"]).has(String(field?.secret_kind || "").toLowerCase()) ? "text" : "password";
}

function credentialLabel(provider, field) {
  const key = String(provider?.provider_key || "").toLowerCase();
  if (field?.secret_name === "webhook_secret" && key === "slack_messaging") return "Slack Signing Secret";
  if (field?.secret_name === "webhook_secret" && ["vk_messaging", "max_messaging", "discord_messaging"].includes(key)) return "Bridge Webhook Secret";
  return field?.label || field?.secret_name || "Поле доступа";
}

function providerTruthCopy(provider) {
  const key = String(provider?.provider_key || "").toLowerCase();
  if (PROVIDER_CONNECTION_GUIDANCE[key]?.truth) return PROVIDER_CONNECTION_GUIDANCE[key].truth;
  if (provider?.truth_status === "read_only_ready" || provider?.live_ready) return "Чтение готово. Изменения во внешней системе выключены.";
  if (provider?.customer_selectable) return "Источник доступен для безопасного анализа в режиме чтения.";
  return "Подключение ещё готовится.";
}

function capabilitySurfaceLabel(surface) {
  return surface === "acquisition" ? "Привлечение и возврат клиентов" : surface === "interaction" ? "Общение и работа с клиентами" : "Системная возможность";
}

function capabilityUserState(item, catalog) {
  if (!item?.connectable) return { label: "Готовится", className: "roadmap", provider: null };
  const providers = (item?.provider_keys || []).map((key) => catalog.find((row) => row.provider_key === key)).filter(Boolean);
  const provider = providers.find((row) => row.connected) || providers.find((row) => row.customer_selectable) || providers[0] || null;
  if (provider?.connected) return { label: "Подключено", className: "ready", provider };
  if (provider?.customer_selectable) return { label: "Можно подключить", className: "ready", provider };
  if (!providers.length) return { label: "Доступно в системе", className: "preparing", provider: null };
  return { label: "Часть функций готова", className: "preparing", provider };
}

function capabilityPlainCopy(item, state) {
  const available = [];
  if (item?.read_supported && (!state.provider || state.provider.read_supported)) available.push("читать данные");
  if (item?.verify_supported) available.push("проверять входящие события");
  if (item?.write_supported && state.provider?.write_supported) available.push("готовить внешнее действие с вашим подтверждением");
  if (available.length) return `${state.provider && !state.provider.connected ? "После подключения" : "Сейчас"} можно: ${available.join(", ")}.`;
  return item?.connectable ? "Базовый контур уже есть, но отдельный пользовательский шаг ещё не открыт." : "Пользовательский путь пока не открыт — функция остаётся в плане доработки.";
}

function providerWebhookUrl(apiBase, data, provider) {
  const key = String(provider?.provider_key || "").toLowerCase();
  if (!PROVIDER_CONNECTION_GUIDANCE[key] || !data?.tenant_id || !data?.business_id) return "";
  return `${String(apiBase || "").replace(/\/$/, "")}/providers/webhook/${encodeURIComponent(data.tenant_id)}/${encodeURIComponent(data.business_id)}/${encodeURIComponent(key)}`;
}

function messagingChannelForProvider(providerKey) {
  const key = String(providerKey || "");
  return key === "email_connector" ? "email" : key.endsWith("_messaging") ? key.slice(0, -10) : "";
}

function providerRecipientContext(providerKey, recipient) {
  const key = String(providerKey || "");
  if (["slack_messaging", "discord_messaging"].includes(key)) return { channel_id: recipient };
  if (["instagram_messaging", "messenger_messaging"].includes(key)) return { recipient_id: recipient };
  if (key === "line_messaging") return { to: recipient };
  if (key === "viber_messaging") return { receiver: recipient };
  if (key === "vk_messaging") return { peer_id: recipient };
  if (key === "max_messaging") return { chat_id: recipient };
  return {};
}

function recipientFieldCopy(providerKey) {
  const key = String(providerKey || "");
  if (key === "email_connector") return { label: "Email получателя", placeholder: "name@example.com" };
  if (["slack_messaging", "discord_messaging"].includes(key)) return { label: "ID канала", placeholder: "ID канала, куда нужно отправить сообщение" };
  if (key === "vk_messaging") return { label: "ID получателя или диалога", placeholder: "ID пользователя или диалога ВКонтакте" };
  if (key === "max_messaging") return { label: "ID чата", placeholder: "ID чата MAX" };
  if (["instagram_messaging", "messenger_messaging", "line_messaging", "viber_messaging"].includes(key)) return { label: "ID получателя", placeholder: "ID получателя в выбранном канале" };
  return { label: "Получатель", placeholder: "ID пользователя, чата, канала или email" };
}

function approvalMessagePreview(row) {
  const metadata = row?.metadata || {};
  const resume = metadata.approval_resume_context || {};
  const payload = resume.payload || {};
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const nestedText = messages.find((item) => item && typeof item === "object" && item.text)?.text;
  return {
    providerKey: String(resume.provider_key || ""),
    recipient: String(payload.recipient || payload.user_id || payload.channel || payload.channel_id || payload.recipient_id || payload.to || payload.receiver || payload.peer_id || payload.chat_id || ""),
    text: String(payload.body || payload.text || payload.message || nestedText || ""),
    subject: String(payload.subject || "")
  };
}

function approvalMatchesPreparedMessage(row, expected) {
  const preview = approvalMessagePreview(row);
  const expectedSubject = String(expected.subject || "");
  const subjectMatches = preview.subject === expectedSubject
    || (expected.providerKey === "email_connector" && !expectedSubject && preview.subject === "BusinessAIOS notification");
  return preview.providerKey === expected.providerKey
    && preview.recipient === expected.recipient
    && preview.text === expected.text
    && subjectMatches;
}

function approvalMatchesDraftIdentity(row, tenantId, actionId) {
  const tenant = String(tenantId || "").trim();
  const action = String(actionId || "").trim();
  if (!tenant || !action) return false;
  const expectedDecisionId = `api-command:${tenant}:${action}`;
  const metadata = row?.metadata || {};
  return [row?.decision_id, row?.subject_id, metadata.decision_id]
    .some((value) => String(value || "") === expectedDecisionId);
}

function providerKeyFromActionName(actionName) {
  const match = /^provider\.([^.]+)\.message_send$/.exec(String(actionName || ""));
  return match ? match[1] : "";
}

function resumeCandidateQueueJobId(candidate) {
  const providerKey = providerKeyFromActionName(candidate?.action_name);
  const fingerprint = String(candidate?.subject_fingerprint || "").trim();
  return providerKey && fingerprint ? `provider-sync-${providerKey}-${fingerprint.slice(0, 32)}` : "";
}

function providerHistoryDisposition(providerKey, row) {
  const status = String(row?.status || "").trim();
  const parsed = row?.parsed_response || {};
  const errorCategory = String(row?.error?.category || "").trim();
  const acceptedWithReceipt = row?.accepted === true && status === "live_executed" && Boolean(String(parsed.resource_id || "").trim());
  let delivered = acceptedWithReceipt;
  let acceptedWithoutDeliveryProof = false;
  if (String(providerKey || "") === "email_connector" && acceptedWithReceipt) {
    delivered = row?.transport_response?.smtp?.delivered === true;
    acceptedWithoutDeliveryProof = !delivered;
  }
  const ambiguous = acceptedWithoutDeliveryProof || ["", "ambiguous_delivery", "in_progress"].includes(status) || status.startsWith("provider_queue_")
    || (status === "live_execution_failed" && !String(parsed.error_code || "").trim()) || errorCategory === "ambiguous_delivery";
  const terminalNonDelivery = !delivered && !ambiguous && (["rejected_misconfigured", "rejected_provider_write_guard", "rejected_provider_write_requires_queue", "live_transport_unbound", "unsupported_operation"].includes(status)
    || (status === "live_execution_failed" && Boolean(String(parsed.error_code || "").trim())));
  return delivered ? "delivered" : terminalNonDelivery ? "terminal_non_delivery" : ambiguous ? "ambiguous" : "unknown";
}

function resumeCandidateHistoryDisposition(candidate, rows) {
  const serverDisposition = String(candidate?.completion_disposition || "");
  if (["delivered", "terminal_non_delivery", "ambiguous", "unknown"].includes(serverDisposition)) return serverDisposition;
  const jobId = resumeCandidateQueueJobId(candidate);
  const providerKey = providerKeyFromActionName(candidate?.action_name);
  const matching = (rows || []).filter((row) => String(row?.queue_job_id || "") === jobId)
    .sort((left, right) => String(right?.recorded_at_utc || "").localeCompare(String(left?.recorded_at_utc || "")))[0];
  return jobId && matching ? providerHistoryDisposition(providerKey, matching) : "unknown";
}

function resumeCandidateCompleted(candidate, rows) {
  return resumeCandidateHistoryDisposition(candidate, rows) === "delivered";
}

function approvalDecisionMatchesCorrelation(row, correlationToken, expectedOutcome) {
  const marker = `[owner-correlation:${String(correlationToken || "")}]`;
  return Boolean(correlationToken) && (Array.isArray(row?.decisions) ? row.decisions : []).some((decision) =>
    String(decision?.rationale || "").includes(marker)
      && String(decision?.outcome || "").toLowerCase() === String(expectedOutcome || "").toLowerCase());
}

function isSuccessfulLiveEvidence(row) {
  return String(row?.mode || "").toLowerCase() === "live"
    && row?.accepted === true
    && String(row?.status || "").toLowerCase() === "live_executed";
}

function latestSuccessfulOperationEvidence(rows, operation) {
  return (rows || []).filter((row) => isSuccessfulLiveEvidence(row) && String(row?.operation || "") === operation)
    .sort((left, right) => String(right?.recorded_at_utc || "").localeCompare(String(left?.recorded_at_utc || "")))[0] || null;
}

function evidenceResourceCount(row) {
  const value = row?.parsed_response?.resource_count ?? row?.transport_response?.resource_count;
  return value === null || value === undefined || !Number.isFinite(Number(value)) ? null : Number(value);
}

function evidenceHasNextPage(row) {
  return Boolean(row?.parsed_response?.next_cursor ?? row?.transport_response?.next_cursor);
}

function evidenceTimeLabel(row) {
  const value = String(row?.recorded_at_utc || "").trim();
  if (!value) return "Время не указано";
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? "Время не указано" : timestamp.toLocaleString("ru-RU");
}

function Workspace({ data, apiBase, businesses, onRestart, onRetryAccess, onSwitchBusiness }) {
  const profile = data.business_profile || {};
  const progress = data.onboarding_progress || {};
  const preview = data.first_value_preview || {};
  const integrations = data.integration_plan || [];
  const ownerSession = data.owner_session || {};
  const apiKey = ownerSession.api_key || "";
  const baseApi = apiBase.replace(/\/$/, "");
  const workspaceUrl = `${baseApi}/business-workspace/providers`;
  const actionExecuteUrl = `${baseApi}/actions/execute`;
  const approvalsUrl = `${baseApi}/control-plane/approvals/open?business_id=${encodeURIComponent(data.business_id)}`;
  const approvalResumeUrl = `${baseApi}/control-plane/provider-runtime/approval-resume`;
  const customersUrl = `${baseApi}/business-workspace/customers`;
  const acquisitionUrl = `${baseApi}/business-workspace/acquisition-plan`;
  const analyticsUrl = `${baseApi}/analytics/dashboard/${encodeURIComponent(data.tenant_id)}?window_days=30`;
  const memorySummaryUrl = `${baseApi}/business-memory/summary`;
  const memoryRecentUrl = `${baseApi}/business-memory/recent-runs`;
  const goalExecuteUrl = `${baseApi}/goals/execute`;
  const decisionDraftUrl = `${baseApi}/business-workspace/decision-draft`;
  const authHeaders = useMemo(() => (apiKey ? { "X-API-Key": apiKey } : {}), [apiKey]);
  const selectedKeys = useMemo(() => new Set(integrations.map((item) => item.provider_key)), [integrations]);
  const [catalog, setCatalog] = useState([]);
  const [capabilities, setCapabilities] = useState([]);
  const [activeKey, setActiveKey] = useState("");
  const [externalRef, setExternalRef] = useState("");
  const [secrets, setSecrets] = useState({});
  const [historyByProvider, setHistoryByProvider] = useState({});
  const [workspaceLoading, setWorkspaceLoading] = useState(Boolean(apiKey));
  const [workspaceBusy, setWorkspaceBusy] = useState("");
  const [workspaceError, setWorkspaceError] = useState("");
  const [accessRecoveryBusy, setAccessRecoveryBusy] = useState(false);
  const [lastAction, setLastAction] = useState(null);
  const [editingAccessKey, setEditingAccessKey] = useState("");
  const [operations, setOperations] = useState({ approvals: [] });
  const [operationProviderKey, setOperationProviderKey] = useState("");
  const [operationRecipient, setOperationRecipient] = useState("");
  const [operationSubject, setOperationSubject] = useState("");
  const [operationText, setOperationText] = useState("");
  const [operationBusy, setOperationBusy] = useState("");
  const [operationError, setOperationError] = useState("");
  const [operationResult, setOperationResult] = useState(null);
  const [operationQueueStale, setOperationQueueStale] = useState(false);
  const [operationRecovery, setOperationRecovery] = useState(null);
  const [operationDraftKey, setOperationDraftKey] = useState(() => crypto.randomUUID());
  const [operationOrigin, setOperationOrigin] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [customerTimeline, setCustomerTimeline] = useState([]);
  const [customerBusy, setCustomerBusy] = useState(false);
  const [customerError, setCustomerError] = useState("");
  const [salesBusy, setSalesBusy] = useState(false);
  const [salesError, setSalesError] = useState("");

  const markOperationStale = (recovery) => { setOperationRecovery(recovery); setOperationQueueStale(true); };
  const clearOperationStale = () => { setOperationRecovery(null); setOperationQueueStale(false); };

  const refreshCatalog = async () => {
    if (!apiKey) return [];
    const payload = await getJson(workspaceUrl, authHeaders);
    const rows = Array.isArray(payload.providers) ? payload.providers : [];
    setCatalog(rows);
    setCapabilities(Array.isArray(payload.capabilities) ? payload.capabilities : []);
    setActiveKey((current) => {
      if (current && rows.some((row) => row.provider_key === current)) return current;
      return rows.find((row) => selectedKeys.has(row.provider_key) && row.customer_selectable)?.provider_key
        || rows.find((row) => row.customer_selectable)?.provider_key
        || "";
    });
    return rows;
  };

  const refreshOperations = async (approvalId = "") => {
    if (!apiKey) { setOperations({ approvals: [], resumeCandidates: [] }); return { approvals: [], resumeCandidates: [], lookup: null }; }
    const payload = await getJson(`${approvalsUrl}${approvalId ? `&approval_id=${encodeURIComponent(approvalId)}` : ""}`, authHeaders);
    const approvals = (Array.isArray(payload.records) ? payload.records : []).filter((row) => {
      const action = String(row?.metadata?.action_name || "");
      const businessId = String(row?.metadata?.approval_resume_context?.business_id || row?.metadata?.business_id || "");
      return action.startsWith("provider.") && action.endsWith(".message_send") && businessId === String(data.business_id || "");
    });
    const resumeCandidates = (Array.isArray(payload.resume_candidates) ? payload.resume_candidates : []).filter((row) => {
      const action = String(row?.action_name || "");
      return action.startsWith("provider.") && action.endsWith(".message_send") && row?.resume_ready === true && String(row?.business_id || "") === String(data.business_id || "");
    });
    const next = {
      approvals,
      resumeCandidates,
      lookup: payload.lookup && typeof payload.lookup === "object" ? payload.lookup : null,
      timeline: Array.isArray(payload.timeline) ? payload.timeline : []
    };
    setOperations(next); return next;
  };

  const refreshCustomers = async () => {
    if (!apiKey) {
      setCustomers([]);
      setSelectedCustomerId("");
      setCustomerTimeline([]);
      return [];
    }
    setCustomerBusy(true);
    setCustomerError("");
    try {
      const payload = await getJson(customersUrl, authHeaders);
      const rows = Array.isArray(payload.customers) ? payload.customers : [];
      setCustomers(rows);
      setSelectedCustomerId((current) => current && rows.some((row) => row.customer_id === current) ? current : (rows[0]?.customer_id || ""));
      return rows;
    } catch {
      setCustomerError("Не удалось загрузить клиентов. Внешние действия не выполнялись.");
      return [];
    } finally {
      setCustomerBusy(false);
    }
  };

  const loadCustomerTimeline = async (customerId) => {
    if (!apiKey || !customerId) { setCustomerTimeline([]); return []; }
    setCustomerBusy(true);
    setCustomerError("");
    try {
      const payload = await getJson(`${customersUrl}?customer_id=${encodeURIComponent(customerId)}`, authHeaders);
      const rows = Array.isArray(payload.timeline?.entries) ? payload.timeline.entries : [];
      setCustomerTimeline(rows);
      return rows;
    } catch {
      setCustomerTimeline([]);
      setCustomerError("Не удалось открыть историю клиента.");
      return [];
    } finally {
      setCustomerBusy(false);
    }
  };

  const loadHistory = async (providerKey) => {
    if (!apiKey || !providerKey) return [];
    const payload = await getJson(`${workspaceUrl}?provider_key=${encodeURIComponent(providerKey)}`, authHeaders);
    const rows = Array.isArray(payload.history) ? payload.history : [];
    setHistoryByProvider((previous) => ({ ...previous, [providerKey]: rows }));
    return rows;
  };

  useEffect(() => {
    if (!apiKey) {
      setWorkspaceLoading(false);
      return;
    }
    let cancelled = false;
    setWorkspaceLoading(true);
    refreshCatalog()
      .then(async (rows) => {
        await Promise.all(rows.filter((row) => row.connected).map((row) => loadHistory(row.provider_key)));
        await refreshOperations();
        await refreshCustomers();
      })
      .catch(() => {
        if (!cancelled) setWorkspaceError("Не удалось открыть защищённый список подключений. Проверьте соединение и повторите попытку.");
      })
      .finally(() => {
        if (!cancelled) setWorkspaceLoading(false);
      });
    return () => { cancelled = true; };
  }, [apiKey]);

  const providers = catalog
    .filter((row) => row.connected || row.customer_selectable || selectedKeys.has(row.provider_key))
    .sort((left, right) => Number(Boolean(right.connected)) - Number(Boolean(left.connected)) || Number(selectedKeys.has(right.provider_key)) - Number(selectedKeys.has(left.provider_key)) || String(left.title || "").localeCompare(String(right.title || ""), "ru"));
  const capabilityRows = capabilities.map((item) => ({ ...item, userState: capabilityUserState(item, catalog) }));
  const actionableCapabilities = capabilityRows.filter((item) => item.connectable && (item.userState.provider?.connected || item.userState.provider?.customer_selectable));
  const otherCapabilities = capabilityRows.filter((item) => !actionableCapabilities.includes(item));
  const activeProvider = providers.find((row) => row.provider_key === activeKey) || providers[0] || null;
  const liveEvidenceByProvider = useMemo(() => {
    const entries = Object.entries(historyByProvider).flatMap(([providerKey, rows]) => {
      const evidence = (rows || []).find(isSuccessfulLiveEvidence);
      return evidence ? [[providerKey, evidence]] : [];
    });
    return new Map(entries);
  }, [historyByProvider]);
  const liveEvidence = Array.from(liveEvidenceByProvider.values())[0] || null;
  const activeLiveEvidence = activeProvider ? liveEvidenceByProvider.get(activeProvider.provider_key) || null : null;
  const connected = providers.some((row) => row.connected);
  const baseCompleted = Math.min(Number(progress.completed || 0), 4);
  const verifiedCompleted = Math.min(6, baseCompleted + (connected ? 1 : 0) + (liveEvidence ? 1 : 0));
  const verifiedPercent = Math.round((verifiedCompleted / 6) * 100);
  const evidenceProvider = liveEvidence ? catalog.find((row) => row.provider_key === liveEvidence.provider_key) : null;
  const resourceCount = liveEvidence?.parsed_response?.resource_count ?? liveEvidence?.transport_response?.resource_count;
  const identityCopy = connectionIdentityCopy(activeProvider);
  const webhookUrl = providerWebhookUrl(baseApi, data, activeProvider);
  const syncActionLabel = workspaceBusy === "sync"
    ? (activeLiveEvidence ? "Обновляем данные…" : "Получаем данные…")
    : (activeLiveEvidence ? "Обновить данные" : "Получить первые данные");
  const hubspotProvider = catalog.find((row) => row.provider_key === "hubspot") || null;
  const hubspotHistory = historyByProvider.hubspot || [];
  const hubspotContactEvidence = latestSuccessfulOperationEvidence(hubspotHistory, "contact_sync");
  const hubspotDealEvidence = latestSuccessfulOperationEvidence(hubspotHistory, "deal_sync");
  const hubspotLastEvidence = [hubspotContactEvidence, hubspotDealEvidence].filter(Boolean).sort((left, right) => String(right.recorded_at_utc || "").localeCompare(String(left.recorded_at_utc || "")))[0] || null;
  const hubspotContactCount = evidenceResourceCount(hubspotContactEvidence);
  const hubspotDealCount = evidenceResourceCount(hubspotDealEvidence);
  const hubspotReadOperations = new Set(hubspotProvider?.runtime_plan?.read_operations || []);
  const hubspotCanRefreshSales = Boolean(hubspotProvider?.connected && hubspotReadOperations.has("contact_sync") && hubspotReadOperations.has("deal_sync"));
  const hubspotRecentReads = hubspotHistory.filter((row) => ["contact_sync", "deal_sync"].includes(String(row?.operation || ""))).slice(0, 4);

  const operationProviders = catalog.filter((row) => row.write_supported).map((row) => {
    const required = Array.isArray(row.transport_binding?.live_required_secrets) ? row.transport_binding.live_required_secrets : [];
    const bound = new Set(Array.isArray(row.bound_secret_fields) ? row.bound_secret_fields : []);
    const missing = required.filter((name) => !bound.has(name));
    const canRequest = Boolean(row.connected && row.write_supported && row.approval_required === true && missing.length === 0);
    return { ...row, can_request_write: canRequest, missing_live_credentials: missing, status: canRequest ? "ready_for_approval" : !row.connected ? "connect_provider_first" : missing.length ? "live_credentials_missing" : row.approval_required !== true ? "approval_not_required" : "write_not_ready" };
  });
  const readyOperationProviders = operationProviders.filter((row) => row.can_request_write);
  const activeOperationProvider = readyOperationProviders.find((row) => row.provider_key === operationProviderKey) || readyOperationProviders[0] || null;
  const operationRecipientCopy = recipientFieldCopy(activeOperationProvider?.provider_key);
  const pendingApprovals = Array.isArray(operations.approvals) ? operations.approvals : [];
  const serverResumeCandidates = Array.isArray(operations.resumeCandidates) ? operations.resumeCandidates : [];
  const resumeCandidates = serverResumeCandidates.filter((item) => {
    const providerKey = providerKeyFromActionName(item?.action_name);
    return !["delivered", "terminal_non_delivery"].includes(resumeCandidateHistoryDisposition(item, historyByProvider[providerKey] || []));
  });
  const terminalResumeCandidates = serverResumeCandidates.filter((item) => {
    const providerKey = providerKeyFromActionName(item?.action_name);
    return resumeCandidateHistoryDisposition(item, historyByProvider[providerKey] || []) === "terminal_non_delivery";
  });
  const operationDecisionProvenance = operationResult?.execution?.decision_provenance || null;
  const operationProviderResult = operationResult?.execution?.execution?.result || null;
  const operationProviderAccepted = Boolean(operationProviderResult?.accepted) && String(operationProviderResult?.status || "") === "live_executed";
  const operationProviderResourceId = String(operationProviderResult?.parsed_response?.resource_id || "");
  const selectedCustomer = customers.find((row) => row.customer_id === selectedCustomerId) || customers[0] || null;
  const providerKeyForChannel = (channel) => channel === "email" ? "email_connector" : `${channel}_messaging`;
  const readyIdentityProvider = (identity) => readyOperationProviders.find((row) => row.provider_key === providerKeyForChannel(identity.channel));

  useEffect(() => {
    if (selectedCustomerId) void loadCustomerTimeline(selectedCustomerId);
    else setCustomerTimeline([]);
  }, [selectedCustomerId, apiKey]);

  const prepareForCustomer = (identity) => {
    if (operationQueueStale) {
      setOperationError("Сначала обновите очередь подтверждений. Неразрешённый запрос сохраняет прежний idempotency key и черновик нельзя менять до сверки.");
      document.getElementById("business-operations-title")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const provider = readyIdentityProvider(identity);
    if (!provider) {
      setOperationError(`Канал ${identity.channel} пока не готов к отправке. Проверьте доступ выше.`);
      return;
    }
    setOperationProviderKey(provider.provider_key);
    setOperationRecipient(String(identity.external_subject || ""));
    setOperationSubject("");
    setOperationDraftKey(crypto.randomUUID());
    setOperationError("");
    document.getElementById("business-operations-title")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const runOperation = async (name, url, payload, headers = authHeaders) => {
    setOperationBusy(name);
    setOperationError("");
    const draftRecovery = { kind: "draft", actionId: operationDraftKey };
    let result = null;
    try {
      result = await postJson(url, payload, headers);
      setOperationResult(result);
    } catch (error) {
      const status = Number(error?.httpStatus || 0);
      const definitiveClientRejection = error?.serverResponded === true && status >= 400 && status < 500 && status !== 408;
      if (definitiveClientRejection) {
        setOperationError(`Запрос отклонён сервером (HTTP ${status}). Черновик сохранён и остаётся редактируемым; внешнее действие не подтверждено.`);
      } else {
        markOperationStale(draftRecovery);
        setOperationError("Ответ на запрос не получен или сервер не подтвердил безопасный отказ. Не повторяйте действие вслепую: сначала обновите очередь — тот же черновик сохранит idempotency key.");
      }
      setOperationBusy("");
      return null;
    }
    try {
      const nextOperations = await refreshOperations();
      return { result, nextOperations };
    } catch {
      markOperationStale(draftRecovery);
      setOperationError("Запрос обработан, но очередь подтверждений не обновилась. Не повторяйте действие — сначала обновите очередь.");
      return { result, nextOperations: null };
    } finally { setOperationBusy(""); }
  };

  const refreshActionQueue = async () => {
    setOperationBusy("refresh_queue"); setOperationError("");
    const recovery = operationRecovery || { kind: "draft", actionId: operationDraftKey };
    try {
      const snapshot = await refreshOperations(recovery.kind === "draft" ? "" : recovery.approvalId);
      if (recovery.kind === "decision") {
        const record = snapshot.lookup;
        const status = String(record?.status || "").toLowerCase();
        const ownDecision = approvalDecisionMatchesCorrelation(record, recovery.correlationToken, recovery.outcome);
        if (!record) {
          clearOperationStale();
          setOperationError("Approval больше не найден в tenant-scoped хранилище. Повторять старое решение нельзя; очередь разблокирована без догадки о статусе.");
        } else if (["approved", "rejected", "expired", "cancelled"].includes(status) || (status === "requested" && ownDecision)) {
          clearOperationStale();
          setOperationError(status === "requested" ? "Ваше решение найдено по собственному correlation marker. Approval всё ещё ждёт другого подтверждения." : `Фактический статус approval подтверждён targeted lookup: «${status}». Повторять решение не нужно.`);
        } else {
          markOperationStale(recovery);
          setOperationError("Targeted lookup видит approval, но именно ваше решение ещё не доказано. Не повторяйте его вслепую — обновите очередь ещё раз.");
        }
        return;
      }
      if (recovery.kind === "resume") {
        const candidate = (snapshot.resumeCandidates || []).find((row) => String(row?.approval_id || "") === String(recovery.approvalId || ""));
        const signal = candidate || { action_name: recovery.actionName, subject_fingerprint: recovery.subjectFingerprint };
        const providerKey = providerKeyFromActionName(signal?.action_name);
        const rows = providerKey ? await loadHistory(providerKey) : [];
        const disposition = resumeCandidateHistoryDisposition(signal, rows);
        if (["delivered", "terminal_non_delivery"].includes(disposition) || candidate) {
          clearOperationStale();
          setOperationError(disposition === "delivered" ? "Выполнение подтверждено provider-history. Recovery больше не нужен." : disposition === "terminal_non_delivery" ? "Provider-history доказал окончательный отказ без доставки. Повторный resume не нужен; исправьте условия и подготовьте новое действие." : "Approval подтверждён и остаётся доступен в безопасной очереди восстановления выполнения.");
        } else {
          markOperationStale(recovery);
          setOperationError("Не удалось доказать ни завершённое выполнение, ни доступный resume. Не создавайте новое действие — повторите обновление очереди.");
        }
        return;
      }
      const providerKey = activeOperationProvider?.provider_key || "";
      const recipient = operationRecipient.trim();
      const text = operationText.trim();
      const subject = operationSubject.trim();
      const actionId = String(recovery.actionId || operationDraftKey);
      const alreadyPrepared = Boolean(providerKey && recipient && text)
        && (snapshot.approvals || []).some((row) => approvalMatchesDraftIdentity(row, data.tenant_id, actionId)
          && approvalMatchesPreparedMessage(row, { providerKey, recipient, text, subject }));
      if (alreadyPrepared) {
        clearOperationStale();
        setOperationText(""); setOperationSubject("");
        setOperationOrigin(null);
        setOperationDraftKey(crypto.randomUUID());
        setOperationError("Действие уже найдено в очереди подтверждений. Повторная подготовка не нужна.");
      } else {
        markOperationStale({ kind: "draft", actionId });
        setOperationError("Очередь обновлена, но действие ещё не найдено. Неопределённый запрос остаётся заблокированным и сохраняет прежний idempotency key до доказанной сверки.");
      }
    } catch {
      markOperationStale(recovery);
      setOperationError("Не удалось обновить очередь. Неразрешённая операция остаётся заблокированной до доказанной сверки.");
    } finally { setOperationBusy(""); }
  };

  const prepareMessage = async ({ allowStaleRetry = false } = {}) => {
    const sameDraftRetry = allowStaleRetry && operationRecovery?.kind === "draft" && String(operationRecovery?.actionId || "") === String(operationDraftKey || "");
    if (operationQueueStale && !sameDraftRetry) {
      setOperationError("Сначала обновите очередь подтверждений. Повторная подготовка заблокирована, чтобы не создать дубликат.");
      return;
    }
    if (!activeOperationProvider || !operationRecipient.trim() || !operationText.trim()) {
      setOperationError("Выберите готовый канал, укажите получателя и текст сообщения.");
      return;
    }
    const recipient = operationRecipient.trim();
    const messageText = operationText.trim();
    const subjectText = operationSubject.trim();
    const providerKey = activeOperationProvider.provider_key;
    const draftOrigin = operationOrigin ? {
      source: "owner_decision_draft",
      source_run_id: String(operationOrigin.run_id || ""),
      source_decision_id: String(operationOrigin.decision_id || ""),
      source_action_id: String(operationOrigin.action_id || "")
    } : null;
    const outcome = await runOperation("message_send", actionExecuteUrl, {
      action_type: "send_message@v1",
      payload: { business_id: data.business_id, user_id: recipient, text: messageText, channel: messagingChannelForProvider(providerKey), kind: operationOrigin ? "owner_decision_draft" : "owner_manual", ...providerRecipientContext(providerKey, recipient), ...(subjectText ? { subject: subjectText } : {}), ...(draftOrigin ? { track_payload: draftOrigin } : {}) }
    }, { ...authHeaders, "X-Idempotency-Key": operationDraftKey, "X-Action-ID": operationDraftKey });
    if (!outcome || !outcome.nextOperations) return;
    const preparedApproval = (outcome.nextOperations.approvals || []).some((row) => approvalMatchesDraftIdentity(row, data.tenant_id, operationDraftKey)
      && approvalMatchesPreparedMessage(row, { providerKey, recipient, text: messageText, subject: subjectText }));
    const resultStatus = String(outcome.result?.status || "").toLowerCase();
    const resultReason = String(outcome.result?.reason || outcome.result?.details?.guard_stage || "").toLowerCase();
    const idempotencyInProgress = resultStatus === "blocked" && resultReason === "idempotency_in_progress";
    if (resultStatus === "ok" || preparedApproval) {
      clearOperationStale();
      setOperationText("");
      setOperationSubject("");
      setOperationOrigin(null);
      setOperationDraftKey(crypto.randomUUID());
    } else if (idempotencyInProgress) {
      markOperationStale({ kind: "draft", actionId: operationDraftKey });
      setOperationError("Этот же запрос ещё обрабатывается. Idempotency key сохранён — не создавайте новое действие, сначала обновите очередь.");
    } else {
      clearOperationStale();
      setOperationDraftKey(crypto.randomUUID());
      setOperationError("Действие не подготовлено. Текст оставлен в форме — проверьте причину в технических деталях и исправьте условия.");
    }
  };

  const decideApproval = async (approvalId, approve) => {
    setOperationBusy(`approval:${approvalId}`); setOperationError("");
    const before = pendingApprovals.find((row) => String(row.approval_id || "") === String(approvalId)) || null;
    const decisionOutcome = approve ? "approve" : "reject";
    const correlationToken = crypto.randomUUID();
    const correlationMarker = `[owner-correlation:${correlationToken}]`;
    const rationale = `${approve ? "Владелец подтвердил" : "Владелец отклонил"} действие в кабинете BusinessAIOS. ${correlationMarker}`;
    const actionName = String(before?.metadata?.action_name || before?.action_name || "");
    const subjectFingerprint = String(before?.subject_fingerprint || before?.metadata?.subject_fingerprint || "");
    const providerKey = providerKeyFromActionName(actionName);
    const decisionRecovery = { kind: "decision", approvalId, correlationToken, outcome: decisionOutcome, actionName, subjectFingerprint };
    const resumeRecovery = { kind: "resume", approvalId, actionName, subjectFingerprint };
    let decision = null;
    let finalRecovery = decisionRecovery;
    try {
      decision = await postJson(`${baseApi}/control-plane/approvals/${encodeURIComponent(approvalId)}/decide`, { outcome: decisionOutcome, rationale }, authHeaders);
    } catch (error) {
      const status = Number(error?.httpStatus || 0);
      const definitiveClientRejection = error?.serverResponded === true && status >= 400 && status < 500 && status !== 408;
      if (definitiveClientRejection) {
        setOperationError(`Решение отклонено сервером (HTTP ${status}). Approval не менялся; очередь остаётся доступной для корректного решения.`);
        await refreshOperations().catch(() => null);
        setOperationBusy("");
        return;
      }
      try {
        const snapshot = await refreshOperations();
        const pending = (snapshot.approvals || []).find((row) => String(row.approval_id || "") === String(approvalId));
        const timeline = (snapshot.timeline || []).find((row) => row?.kind === "approval" && String(row?.ref_id || "") === String(approvalId));
        const status = String(timeline?.status || pending?.status || "").toLowerCase();
        const ownDecision = approvalDecisionMatchesCorrelation(pending, correlationToken, decisionOutcome);
        if (approve && status === "approved") {
          try {
            const execution = await postJson(approvalResumeUrl, { approval_id: approvalId }, authHeaders);
            setOperationResult({ decision: { status: "approved", recovered: true }, execution });
            if (providerKey) await loadHistory(providerKey).catch(() => []);
            setOperationError("Approval уже подтверждён. BusinessAIOS продолжил выполнение по сохранённому approval без повторного голосования.");
          } catch {
            setOperationResult({ decision: { status: "approved", recovered: true }, execution: null });
            setOperationError("Approval подтверждён, но внешнее выполнение не доказано. Используйте отдельную recovery-карточку, не подтверждая approval заново.");
          }
        } else if (status === "rejected") {
          setOperationResult({ decision: { status: "rejected", recovered: true }, execution: null });
          setOperationError("Approval уже отклонён. Повторять решение не нужно.");
        } else if (status === "requested" && ownDecision) {
          setOperationResult({ decision: { status: "requested", recovered: true }, execution: null });
          setOperationError("Именно ваше решение найдено по correlation marker, но approval ещё ждёт дополнительного подтверждения.");
        } else if (status === "requested") {
          markOperationStale(decisionRecovery);
          setOperationError("Ответ на решение потерян, а именно ваш голос пока не найден. Не повторяйте решение вслепую — сначала обновите очередь.");
        } else if (status) {
          setOperationResult({ decision: { status, recovered: true }, execution: null });
          setOperationError(`Approval уже завершён со статусом «${status}». Повторять решение не нужно.`);
        } else {
          markOperationStale(decisionRecovery);
          setOperationError("Ответ на решение потерян, а фактический статус approval не удалось доказать. Не повторяйте решение — сначала обновите очередь.");
        }
      } catch {
        markOperationStale(decisionRecovery);
        setOperationError("Ответ на решение потерян, и фактический статус approval не удалось перечитать. Не повторяйте решение — сначала обновите очередь.");
      } finally { setOperationBusy(""); }
      return;
    }
    try {
      if (!approve || decision?.status !== "approved") {
        setOperationResult({ decision, execution: null });
        return;
      }
      finalRecovery = resumeRecovery;
      try {
        const execution = await postJson(approvalResumeUrl, { approval_id: approvalId }, authHeaders);
        setOperationResult({ decision, execution });
        if (providerKey) await loadHistory(providerKey).catch(() => []);
      } catch {
        setOperationResult({ decision, execution: null });
        setOperationError("Подтверждение сохранено, но внешнее выполнение не подтверждено. Используйте recovery-карточку этого approval, не подтверждая его повторно.");
      }
    } finally {
      try { await refreshOperations(); }
      catch {
        markOperationStale(finalRecovery);
        setOperationError((current) => current || "Решение обработано, но серверную истину не удалось перечитать. Обновите очередь — тип recovery сохранён.");
      }
      setOperationBusy("");
    }
  };

  const resumeApprovedOperation = async (approvalId) => {
    setOperationBusy(`resume:${approvalId}`); setOperationError("");
    const candidate = serverResumeCandidates.find((row) => String(row?.approval_id || "") === String(approvalId)) || null;
    const providerKey = providerKeyFromActionName(candidate?.action_name);
    const recovery = { kind: "resume", approvalId, actionName: String(candidate?.action_name || ""), subjectFingerprint: String(candidate?.subject_fingerprint || "") };
    try {
      const execution = await postJson(approvalResumeUrl, { approval_id: approvalId }, authHeaders);
      setOperationResult({ decision: { status: "approved", recovered: true }, execution });
      if (providerKey) await loadHistory(providerKey).catch(() => []);
      setOperationError("Выполнение проверено через сохранённый approval. Подтверждённый provider-history уберёт recovery-карточку; недоказанное выполнение останется доступно для безопасного resume.");
    } catch {
      setOperationResult({ decision: { status: "approved", recovered: true }, execution: null });
      setOperationError("Approval подтверждён, но выполнение всё ещё не доказано. Карточка восстановления сохранена — повторите resume, не подтверждая approval заново.");
    } finally {
      try { await refreshOperations(); }
      catch {
        markOperationStale(recovery);
        setOperationError((current) => current || "Статус выполнения не удалось перечитать. Recovery сохранён именно для этого approval.");
      }
      setOperationBusy("");
    }
  };

  const runWorkspaceAction = async (name, payload, providerKey = activeProvider?.provider_key) => {
    if (!providerKey) return null;
    setWorkspaceBusy(name);
    setWorkspaceError("");
    try {
      const result = await postJson(workspaceUrl, { provider_key: providerKey, ...payload }, authHeaders);
      setLastAction({ name, providerKey, result });
      await refreshCatalog();
      await refreshOperations().catch(() => null);
      if (name === "sync" || name === "probe") await loadHistory(providerKey);
      return result;
    } catch {
      setWorkspaceError("Действие не выполнено. Проверьте подключение и повторите попытку.");
      return null;
    } finally {
      setWorkspaceBusy("");
    }
  };

  const activateProvider = async () => {
    if (!activeProvider) return;
    const cleanSecrets = Object.fromEntries(Object.entries(secrets).filter(([, value]) => String(value || "").trim()));
    if (activeProvider.connected) {
      if (!Object.keys(cleanSecrets).length) {
        setWorkspaceError("Введите хотя бы один новый параметр доступа, который нужно добавить или заменить.");
        return;
      }
      setWorkspaceBusy("update_access"); setWorkspaceError("");
      try {
        await postJson(workspaceUrl, { action: "update_access", provider_key: activeProvider.provider_key, secrets: cleanSecrets }, authHeaders);
        setSecrets({}); setEditingAccessKey(""); await refreshCatalog(); await refreshOperations();
      } catch { setWorkspaceError("Не удалось обновить доступ. Старые сохранённые данные не удалялись."); }
      finally { setWorkspaceBusy(""); }
      return;
    }
    const requiredMissing = (activeProvider.secret_fields || []).some((field) => field.required && !String(secrets[field.secret_name] || "").trim());
    if (!externalRef.trim() || requiredMissing) {
      setWorkspaceError("Укажите аккаунт и заполните обязательные поля доступа.");
      return;
    }
    const result = await runWorkspaceAction("activate", { action: "activate", external_ref: externalRef.trim(), secrets: cleanSecrets });
    if (result) {
      setSecrets({});
      setEditingAccessKey("");
      await loadHistory(activeProvider.provider_key).catch(() => []);
    }
  };

  const probeProvider = async () => {
    await runWorkspaceAction("probe", { action: "read", mode: "live" });
  };

  const syncProvider = async () => {
    if (!activeProvider) return;
    const operation = activeProvider.runtime_plan?.read_operations?.[0];
    if (!operation) {
      setWorkspaceError("Для этого источника пока нет доступной операции чтения. Сначала проверьте подключение.");
      return;
    }
    await runWorkspaceAction("sync", { action: "read", mode: "live", operation, payload: {} });
  };

  const refreshSalesCenter = async () => {
    if (!hubspotProvider) { setSalesError("HubSpot пока не открыт для подключения в текущем реестре BusinessAIOS."); return; }
    if (!hubspotProvider.connected) { setSalesError(""); openCapabilityProvider("hubspot"); return; }
    if (!hubspotCanRefreshSales) { setSalesError("Подключение есть, но безопасное чтение контактов и сделок пока не открыто одновременно. Ничего внешнего не менялось."); return; }
    setSalesBusy(true); setSalesError("");
    try {
      for (const operation of ["contact_sync", "deal_sync"]) {
        const result = await postJson(workspaceUrl, { provider_key: "hubspot", action: "read", mode: "live", operation, payload: {} }, authHeaders);
        if (!isSuccessfulLiveEvidence(result)) throw new Error(`hubspot_sales_read_rejected:${operation}:${String(result?.status || "unknown")}`);
        setLastAction({ name: `sales_${operation}`, providerKey: "hubspot", result });
      }
      await refreshCatalog();
    } catch {
      setSalesError("Не все данные продаж удалось обновить. Внешних изменений не выполнялось — проверьте доступ HubSpot и повторите чтение.");
    } finally { await loadHistory("hubspot").catch(() => []); setSalesBusy(false); }
  };

  const openCapabilityProvider = (providerKey) => {
    if (!providerKey) return;
    setActiveKey(providerKey);
    setExternalRef("");
    setSecrets({});
    setEditingAccessKey("");
    requestAnimationFrame(() => document.getElementById("connections-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  const loadBusinessIntelligence = useCallback(async () => {
    if (!apiKey) return { analytics: null, memory: null, recentRuns: [], errors: ["session"] };
    const ownerScope = { tenant_id: data.tenant_id, business_id: data.business_id };
    const [analytics, memory, recent] = await Promise.allSettled([
      getJson(analyticsUrl, authHeaders),
      postJson(memorySummaryUrl, ownerScope, authHeaders),
      postJson(memoryRecentUrl, { ...ownerScope, limit: 5 }, authHeaders)
    ]);
    return {
      analytics: analytics.status === "fulfilled" ? analytics.value?.payload || null : null,
      memory: memory.status === "fulfilled" ? memory.value : null,
      recentRuns: recent.status === "fulfilled" && Array.isArray(recent.value?.runs) ? recent.value.runs : [],
      errors: [analytics, memory, recent].map((item, index) => item.status === "rejected" ? ["analytics", "memory", "recent_runs"][index] : null).filter(Boolean)
    };
  }, [apiKey, analyticsUrl, authHeaders, data.business_id, data.tenant_id, memoryRecentUrl, memorySummaryUrl]);

  const openWorkspaceSection = useCallback((sectionId) => {
    const target = String(sectionId || "").trim();
    if (!target) return;
    requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, []);

  const runAdvisoryGoal = useCallback(async (goal) => {
    if (!apiKey) throw new Error("owner_session_required");
    return postJson(goalExecuteUrl, {
      goal, business_id: data.business_id, tenant_id: data.tenant_id, max_steps: 1,
      profile: { industry: profile.industry || "", city: profile.city || "", business_model: profile.business_model || "" },
      meta: { source: "owner_workspace" }
    }, { ...authHeaders, "X-Idempotency-Key": crypto.randomUUID() });
  }, [apiKey, authHeaders, data.business_id, data.tenant_id, goalExecuteUrl, profile.business_model, profile.city, profile.industry]);

  const prepareDecisionAction = useCallback(async (goalResult) => {
    if (!apiKey) throw new Error("owner_session_required");
    if (operationQueueStale) throw new Error("action_queue_stale");
    const step = Array.isArray(goalResult?.steps) ? goalResult.steps[0] : null;
    if (!goalResult?.run_id || !step?.decision_id || !step?.action_id) throw new Error("decision_draft_identity_missing");
    const draft = await postJson(decisionDraftUrl, { run_id: goalResult.run_id, decision_id: step.decision_id, action_id: step.action_id }, authHeaders);
    const suggestedProvider = readyOperationProviders.find((row) => row.provider_key === draft.suggested_provider_key) || null;
    const customerMatches = (selectedCustomer?.identities || []).map((identity) => ({ identity, provider: readyIdentityProvider(identity) })).filter((item) => item.provider);
    const customerMatch = customerMatches.length === 1 ? customerMatches[0] : null;
    const provider = suggestedProvider || customerMatch?.provider || readyOperationProviders[0] || null;
    const recipient = suggestedProvider && draft.recipient ? String(draft.recipient) : String(customerMatch?.identity?.external_subject || "");
    setOperationProviderKey(provider?.provider_key || "");
    setOperationRecipient(recipient);
    setOperationSubject(provider?.provider_key === "email_connector" ? String(draft.subject || "") : "");
    setOperationText(String(draft.text || ""));
    setOperationOrigin(draft);
    setOperationDraftKey(crypto.randomUUID());
    setOperationError(recipient ? "" : "Черновик DecisionCore перенесён. Перед подготовкой выберите клиента или укажите получателя — BusinessAIOS не подставляет неизвестный адресат.");
    document.getElementById("business-operations-title")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return draft;
  }, [apiKey, authHeaders, decisionDraftUrl, operationQueueStale, readyOperationProviders, selectedCustomer]);

  const retryProtectedAccess = async () => {
    if (!data.intake_id || !onRetryAccess) return;
    setAccessRecoveryBusy(true);
    setWorkspaceError("");
    try {
      const restored = await onRetryAccess(data.intake_id);
      if (!restored) setWorkspaceError("Защищённый вход больше недоступен. Если срок безопасной сессии истёк, создайте новый кабинет.");
    } catch {
      setWorkspaceError("Не удалось повторно открыть защищённый вход. Проверьте соединение и повторите попытку.");
    } finally {
      setAccessRecoveryBusy(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/"><span className="brand-mark">B</span><span className="brand-name">BusinessAIOS</span></a>
        <div className="topbar-actions">
          <span className="safe-chip"><span className="safe-chip-full">{readyOperationProviders.length ? "Действия · только после подтверждения" : "Безопасный режим · чтение данных"}</span><span className="safe-chip-short">{readyOperationProviders.length ? "С подтверждением" : "Режим чтения"}</span></span>
          {businesses.length > 1 ? <label className="business-switcher"><span>Бизнес</span><select aria-label="Выбор бизнеса" value={data.intake_id} onChange={(event) => onSwitchBusiness(event.target.value)}>{businesses.map((item) => <option value={item.intake_id} key={item.intake_id}>{item.name || "Бизнес"}</option>)}</select></label> : null}
          <button className="ghost small add-business-button" aria-label="Добавить бизнес" onClick={onRestart}><span className="add-business-full">Добавить бизнес</span><span className="add-business-short">Добавить</span></button>
        </div>
      </header>

      <section className="workspace-hero">
        <div>
          <p className="eyebrow">Кабинет бизнеса</p>
          <h1>{profile.name || "Ваш бизнес"}</h1>
          <p className="lead">{liveEvidence ? "Первые реальные данные уже подтверждены. Ниже — результат и следующие безопасные действия." : "Сейчас задача одна: получить первый подтверждённый результат на ваших данных. Никаких отправок, изменений или расходов."}</p>
        </div>
        <div className="progress-card">
          <div className="progress-head"><span>До рабочего результата</span><strong>{verifiedPercent}%</strong></div>
          <div className="progress-track" role="progressbar" aria-label="Готовность подключения" aria-valuemin={0} aria-valuemax={100} aria-valuenow={verifiedPercent}><span style={{ width: `${verifiedPercent}%` }} /></div>
          <small>{liveEvidence ? "Первый подтверждённый результат получен." : connected ? "Источник подключён. Осталось получить первые данные." : "Следующий шаг: подключить выбранный источник."}</small>
        </div>
      </section>

      <section className="summary-grid">
        <article className="summary-card"><span className="summary-icon">◎</span><div><small>Цель</small><strong>{GOALS.find((goal) => goal.value === profile.goal)?.title || profile.goal || "Рост"}</strong></div></article>
        <article className="summary-card"><span className="summary-icon">⌁</span><div><small>Источники</small><strong>{providers.filter((row) => row.connected).length} подключено / {integrations.length} выбрано</strong></div></article>
        <article className="summary-card"><span className="summary-icon">◇</span><div><small>Режим</small><strong>{data.user_functionality?.autonomy_mode_label || "Советник"}</strong></div></article>
      </section>

      <section className="panel first-value-panel" aria-live="polite">
        <div className="panel-title-row">
          <div><p className="eyebrow">{liveEvidence ? "Подтверждено на ваших данных" : connected ? "Один шаг до результата" : "Первый полезный результат"}</p><h2>{liveEvidence ? "Первые реальные данные получены" : preview.title || "Первый полезный результат"}</h2></div>
          <span className={`result-badge ${liveEvidence ? "verified" : "pending"}`}>{liveEvidence ? "Данные получены" : connected ? "Готово к чтению" : "Нужно подключение"}</span>
        </div>
        <p className="muted-text">{liveEvidence ? `${evidenceProvider?.title || liveEvidence.provider_key || "Источник"}: BusinessAIOS подтвердил чтение реальных данных и теперь может опираться на факты.` : connected ? "Доступ к источнику сохранён. Реальные данные ещё не читались. Нажмите «Получить первые данные» — подтверждённый результат появится здесь." : preview.message}</p>
        <div className="check-list compact-check-list">
          {liveEvidence ? (
            <>
              <div className="check-row"><span>✓</span><strong>Подключение работает</strong></div>
              <div className="check-row"><span>✓</span><strong>Данные прочитаны в безопасном режиме</strong></div>
              {resourceCount !== undefined ? <div className="check-row"><span>✓</span><strong>Получено объектов: {resourceCount}</strong></div> : null}
            </>
          ) : connected ? (
            <>
              <div className="check-row"><span>✓</span><strong>Доступ к источнику сохранён</strong></div>
              <div className="check-row"><span>→</span><strong>Получить первые реальные данные</strong></div>
            </>
          ) : (preview.checks || []).map((item) => <div className="check-row" key={item}><span>→</span><strong>{item}</strong></div>)}
        </div>
        <div className="truth-note">{liveEvidence ? "Результат подтверждён реальным чтением данных из подключённого источника." : "До первого чтения здесь нет финансовых обещаний или выдуманных выводов. Сначала факты — потом рекомендации."}</div>
      </section>

      <BusinessIntelligencePanel
        key={data.business_id}
        enabled={Boolean(apiKey)}
        initialGoal={GOALS.find((goal) => goal.value === profile.goal)?.title || "Улучшить результаты бизнеса"}
        onLoad={loadBusinessIntelligence}
        onRunGoal={runAdvisoryGoal}
        onPrepareAction={prepareDecisionAction}
        onOpenSurface={openWorkspaceSection}
      />

      <section className="panel capabilities-panel" aria-labelledby="business-capabilities-title">
        <div className="panel-title-row">
          <div><p className="eyebrow">Возможности</p><h2 id="business-capabilities-title">Что BusinessAIOS уже умеет для вашего бизнеса</h2></div>
          <span className="privacy-badge">По фактической готовности</span>
        </div>
        <p className="muted-text">Это не рекламный список. Статус каждой возможности приходит из единого реестра BusinessAIOS и текущего состояния подключений. Если путь уже доказан, отсюда можно сразу перейти к существующей настройке.</p>
        <div className="capability-summary">
          <article><strong>{actionableCapabilities.length}</strong><span>можно открыть или подключить</span></article>
          <article><strong>{capabilityRows.filter((item) => item.userState.provider?.connected).length}</strong><span>уже подключено</span></article>
          <article><strong>{otherCapabilities.length}</strong><span>системные или готовятся</span></article>
        </div>
        {actionableCapabilities.length ? <div className="capability-grid">{actionableCapabilities.map((item) => <article className="capability-card" key={item.id}>
          <div className="capability-card-head"><div><small>{capabilitySurfaceLabel(item.surface)}</small><strong>{item.title}</strong></div><span className={`status-pill ${item.userState.className}`}>{item.userState.label}</span></div>
          <p>{capabilityPlainCopy(item, item.userState)}</p>
          <button type="button" className="ghost small" onClick={() => openCapabilityProvider(item.userState.provider.provider_key)}>{item.userState.provider.connected ? "Открыть подключение" : "Подключить"}</button>
        </article>)}</div> : <p className="empty-state">Сейчас нет возможностей с готовым пользовательским путём подключения.</p>}
        {otherCapabilities.length ? <details className="capability-roadmap"><summary><span>Остальные возможности проекта</span><strong>{otherCapabilities.length}</strong></summary><div className="capability-grid roadmap-grid">{otherCapabilities.map((item) => <article className="capability-card muted-capability" key={item.id}>
          <div className="capability-card-head"><div><small>{capabilitySurfaceLabel(item.surface)}</small><strong>{item.title}</strong></div><span className={`status-pill ${item.userState.className}`}>{item.userState.label}</span></div>
          <p>{capabilityPlainCopy(item, item.userState)}</p>
          {item.userState.provider?.customer_selectable ? <button type="button" className="ghost small" onClick={() => openCapabilityProvider(item.userState.provider.provider_key)}>Открыть настройку</button> : <small className="helper-text">BusinessAIOS не показывает кнопку действия, пока для неё нет честного пользовательского пути.</small>}
        </article>)}</div></details> : null}
      </section>

      <section className="workspace-grid">
        <article className="panel primary-panel" id="connections-panel">
          <div className="panel-title-row"><div><p className="eyebrow">Шаг к результату</p><h2>Подключите источник данных</h2></div><span className="privacy-badge">Только чтение</span></div>
          <p className="muted-text">Выберите источник и дайте доступ для чтения. Секреты используются только для подключения и не сохраняются в браузере.</p>

          {!apiKey ? <div className="recovery-box" role="alert"><p><strong>Кабинет найден, но защищённый вход сейчас не восстановлен.</strong> Обычная перезагрузка сама по себе сессию не завершает. Повторите вход; если срок безопасной сессии истёк, создайте новый кабинет.</p><button type="button" className="ghost" disabled={accessRecoveryBusy} onClick={retryProtectedAccess}>{accessRecoveryBusy ? "Восстанавливаем вход…" : "Повторить защищённый вход"}</button></div> : null}
          {workspaceLoading ? <div className="loading-box">Восстанавливаем кабинет и проверяем подключения…</div> : null}
          {workspaceError ? <div className="error-box inline-error" role="alert">{workspaceError}</div> : null}

          <div className="connection-list">
            {providers.length ? providers.map((item) => (
              <button type="button" className={`connection-row ${activeProvider?.provider_key === item.provider_key ? "selected" : ""}`} aria-current={activeProvider?.provider_key === item.provider_key ? "true" : undefined} onClick={() => { setActiveKey(item.provider_key); setExternalRef(""); setSecrets({}); setEditingAccessKey(""); }} key={item.provider_key} disabled={!item.customer_selectable}>
                <div className="provider-logo">{providerInitial(item.title)}</div>
                <div className="connection-copy"><strong>{item.title}</strong><span>{liveEvidenceByProvider.has(item.provider_key) ? "Данные получены" : item.connected ? "Доступ сохранён · данные ещё не получены" : item.customer_selectable ? "Можно подключить" : "Пока не доступно"}</span></div>
                <span className={`dot ${item.connected ? "green" : item.customer_selectable ? "orange" : "gray"}`} />
              </button>
            )) : <p className="empty-state">Для выбранных источников пока нет готового подключения.</p>}
          </div>

          {activeProvider && apiKey ? (
            <div className="connection-flow">
              <div className="connection-steps" aria-label="Этапы подключения">
                <span className="done">1. Источник выбран</span>
                <span className={activeProvider.connected ? "done" : "active"}>2. Доступ</span>
                <span className={activeLiveEvidence ? "done" : activeProvider.connected ? "active" : ""}>3. Первые данные</span>
              </div>
              <div className="step-content workspace-step-content">
                <div className="section-heading"><h2>{activeProvider.title}</h2><p>{activeLiveEvidence ? "Первые данные из этого источника подтверждены. При необходимости обновите их или проверьте доступ." : activeProvider.connected ? "Доступ сохранён. Получите первые данные — это главное действие сейчас." : "Нужен только доступ для чтения. Изменения во внешней системе остаются выключены."}</p></div>
                <div className="provider-truth-card"><strong>Что реально доступно</strong><span>{providerTruthCopy(activeProvider)}</span>{identityCopy.help ? <small>{identityCopy.help}</small> : null}</div>
                {!activeProvider.connected || editingAccessKey === activeProvider.provider_key ? (
                  <div className="form-grid">
                    <label className="full">{identityCopy.label}<input value={externalRef} onChange={(event) => setExternalRef(event.target.value)} placeholder={identityCopy.placeholder} /><small className="input-help">Это идентификатор именно вашего кабинета или проекта — не внутренний ID BusinessAIOS.</small></label>
                    {webhookUrl ? <label className="full">Webhook URL<input className="readonly-value" type="text" readOnly value={webhookUrl} onFocus={(event) => event.target.select()} /><small className="input-help">Скопируйте этот адрес в настройки входящих событий провайдера. Адрес не содержит секретов.</small></label> : null}
                    {(activeProvider.secret_fields || []).map((field) => (
                      <label className={field.multiline ? "full" : ""} key={field.secret_name}><span className="field-label-row"><span>{credentialLabel(activeProvider, field)}</span>{!field.required ? <small>Необязательно</small> : null}</span>{field.multiline ? <textarea value={secrets[field.secret_name] || ""} onChange={(event) => setSecrets((previous) => ({ ...previous, [field.secret_name]: event.target.value }))} placeholder={field.placeholder || ""} /> : <input type={credentialInputType(field)} autoComplete="off" value={secrets[field.secret_name] || ""} onChange={(event) => setSecrets((previous) => ({ ...previous, [field.secret_name]: event.target.value }))} placeholder={field.placeholder || ""} />}{credentialInputType(field) === "text" ? <small className="input-help">Обычная настройка, не пароль. Значение передаётся только на защищённый сервер BusinessAIOS.</small> : null}</label>
                    ))}
                    <button type="button" className="primary" disabled={Boolean(workspaceBusy)} onClick={activateProvider}>{workspaceBusy === "activate" || workspaceBusy === "update_access" ? "Сохраняем доступ…" : activeProvider.connected ? "Обновить доступ" : "Подключить для чтения"}</button>
                    {activeProvider.connected ? <button type="button" className="ghost" disabled={Boolean(workspaceBusy)} onClick={() => { setEditingAccessKey(""); setExternalRef(""); setSecrets({}); }}>Отмена</button> : null}
                  </div>
                ) : (
                  <div className="navigation-row workspace-actions">
                    <button type="button" className="ghost" disabled={Boolean(workspaceBusy)} onClick={probeProvider}>{workspaceBusy === "probe" ? "Проверяем…" : "Проверить доступ"}</button>
                    <button type="button" className="primary" disabled={Boolean(workspaceBusy)} onClick={syncProvider}>{syncActionLabel}</button>
                    <button type="button" className="ghost" disabled={Boolean(workspaceBusy)} onClick={() => { setEditingAccessKey(activeProvider.provider_key); setExternalRef(activeProvider.external_ref || ""); setSecrets({}); }}>Изменить доступ</button>
                  </div>
                )}
                <small className="helper-text">Чтение доступно сразу. Перед внешним действием BusinessAIOS сначала проверит его и попросит ваше подтверждение. Прямой отправки из браузера нет.</small>
                {lastAction?.providerKey === activeProvider.provider_key ? <details className="technical-inline"><summary>Технические детали последней операции</summary><pre>{JSON.stringify(lastAction.result, null, 2)}</pre></details> : null}
              </div>
            </div>
          ) : null}
        </article>

        <article className="panel next-step-panel">
          <p className="eyebrow">Что дальше</p>
          <h2>{liveEvidence ? "Переходите от настройки к решениям" : connected ? "Получите факты одним действием" : "Сначала одно подключение"}</h2>
          <p className="muted-text">{liveEvidence ? "Источник уже дал реальные данные. Теперь сценарный расчёт ниже можно сопоставлять с фактическими показателями бизнеса." : connected ? "Доступ уже есть. Не заполняйте ничего лишнего — получите первые данные и посмотрите подтверждённый результат выше." : "Не нужно настраивать всю систему. Достаточно подключить один выбранный источник и получить первый результат."}</p>
          <div className="check-list">
            <div className="check-row"><span>{connected ? "✓" : "1"}</span><strong>Подключить один источник</strong></div>
            <div className="check-row"><span>{liveEvidence ? "✓" : "2"}</span><strong>Получить первые реальные данные</strong></div>
            <div className="check-row"><span>3</span><strong>Сравнить факты со сценарием и выбрать действие</strong></div>
          </div>
        </article>
      </section>

      <section className="panel sales-panel" aria-labelledby="business-sales-title">
        <div className="panel-title-row">
          <div><p className="eyebrow">Центр продаж</p><h2 id="business-sales-title">Продажи</h2></div>
          <span className="privacy-badge">HubSpot · только чтение</span>
        </div>
        <p className="muted-text">Здесь BusinessAIOS показывает только подтверждённые чтением CRM-факты. Отдельную CRM-копию не создаём и неизвестные показатели не заменяем нулями.</p>
        {salesError ? <div className="error-box inline-error" role="alert">{salesError}</div> : null}
        {!hubspotProvider ? (
          <div className="recovery-box"><p>HubSpot есть в архитектуре проекта, но текущий пользовательский реестр ещё не открыл его для безопасного подключения. Поэтому кнопки с фиктивными данными здесь нет.</p></div>
        ) : !hubspotProvider.connected ? (
          <div className="sales-empty-state">
            <div><strong>Подключите CRM — и здесь появятся факты по контактам и сделкам.</strong><span>Sales Center использует подключение только для чтения. Права самого Private App Token задаются в HubSpot.</span></div>
            <button type="button" className="primary" onClick={() => openCapabilityProvider("hubspot")}>Подключить HubSpot</button>
          </div>
        ) : (
          <>
            <div className="sales-metrics">
              <article><small>Контакты</small><strong>{hubspotContactCount ?? "—"}</strong><span>{hubspotContactEvidence ? "объектов в последнем подтверждённом чтении" : "подтверждённых данных пока нет"}</span><em>{hubspotContactEvidence ? evidenceHasNextPage(hubspotContactEvidence) ? "Есть следующая страница — это не общий итог." : `Подтверждено ${evidenceTimeLabel(hubspotContactEvidence)}` : "Нажмите «Получить данные по продажам»."}</em></article>
              <article><small>Сделки</small><strong>{hubspotDealCount ?? "—"}</strong><span>{hubspotDealEvidence ? "объектов в последнем подтверждённом чтении" : "подтверждённых данных пока нет"}</span><em>{hubspotDealEvidence ? evidenceHasNextPage(hubspotDealEvidence) ? "Есть следующая страница — это не общий итог." : `Подтверждено ${evidenceTimeLabel(hubspotDealEvidence)}` : "Нажмите «Получить данные по продажам»."}</em></article>
              <article><small>Свежесть</small><strong className="sales-time-value">{hubspotLastEvidence ? evidenceTimeLabel(hubspotLastEvidence) : "—"}</strong><span>последнее подтверждённое чтение CRM</span><em>Дата берётся из защищённой истории чтений BusinessAIOS.</em></article>
            </div>
            <div className="sales-truth-grid">
              <article className="sales-truth-card"><strong>Что уже подтверждено</strong><p>{hubspotContactEvidence && hubspotDealEvidence ? "BusinessAIOS уже получил реальные ответы HubSpot по контактам и сделкам. Эти значения можно использовать как факты последнего чтения." : "HubSpot подключён, но для Sales Center ещё нужны подтверждённые чтения и контактов, и сделок."}</p></article>
              <article className="sales-truth-card caution"><strong>Что пока не считаем</strong><p>«Выиграно / проиграно / зависло», сумму воронки и конверсию по стадиям пока не показываем: BusinessAIOS ещё не доказал единые правила сопоставления стадий HubSpot. Нули вместо неизвестных значений не подставляются.</p></article>
            </div>
            <div className="navigation-row sales-actions">
              <button type="button" className="primary" disabled={salesBusy || Boolean(workspaceBusy) || !hubspotCanRefreshSales} onClick={refreshSalesCenter}>{salesBusy ? "Обновляем CRM…" : hubspotLastEvidence ? "Обновить данные продаж" : "Получить данные по продажам"}</button>
              <button type="button" className="ghost" onClick={() => document.getElementById("business-customers-title")?.scrollIntoView({ behavior: "smooth", block: "start" })}>Открыть клиентов</button>
            </div>
            {!hubspotCanRefreshSales ? <small className="sales-note">HubSpot подключён, но текущий контур подключения не подтверждает обе безопасные операции чтения. Sales Center остаётся в режиме просмотра без выдуманных результатов.</small> : <small className="sales-note">Кнопка выполняет только чтение HubSpot. Создание задач, изменение контактов и другие CRM-записи отсюда не запускаются.</small>}
            <div className="sales-activity">
              <div className="sales-activity-head"><h3>Последние чтения CRM</h3><small>{hubspotLastEvidence ? `Последнее подтверждение: ${evidenceTimeLabel(hubspotLastEvidence)}` : "Подтверждённых чтений пока нет."}</small></div>
              {hubspotRecentReads.length ? hubspotRecentReads.map((row, index) => {
                const successful = isSuccessfulLiveEvidence(row);
                const count = evidenceResourceCount(row);
                return <article className={`sales-activity-row ${successful ? "" : "warning"}`} key={row.history_id || `${row.operation}-${row.recorded_at_utc}-${index}`}><div><strong>{row.operation === "deal_sync" ? "Сделки" : "Контакты"}</strong><span>{successful ? count === null ? "Чтение подтверждено" : `Получено объектов: ${count}` : "Чтение не подтверждено"}</span></div><small>{evidenceTimeLabel(row)}{successful && evidenceHasNextPage(row) ? " · есть следующая страница" : ""}</small></article>;
              }) : <p className="empty-state">История чтения HubSpot появится после первого безопасного запроса.</p>}
            </div>
          </>
        )}
      </section>

      <section className="panel customers-panel" aria-labelledby="business-customers-title">
        <div className="panel-title-row">
          <div><p className="eyebrow">Клиенты</p><h2 id="business-customers-title">Клиенты и история контактов</h2></div>
          <span className="privacy-badge">Из единого EventStore</span>
        </div>
        <p className="muted-text">Клиенты появляются здесь из подтверждённых входящих событий подключённых каналов. Отдельной CRM-копии BusinessAIOS не создаёт.</p>
        {customerError ? <div className="error-box inline-error" role="alert">{customerError}</div> : null}
        {customerBusy && !customers.length ? <div className="loading-box">Загружаем клиентов…</div> : null}
        {customers.length ? (
          <div className="customers-layout">
            <div className="customer-list">
              {customers.map((customer) => <button type="button" className={`customer-row ${selectedCustomer?.customer_id === customer.customer_id ? "selected" : ""}`} aria-current={selectedCustomer?.customer_id === customer.customer_id ? "true" : undefined} onClick={() => setSelectedCustomerId(customer.customer_id)} key={customer.customer_id}>
                <strong>{customer.display_name || customer.identities?.[0]?.display_name || customer.identities?.[0]?.username || "Клиент"}</strong>
                <span>{(customer.identities || []).map((identity) => identity.channel).join(" · ") || "Канал не указан"}</span>
              </button>)}
            </div>
            <div className="customer-detail">
              {selectedCustomer ? <>
                <h3>{selectedCustomer.display_name || selectedCustomer.identities?.[0]?.display_name || "Клиент"}</h3>
                <div className="customer-identities">
                  {(selectedCustomer.identities || []).map((identity) => <article className="customer-identity" key={identity.identity_id}>
                    <div><strong>{identity.channel}</strong><span>{identity.display_name || identity.username || identity.external_subject}</span></div>
                    {readyIdentityProvider(identity) ? <button type="button" className="ghost small" onClick={() => prepareForCustomer(identity)}>Написать</button> : <small>Отправка по каналу пока не готова</small>}
                  </article>)}
                </div>
                <h3>История</h3>
                <div className="timeline-list">
                  {customerTimeline.length ? customerTimeline.slice().reverse().map((entry) => <article className="timeline-row" key={entry.source_id}>
                    <strong>{entry.title || entry.kind}</strong>
                    <span>{entry.detail || entry.source_type}</span>
                    <small>{entry.occurred_at_ms ? new Date(entry.occurred_at_ms).toLocaleString("ru-RU") : ""}{entry.amount_minor !== null && entry.amount_minor !== undefined ? ` · ${(Number(entry.amount_minor) / 100).toLocaleString("ru-RU")} ${entry.currency || ""}` : ""}</small>
                  </article>) : <p className="empty-state">Для клиента пока нет дополнительных событий.</p>}
                </div>
              </> : null}
            </div>
          </div>
        ) : <p className="empty-state">Клиенты появятся здесь после входящих событий из подключённых каналов.</p>}
      </section>

      <section className="panel operations-panel" aria-labelledby="business-operations-title">
        <div className="panel-title-row">
          <div><p className="eyebrow">Контроль внешних действий</p><h2 id="business-operations-title">Центр действий</h2></div>
          <span className="privacy-badge">С подтверждением владельца</span>
        </div>
        <p className="muted-text">Здесь видно, что требует вашего решения и какие каналы уже готовы к безопасному действию. BusinessAIOS сначала сохраняет и показывает действие; внешнее выполнение возможно только после вашего подтверждения.</p>
        <div className="action-summary" aria-label="Сводка центра действий">
          <article><small>Ждут решения</small><strong>{pendingApprovals.length}</strong><span>{pendingApprovals.length ? "проверьте получателя и содержание" : "очередь подтверждений пуста"}</span></article>
          <article><small>Нужно проверить выполнение</small><strong>{resumeCandidates.length}</strong><span>{resumeCandidates.length ? "approval уже подтверждён — доступен безопасный resume" : "незавершённых resume нет"}</span></article>
          <article><small>Готовые каналы</small><strong>{readyOperationProviders.length}</strong><span>{readyOperationProviders.length ? "можно подготовить новое действие" : "сначала завершите подключение канала"}</span></article>
          <article><small>Последнее действие</small><strong>{operationDecisionProvenance ? "Связано с DecisionCore" : operationResult ? "Есть результат" : "—"}</strong><span>{operationDecisionProvenance ? `run ${operationDecisionProvenance.run_id}` : operationResult ? "технический результат доступен ниже" : "в этой сессии действий ещё не было"}</span></article>
        </div>
        <div className={`action-attention ${operationQueueStale ? "stale" : pendingApprovals.length ? "needs-review" : readyOperationProviders.length ? "ready" : "setup"}`} role="status">
          <strong>{operationQueueStale ? "Очередь требует обновления" : pendingApprovals.length ? `Вашего решения ждут: ${pendingApprovals.length}` : readyOperationProviders.length ? "Сейчас ничего не ждёт подтверждения" : "Сначала нужен готовый канал"}</strong>
          <span>{operationQueueStale ? "Последний запрос мог быть обработан, поэтому BusinessAIOS не разрешает повторять подготовку вслепую. Сначала перечитайте очередь." : pendingApprovals.length ? "Подтверждайте только после проверки получателя, темы и текста. После подтверждения BusinessAIOS возобновит именно сохранённое действие." : readyOperationProviders.length ? "Можно подготовить новое сообщение. Нажатие «Подготовить к отправке» ничего внешнему получателю не отправляет." : "Кнопка подготовки появится только когда BusinessAIOS видит подключение и готовый путь внешнего действия."}</span>
          {operationQueueStale ? <div className="navigation-row"><button type="button" className="ghost small" disabled={Boolean(operationBusy)} onClick={refreshActionQueue}>{operationBusy === "refresh_queue" ? "Обновляем…" : "Обновить очередь"}</button>{operationRecovery?.kind === "draft" ? <button type="button" className="ghost small" disabled={Boolean(operationBusy)} onClick={() => prepareMessage({ allowStaleRetry: true })}>{operationBusy === "message_send" ? "Повторяем…" : "Повторить тот же запрос"}</button> : null}</div> : null}
        </div>
        {operationError ? <div className="error-box inline-error" role="alert">{operationError}</div> : null}
        <div className="provider-readiness" aria-label="Готовность каналов к действиям">
          {operationProviders.length ? operationProviders.map((item) => <span className={`status-pill ${item.can_request_write ? "ready" : "preparing"}`} key={item.provider_key}>{item.title}: {item.can_request_write ? "готов к подготовке" : !item.connected ? "нужно подключить" : item.status === "live_credentials_missing" ? "нужны данные для отправки" : "действие пока недоступно"}</span>) : <span className="muted-text">Каналов с доказанным путём внешнего действия пока нет.</span>}
        </div>
        {terminalResumeCandidates.length ? <div className="recovery-box" aria-label="Завершённые неуспешные действия">
          <strong>Выполнение завершилось без доставки</strong>
          <p>Для этих approvals provider-history доказал окончательный отказ. Повторный resume не предлагается: исправьте подключение или условия и подготовьте новое действие.</p>
          <div className="approval-list">{terminalResumeCandidates.map((item) => <article className="approval-card" key={`terminal:${item.approval_id}`}><div className="approval-card-head"><div><strong>{item.action_name || "Подтверждённое действие"}</strong><small>Approval: {item.approval_id}</small></div><span>Окончательный отказ</span></div></article>)}</div>
        </div> : null}
        {resumeCandidates.length ? <div className="recovery-box" aria-label="Восстановление подтверждённых действий">
          <strong>Подтверждено — выполнение нужно проверить</strong>
          <p>Эти approvals уже подтверждены владельцем. Не подтверждайте их повторно: используйте сохранённый resume. Повтор безопасно проходит через тот же серверный dedupe-контур.</p>
          <div className="approval-list">{resumeCandidates.map((item) => <article className="approval-card" key={`resume:${item.approval_id}`}>
            <div className="approval-card-head"><div><strong>{item.action_name || "Подтверждённое действие"}</strong><small>Approval: {item.approval_id}</small></div><span>Выполнение не закрыто в UI</span></div>
            <button type="button" className="primary" disabled={Boolean(operationBusy)} onClick={() => resumeApprovedOperation(item.approval_id)}>{operationBusy === `resume:${item.approval_id}` ? "Проверяем…" : "Проверить / продолжить выполнение"}</button>
          </article>)}</div>
        </div> : null}
        <div className="operations-layout">
          <div className="approval-list">
            <div className="action-column-heading"><div><span className="step-kicker">1 · Проверить</span><h3>Ждут вашего решения</h3></div><strong className="queue-count">{pendingApprovals.length}</strong></div>
            {pendingApprovals.length ? pendingApprovals.map((approval) => {
              const previewRow = approvalMessagePreview(approval);
              const provider = operationProviders.find((item) => item.provider_key === previewRow.providerKey);
              return <article className="approval-card" key={approval.approval_id}>
                <div className="approval-card-head"><div><strong>{provider?.title || previewRow.providerKey || "Сообщение"}</strong><small>Получатель: {previewRow.recipient || "—"}</small></div><span>Ждёт решения</span></div>
                {previewRow.subject ? <p><strong>{previewRow.subject}</strong></p> : null}
                <p>{previewRow.text || "Текст действия сохранён и ждёт вашего решения."}</p>
                <small className="helper-text">После подтверждения получатель и содержание берутся из этого сохранённого действия.</small>
                <div className="navigation-row"><button type="button" className="ghost" disabled={Boolean(operationBusy) || operationQueueStale} onClick={() => decideApproval(approval.approval_id, false)}>Отклонить</button><button type="button" className="primary" disabled={Boolean(operationBusy) || operationQueueStale} onClick={() => decideApproval(approval.approval_id, true)}>{operationBusy === `approval:${approval.approval_id}` ? "Выполняем…" : "Подтвердить и выполнить"}</button></div>
              </article>;
            }) : <p className="empty-state">Очередь пуста. Здесь появится действие после нажатия «Подготовить к отправке».</p>}
          </div>
          <div className="operations-form">
            <div className="action-column-heading"><div><span className="step-kicker">2 · Подготовить</span><h3>Новое сообщение</h3></div></div>
            {operationOrigin ? <div className="decision-draft-origin" role="status"><strong>Черновик из DecisionCore</strong><span>Источник проверен по серверному ledger: run {operationOrigin.run_id}. Это только основа черновика — текст, канал и получателя нужно проверить перед созданием approval.</span>{!operationRecipient ? <button type="button" className="ghost small" onClick={() => document.getElementById("business-customers-title")?.scrollIntoView({ behavior: "smooth", block: "start" })}>Выбрать клиента</button> : null}</div> : null}
            {readyOperationProviders.length ? (
              <>
                <label>Канал<select aria-label="Канал для действия" disabled={operationQueueStale} value={activeOperationProvider?.provider_key || ""} onChange={(event) => { setOperationProviderKey(event.target.value); setOperationRecipient(""); setOperationSubject(""); setOperationDraftKey(crypto.randomUUID()); }}>{readyOperationProviders.map((item) => <option value={item.provider_key} key={item.provider_key}>{item.title}</option>)}</select></label>
                <label>{operationRecipientCopy.label}<input disabled={operationQueueStale} value={operationRecipient} onChange={(event) => { setOperationRecipient(event.target.value); setOperationDraftKey(crypto.randomUUID()); }} placeholder={operationRecipientCopy.placeholder} /></label>
                {activeOperationProvider?.provider_key === "email_connector" ? <label>Тема<input disabled={operationQueueStale} value={operationSubject} onChange={(event) => { setOperationSubject(event.target.value); setOperationDraftKey(crypto.randomUUID()); }} placeholder="Тема письма" /></label> : null}
                <label>Сообщение<textarea disabled={operationQueueStale} value={operationText} onChange={(event) => { setOperationText(event.target.value); setOperationDraftKey(crypto.randomUUID()); }} placeholder="Что BusinessAIOS должен подготовить для отправки" /></label>
                <button type="button" className="primary" disabled={Boolean(operationBusy) || operationQueueStale} onClick={prepareMessage}>{operationBusy === "message_send" ? "Готовим…" : "Подготовить к отправке"}</button>
                <small className="helper-text">Это только создаёт действие для проверки. Нажатие этой кнопки само по себе ничего внешнему получателю не отправляет.</small>
              </>
            ) : <div className="recovery-box"><p>Сначала завершите подключение канала. Форма станет доступна только когда BusinessAIOS видит готовый путь внешнего действия.</p></div>}
          </div>
        </div>
        {operationDecisionProvenance ? <div className="decision-result-evidence" role="status"><strong>Результат связан с решением DecisionCore</strong><span>Сервер подтвердил происхождение: run {operationDecisionProvenance.run_id}, decision {operationDecisionProvenance.decision_id}, action {operationDecisionProvenance.action_id}.</span><span>{operationProviderAccepted && operationProviderResourceId ? `Провайдер принял действие и вернул receipt ${operationProviderResourceId}. Это подтверждает приём провайдером, но не объявляется доказанной доставкой получателю.` : "Внешний результат пока не имеет подтверждённого provider receipt; используйте recovery и историю выполнения."}</span></div> : null}
        {operationResult ? <details className="technical-inline"><summary>Технические детали последнего действия</summary><pre>{JSON.stringify(operationResult, null, 2)}</pre></details> : null}
      </section>

      <AcquisitionPlanner enabled={Boolean(apiKey)} onEvaluate={(payload) => postJson(acquisitionUrl, payload, authHeaders)} />

      <section className="panel business-card">
        <div><p className="eyebrow">Профиль</p><h2>{profile.name || "Бизнес"}</h2></div>
        <div className="business-meta">{profile.industry ? <span>{profile.industry}</span> : null}{profile.city ? <span>{profile.city}</span> : null}{profile.website ? <a href={profile.website} target="_blank" rel="noreferrer">{profile.website}</a> : null}</div>
      </section>

      <details className="diagnostics"><summary>Техническая информация</summary><pre>{JSON.stringify({ intake_id: data.intake_id, tenant_id: data.tenant_id, business_id: data.business_id, status: data.onboarding_status, owner_session_expires_at: ownerSession.expires_at || null, live_sync_evidence: liveEvidence || null }, null, 2)}</pre></details>
    </main>
  );
}

function BusinessChooser({ businesses, onOpen, onAdd }) {
  return (
    <main className="onboarding-shell account-home">
      <header className="topbar onboarding-topbar"><div className="brand"><span className="brand-mark">B</span><span className="brand-name">BusinessAIOS</span></div><button type="button" className="primary small add-business-button" aria-label="Добавить бизнес" onClick={onAdd}><span className="add-business-full">Добавить бизнес</span><span className="add-business-short">Добавить</span></button></header>
      <section className="account-businesses panel">
        <div className="section-heading"><p className="eyebrow">Ваш аккаунт</p><h1>Мои бизнесы</h1><p>Выберите бизнес. Данные, интеграции и действия каждого бизнеса остаются в его отдельном защищённом контуре.</p></div>
        <div className="business-choice-grid">
          {businesses.map((item) => <button type="button" className="business-choice-card" aria-label={`Открыть бизнес ${item.name || "Бизнес"}`} onClick={() => onOpen(item.intake_id)} key={item.intake_id}><strong>{item.name || "Бизнес"}</strong><span>{[item.industry, item.city].filter(Boolean).join(" · ") || "Открыть кабинет"}</span><small>Открыть →</small></button>)}
        </div>
      </section>
    </main>
  );
}

export function App() {
  const [apiBase] = useState(DEFAULT_API);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [marketLoading, setMarketLoading] = useState(true);
  const [error, setError] = useState("");
  const [marketError, setMarketError] = useState("");
  const [marketplace, setMarketplace] = useState([]);
  const [selectedProviders, setSelectedProviders] = useState([]);
  const availableMarketplace = useMemo(() => marketplace.filter((item) => item.selectable), [marketplace]);
  const roadmapMarketplace = useMemo(() => marketplace.filter((item) => !item.selectable), [marketplace]);
  const [result, setResult] = useState(null);
  const [ownerBusinesses, setOwnerBusinesses] = useState([]);
  const [ownerAccountChecked, setOwnerAccountChecked] = useState(false);
  const [creatingNewBusiness, setCreatingNewBusiness] = useState(false);
  const [form, setForm] = useState(() => ({ ...INITIAL_FORM }));

  const endpoints = useMemo(() => {
    const base = apiBase.replace(/\/$/, "");
    return { integrations: `${base}/public-site/integrations`, ctaStart: `${base}/public-site/cta/start`, ctaStatus: (id) => `${base}/public-site/cta/${encodeURIComponent(id)}`, ownerBusinesses: `${base}/public-site/owner/businesses` };
  }, [apiBase]);

  const openSavedWorkspace = useCallback(async (intakeId) => {
    const payload = await getJson(endpoints.ctaStatus(intakeId));
    if (!payload?.ok) throw new Error("workspace_not_found");
    setResult(payload);
    setOwnerBusinesses(Array.isArray(payload.owner_businesses) ? payload.owner_businesses : []);
    setOwnerAccountChecked(true);
    setCreatingNewBusiness(false);
    setError("");
    return payload;
  }, [endpoints]);

  const restoreWorkspaceAccess = useCallback(async (intakeId) => {
    const payload = await openSavedWorkspace(intakeId);
    return Boolean(payload?.owner_session?.api_key);
  }, [openSavedWorkspace]);

  const loadOwnerBusinesses = useCallback(async () => {
    try {
      const payload = await getJson(endpoints.ownerBusinesses);
      const rows = Array.isArray(payload.businesses) ? payload.businesses : [];
      setOwnerBusinesses(rows);
      return rows;
    } catch {
      setOwnerBusinesses([]);
      return [];
    } finally {
      setOwnerAccountChecked(true);
    }
  }, [endpoints.ownerBusinesses]);

  const switchBusiness = useCallback(async (intakeId) => {
    if (!intakeId) return;
    setLoading(true);
    setError("");
    try {
      await openSavedWorkspace(intakeId);
      window.history.replaceState(null, "", `?intake_id=${encodeURIComponent(intakeId)}`);
    } catch {
      setError("Не удалось открыть выбранный бизнес. Проверьте соединение и повторите попытку.");
    } finally {
      setLoading(false);
    }
  }, [openSavedWorkspace]);

  const loadMarketplace = useCallback(async () => {
    setMarketLoading(true);
    setMarketError("");
    try {
      const payload = await getJson(endpoints.integrations);
      setMarketplace(Array.isArray(payload.items) ? payload.items : []);
    } catch {
      setMarketplace([]);
      setMarketError("Не удалось загрузить список интеграций. Проверьте соединение и повторите попытку.");
    } finally {
      setMarketLoading(false);
    }
  }, [endpoints.integrations]);

  useEffect(() => {
    void loadMarketplace();
  }, [loadMarketplace]);

  useEffect(() => {
    const intakeId = initialIntakeId();
    if (!intakeId) {
      void loadOwnerBusinesses();
      return;
    }
    let cancelled = false;
    setLoading(true);
    openSavedWorkspace(intakeId)
      .catch(() => { if (!cancelled) setError("Не удалось открыть сохранённый кабинет бизнеса."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [loadOwnerBusinesses, openSavedWorkspace]);

  const savedIntakeId = initialIntakeId();
  const retrySavedWorkspace = async () => {
    if (!savedIntakeId) return;
    setLoading(true);
    setError("");
    try {
      await openSavedWorkspace(savedIntakeId);
    } catch {
      setError("Не удалось открыть сохранённый кабинет бизнеса. Проверьте соединение и повторите попытку.");
    } finally {
      setLoading(false);
    }
  };

  const emailValid = isValidEmail(form.email);
  const updateForm = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));
  const toggleProvider = (item) => {
    if (!item.selectable) return;
    setSelectedProviders((prev) => prev.includes(item.provider_key) ? prev.filter((key) => key !== item.provider_key) : [...prev, item.provider_key]);
  };
  const canContinue = () => {
    if (step === 0) return Boolean(form.business_name.trim() && emailValid);
    if (step === 1) return Boolean(form.goal);
    if (step === 2) return selectedProviders.length > 0;
    return Boolean(form.autonomy_mode);
  };

  const finishOnboarding = async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await postJson(endpoints.ctaStart, { ...form, selected_providers: selectedProviders, intent: form.goal, source: "businessaios_product_onboarding", requested_surface: "business_workspace" });
      setResult(payload);
      setOwnerBusinesses(Array.isArray(payload.owner_businesses) ? payload.owner_businesses : []);
      setOwnerAccountChecked(true);
      setCreatingNewBusiness(false);
      if (payload.intake_id) window.history.replaceState(null, "", `?intake_id=${encodeURIComponent(payload.intake_id)}`);
    } catch {
      setError("Не удалось создать кабинет. Проверьте соединение и повторите попытку.");
    } finally {
      setLoading(false);
    }
  };

  const restart = () => {
    window.history.replaceState(null, "", window.location.pathname);
    setCreatingNewBusiness(true);
    setResult(null);
    setStep(0);
    setSelectedProviders([]);
    setForm({ ...INITIAL_FORM });
    setError("");
  };

  if (result) return <Workspace key={`${result.business_id}:${result.owner_session?.expires_at || result.intake_id || ""}`} data={result} apiBase={apiBase} businesses={ownerBusinesses} onRestart={restart} onRetryAccess={restoreWorkspaceAccess} onSwitchBusiness={switchBusiness} />;
  if (!creatingNewBusiness && !initialIntakeId() && !ownerAccountChecked) return <main className="onboarding-shell"><div className="account-loading" role="status">Открываем ваши бизнесы…</div></main>;
  if (!creatingNewBusiness && ownerBusinesses.length) return <BusinessChooser businesses={ownerBusinesses} onOpen={switchBusiness} onAdd={restart} />;

  return (
    <main className="onboarding-shell">
      <header className="topbar onboarding-topbar"><div className="brand"><span className="brand-mark">B</span><span className="brand-name">BusinessAIOS</span></div><span className="topbar-note">Настройка бизнеса</span></header>
      <section className="onboarding-layout">
        <aside className="intro-column">
          <p className="eyebrow">Управление бизнесом с ИИ</p><h1>Подключите бизнес.<br />Остальное система разберёт сама.</h1>
          <p className="lead">Сначала только чтение и анализ. Никаких расходов, сообщений клиентам или публикаций без вашего разрешения.</p>
          <div className="trust-list">
            <div><span>✓</span><p><strong>Безопасный старт</strong><small>Ничего не отправляем и не меняем без вашего разрешения.</small></p></div>
            <div><span>✓</span><p><strong>Честные статусы</strong><small>Доступные сейчас отделены от интеграций, которые ещё готовятся.</small></p></div>
            <div><span>✓</span><p><strong>Первый результат на ваших данных</strong><small>Без выдуманных финансовых обещаний.</small></p></div>
          </div>
        </aside>

        <section className="onboarding-card">
          <div className="stepper">{STEP_LABELS.map((label, index) => <div className={`step ${index === step ? "active" : ""} ${index < step ? "done" : ""}`} aria-current={index === step ? "step" : undefined} key={label}><span>{index < step ? "✓" : index + 1}</span><small>{label}</small></div>)}</div>

          {step === 0 ? <div className="step-content"><div className="section-heading"><p className="eyebrow">Шаг 1</p><h2>Расскажите о бизнесе</h2><p>Этого достаточно, чтобы создать отдельный защищённый кабинет.</p></div><div className="form-grid"><label className="full">Название бизнеса<input value={form.business_name} onChange={updateForm("business_name")} placeholder="Например, Студия Линия" autoFocus /></label><label>Email владельца<input value={form.email} onChange={updateForm("email")} placeholder="you@company.ru" type="email" aria-invalid={Boolean(form.email.trim()) && !emailValid} aria-describedby={form.email.trim() && !emailValid ? "owner-email-error" : undefined} />{form.email.trim() && !emailValid ? <small className="field-error" id="owner-email-error">Введите email в формате name@company.ru</small> : null}</label><label>Сайт или страница<input value={form.website} onChange={updateForm("website")} placeholder="https://..." /></label><label>Сфера<input value={form.industry} onChange={updateForm("industry")} placeholder="Услуги, магазин, образование..." /></label><label>Город<input value={form.city} onChange={updateForm("city")} placeholder="Москва" /></label><label className="full">Модель бизнеса<select value={form.business_model} onChange={updateForm("business_model")}><option value="services">Услуги</option><option value="commerce">Товары / интернет-магазин</option><option value="marketplace">Маркетплейсы</option><option value="b2b">B2B</option><option value="mixed">Смешанная</option></select></label></div></div> : null}

          {step === 1 ? <div className="step-content"><div className="section-heading"><p className="eyebrow">Шаг 2</p><h2>Что важнее прямо сейчас?</h2><p>BusinessAIOS начнёт анализ с выбранной бизнес-задачи.</p></div><div className="choice-grid">{GOALS.map((goal) => <button type="button" className={`choice-card ${form.goal === goal.value ? "selected" : ""}`} aria-pressed={form.goal === goal.value} onClick={() => setForm((prev) => ({ ...prev, goal: goal.value }))} key={goal.value}><span className="radio-dot" /><strong>{goal.title}</strong><small>{goal.text}</small></button>)}</div></div> : null}

          {step === 2 ? <div className="step-content integrations-step"><div className="section-heading"><p className="eyebrow">Шаг 3</p><h2>Где уже живут данные бизнеса?</h2><p>Выберите хотя бы один источник. Подключение начнётся в режиме только чтения.</p></div>{marketLoading ? <div className="loading-box">Загружаем доступные интеграции…</div> : null}{marketError && !marketLoading ? <div className="recovery-box" role="alert"><p>{marketError}</p><button type="button" className="ghost" onClick={loadMarketplace}>Повторить загрузку</button></div> : null}{!marketLoading && !marketError ? <><div className="integration-section-head"><strong>Можно подключить сейчас</strong><span>{availableMarketplace.length}</span></div>{availableMarketplace.length ? <div className="integration-grid">{availableMarketplace.map((item) => <IntegrationCard item={item} selected={selectedProviders.includes(item.provider_key)} onToggle={toggleProvider} key={item.provider_key} />)}</div> : <p className="empty-state">Сейчас нет источников, готовых к подключению. Ниже можно посмотреть, что уже готовится.</p>}<p className="selection-count" aria-live="polite">Выбрано: <strong>{selectedProviders.length}</strong></p>{roadmapMarketplace.length ? <details className="roadmap-integrations"><summary><span>Что ещё готовится</span><strong>{roadmapMarketplace.length}</strong></summary><p>Эти интеграции уже есть в каталоге, но пока не доступны для подключения. Статус каждой берём напрямую из BusinessAIOS.</p><div className="integration-grid roadmap-grid">{roadmapMarketplace.map((item) => <IntegrationCard item={item} selected={false} onToggle={toggleProvider} key={item.provider_key} />)}</div></details> : null}</> : null}</div> : null}

          {step === 3 ? <div className="step-content"><div className="section-heading"><p className="eyebrow">Шаг 4</p><h2>Сколько свободы дать системе?</h2><p>На старте система всё равно ничего не отправит и не изменит без проверки.</p></div><div className="autonomy-grid">{AUTONOMY.map((mode) => <button type="button" className={`autonomy-card ${form.autonomy_mode === mode.value ? "selected" : ""}`} aria-pressed={form.autonomy_mode === mode.value} onClick={() => setForm((prev) => ({ ...prev, autonomy_mode: mode.value }))} key={mode.value}><span className="mode-badge">{mode.badge}</span><strong>{mode.title}</strong><small>{mode.text}</small></button>)}</div><div className="launch-preview"><span>✓</span><div><strong>После создания кабинета</strong><p>Вы подключите один источник, получите первые реальные данные и сразу увидите подтверждённый результат.</p></div></div></div> : null}

          {error && savedIntakeId ? <div className="recovery-box" role="alert"><p>{error}</p><button type="button" className="ghost" disabled={loading} onClick={retrySavedWorkspace}>{loading ? "Открываем кабинет…" : "Повторить открытие кабинета"}</button></div> : error ? <div className="error-box" role="alert">{error}</div> : null}
          <div className="navigation-row"><button type="button" className="ghost" disabled={step === 0 || loading} onClick={() => setStep((value) => Math.max(0, value - 1))}>Назад</button>{step < STEP_LABELS.length - 1 ? <button type="button" className="primary" disabled={!canContinue() || loading} onClick={() => setStep((value) => Math.min(STEP_LABELS.length - 1, value + 1))}>Продолжить →</button> : <button type="button" className="primary launch" disabled={!canContinue() || loading} onClick={finishOnboarding}>{loading ? "Создаём кабинет…" : "Создать мой BusinessAIOS →"}</button>}</div>
        </section>
      </section>
      <footer className="product-footer">BusinessAIOS · безопасная автоматизация бизнеса · изменения и отправки только после проверки</footer>
    </main>
  );
}

export { getJson, postJson, isSuccessfulLiveEvidence };
