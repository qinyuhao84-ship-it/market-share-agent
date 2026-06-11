// 第一章任务轮询补丁：容错状态查询、瞬时错误重试、终局结果完整拉取。
// 该文件必须在 app.js 之后加载，以覆盖原 pollOtherChapter1Task 实现。

(function () {
  const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
  const MAX_CONSECUTIVE_FAILURES = 8;
  const MAX_NOT_FOUND_RETRIES = 3;

  function wait(ms) {
    return new Promise((resolve) => {
      otherProofChapter1TaskPollTimer = window.setTimeout(resolve, ms);
    }).finally(() => {
      otherProofChapter1TaskPollTimer = null;
    });
  }

  function retryDelayMs(failureCount) {
    return Math.min(8000, 1000 + failureCount * 1000);
  }

  function formatStatusError(status, err) {
    const detail = err && err.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (detail && typeof detail === "object") return JSON.stringify(detail);
    return `HTTP ${status}`;
  }

  async function readJson(resp) {
    try {
      return await resp.json();
    } catch (_e) {
      return {};
    }
  }

  async function fetchChapter1TaskSnapshot(taskId, full) {
    const suffix = full ? "?full=true" : "";
    return fetch(`/other-proof/chapter1/tasks/${encodeURIComponent(taskId)}${suffix}`, {
      signal: otherChapter1AbortController ? otherChapter1AbortController.signal : undefined,
      cache: "no-store",
    });
  }

  pollOtherChapter1Task = async function pollOtherChapter1Task(taskId) {
    if (!taskId) return null;

    let consecutiveFailures = 0;
    let notFoundRetries = 0;
    let lastProgress = 0;

    while (true) {
      if (otherChapter1AbortController && otherChapter1AbortController.signal.aborted) {
        return null;
      }

      let resp;
      try {
        resp = await fetchChapter1TaskSnapshot(taskId, false);
      } catch (err) {
        if (err && err.name === "AbortError") return null;
        consecutiveFailures += 1;
        if (consecutiveFailures <= MAX_CONSECUTIVE_FAILURES) {
          updateChapter1State(`第一章：任务状态查询暂时失败，正在重试 ${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}`);
          setStatus(`第一章生成中：${lastProgress}%（状态查询重试中）`);
          await wait(retryDelayMs(consecutiveFailures));
          continue;
        }
        setStatus("第一章任务查询失败：连续多次无法连接状态接口", "error");
        updateChapter1State("第一章：任务查询失败");
        return null;
      }

      if (!resp.ok) {
        const err = await readJson(resp);
        const retryable = RETRYABLE_STATUS.has(resp.status);
        const notFoundCanRetry = resp.status === 404 && notFoundRetries < MAX_NOT_FOUND_RETRIES;
        if (retryable || notFoundCanRetry) {
          consecutiveFailures += 1;
          if (resp.status === 404) notFoundRetries += 1;
          if (consecutiveFailures <= MAX_CONSECUTIVE_FAILURES) {
            updateChapter1State(`第一章：任务状态暂时不可用，正在重试 ${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}`);
            setStatus(`第一章生成中：${lastProgress}%（状态接口返回 ${resp.status}，正在重试）`);
            await wait(retryDelayMs(consecutiveFailures));
            continue;
          }
        }
        setStatus("第一章任务查询失败：" + formatStatusError(resp.status, err), "error");
        updateChapter1State("第一章：任务查询失败");
        return null;
      }

      const snapshot = await readJson(resp);
      otherProofChapter1TaskSnapshot = snapshot;
      consecutiveFailures = 0;
      notFoundRetries = 0;

      const progress = Number(snapshot.progress || 0);
      lastProgress = Number.isFinite(progress) ? progress : lastProgress;
      const currentSection = String(snapshot.current_section || "").trim();
      const currentStage = String(snapshot.current_stage || "").trim();
      const modelName = String(snapshot.model_name || ReportAutomationChapter1Config.modelName || "deepseek-v4-pro").trim();

      updateChapter1State(
        `第一章：${lastProgress}%${currentSection ? `｜${currentSection}` : ""}${currentStage ? `｜${currentStage}` : ""}`
      );
      setStatus(`第一章生成中：${lastProgress}%（模型：${modelName}）`);

      if (chapter1TaskIsTerminal(snapshot)) {
        if (!Array.isArray(snapshot.legacy_sections) || !snapshot.legacy_sections.length) {
          try {
            const fullResp = await fetchChapter1TaskSnapshot(taskId, true);
            if (fullResp.ok) {
              const fullSnapshot = await readJson(fullResp);
              otherProofChapter1TaskSnapshot = fullSnapshot;
              return fullSnapshot;
            }
          } catch (_e) {
            // 终局完整结果补拉失败时，继续返回当前快照，让后续错误处理给出明确提示。
          }
        }
        return snapshot;
      }

      await wait(1200);
    }
  };
})();
