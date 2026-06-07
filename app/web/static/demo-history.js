export const HISTORY_STORAGE_KEY = "demoEvaluationHistory";
export const HISTORY_MAX_ITEMS = 30;

export function loadEvaluationHistory(storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem(HISTORY_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveEvaluationHistory(items, storage = globalThis.localStorage) {
  storage?.setItem(HISTORY_STORAGE_KEY, JSON.stringify(items));
}

export function appendEvaluationHistory(entry, storage = globalThis.localStorage) {
  const next = [entry, ...loadEvaluationHistory(storage).filter((item) => item.id !== entry.id)].slice(
    0,
    HISTORY_MAX_ITEMS,
  );
  saveEvaluationHistory(next, storage);
  return next;
}

export function removeEvaluationHistoryItem(id, storage = globalThis.localStorage) {
  const next = loadEvaluationHistory(storage).filter((item) => item.id !== id);
  saveEvaluationHistory(next, storage);
  return next;
}

export function clearEvaluationHistory(storage = globalThis.localStorage) {
  storage?.removeItem(HISTORY_STORAGE_KEY);
  return [];
}

export function createHistoryEntry(state, result, getPresetById) {
  const evaluation = result.evaluation ?? result;
  const preset = getPresetById(state.activePresetId);
  const runId = evaluation.run_id ?? result.simulation_id ?? `hist_${Date.now()}`;
  return {
    id: runId,
    savedAt: new Date().toISOString(),
    presetId: state.activePresetId,
    presetLabel: preset?.label ?? state.activePresetId ?? "未命名案例",
    scenarioLabel: result.scenario_label ?? result.scenario_key ?? "默认场景",
    overallScore: Number(evaluation.overall_score ?? result.overall_score ?? 0),
    needsReview: Boolean(evaluation.needs_review ?? result.needs_review),
    grade: evaluation.evaluation_summary?.grade ?? "",
    confidence: Number(evaluation.confidence ?? result.confidence ?? 0),
    result,
  };
}

export function formatHistoryTime(iso) {
  if (!iso) {
    return "-";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
}

export function buildHistoryPanelHtml(history, activeId) {
  if (!history.length) {
    return `<p class="history-empty">暂无记录。每次运行模拟评测后会自动保存到这里。</p>`;
  }

  return history
    .map((item) => {
      const level =
        item.overallScore >= 80 ? "good" : item.overallScore >= 60 ? "mid" : item.overallScore > 0 ? "low" : "neutral";
      const active = item.id === activeId ? " is-active" : "";
      const reviewTag = item.needsReview ? `<span class="history-item__tag">需复核</span>` : "";
      const gradeTag = item.grade ? `<span class="history-item__tag">${item.grade}</span>` : "";
      return `<article class="history-item${active}" data-history-id="${item.id}">
        <button type="button" class="history-item__open" data-history-open="${item.id}">
          <span class="history-item__score" data-level="${level}">${item.overallScore.toFixed(1)}</span>
          <span class="history-item__body">
            <span class="history-item__title">${escapeHtml(item.scenarioLabel)}</span>
            <span class="history-item__meta">${escapeHtml(item.presetLabel)} · ${formatHistoryTime(item.savedAt)}</span>
            <span class="history-item__tags">${gradeTag}${reviewTag}</span>
          </span>
        </button>
        <button
          type="button"
          class="history-item__delete"
          data-history-delete="${item.id}"
          aria-label="删除记录"
          title="删除记录"
        >删除</button>
      </article>`;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
