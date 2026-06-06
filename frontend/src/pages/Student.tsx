import { useEffect, useState } from "react";
import {
  AnalysisTask,
  DraftResponse,
  Notification,
  UserRead,
  apiFetch,
  apiForm,
} from "../api/client";

type StudentProps = {
  user: UserRead | null;
  authChecked: boolean;
};

export function Student({ user, authChecked }: StudentProps) {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [historyTasks, setHistoryTasks] = useState<AnalysisTask[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ignoredIssues, setIgnoredIssues] = useState<Set<string>>(new Set());
  const [checksExpanded, setChecksExpanded] = useState(false);
  const isDevMode = import.meta.env.DEV;

  // sync persisted ignored issues from backend
  useEffect(() => {
    const keys = task?.ignored_issue_keys ?? [];
    setIgnoredIssues(new Set(keys));
  }, [task?.id, task?.ignored_issue_keys?.length]);

  const requireToken = () => {
    if (!user) {
      setError("请先登录后再使用学生工作台。");
      return false;
    }
    return true;
  };

  const handleDraftSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setNotice(null);
    setError(null);
    if (!requireToken()) return;
    if (!file) {
      setError("请选择一个 PDF 文件。");
      return;
    }

    const form = new FormData();
    form.append("title", title);
    form.append("file", file);

    setLoading(true);
    try {
      const result = await apiForm<DraftResponse>("/theses/drafts", form);
      setTask(result.task);
      await loadTasks(false, result.task.id);
      setNotice("草稿已提交，分析任务已创建。");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "提交失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleTaskRefresh = async () => {
    setNotice(null);
    setError(null);
    if (!requireToken()) return;
    if (!task) {
      setError("当前还没有可刷新的稿件记录。");
      return;
    }
    setLoading(true);
    try {
      const result = await apiFetch<AnalysisTask>(`/tasks/${task.id}`);
      setTask(result);
      setHistoryTasks((prev) =>
        prev.map((t) => (t.id === result.id ? result : t))
      );
      setNotice("任务状态已刷新。");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "查询任务失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleNotifications = async () => {
    setNotice(null);
    setError(null);
    if (!requireToken()) return;
    setLoading(true);
    try {
      const result = await apiFetch<Notification[]>("/notifications?unread_only=false");
      setNotifications(result);
      setNotice("通知已加载。");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "加载通知失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const markRead = async (notificationId: number) => {
    if (!requireToken()) return;
    try {
      await apiFetch<Notification>(`/notifications/${notificationId}/read`, {
        method: "POST",
      });
      setNotifications((items) =>
        items.map((item) =>
          item.id === notificationId ? { ...item, is_read: true } : item
        )
      );
    } catch {
      setError("更新通知失败。");
    }
  };

  const loadTasks = async (showNotice = true, selectedTaskId?: number) => {
    if (!requireToken()) return;
    setLoading(true);
    try {
      const result = await apiFetch<AnalysisTask[]>("/tasks");
      setHistoryTasks(result);
      if (result.length > 0) {
        const selected =
          (selectedTaskId ? result.find((item) => item.id === selectedTaskId) : null) ?? result[0];
        setTask((prev) => {
          if (prev && prev.id === selected.id) {
            return selected;
          }
          return selected;
        });
      } else {
        setTask(null);
      }
      if (showNotice) {
        setNotice(result.length > 0 ? "历史任务已加载。" : "当前还没有历史任务。");
      }
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "加载历史任务失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authChecked || !user || user.role !== "student") return;
    void loadTasks(false);
  }, [authChecked, user]);

  useEffect(() => {
    setIgnoredIssues(new Set());
  }, [task?.id]);

  useEffect(() => {
    if (!task || (task.status !== "pending" && task.status !== "running")) return;

    const interval = setInterval(() => {
      void (async () => {
        try {
          const refreshed = await apiFetch<AnalysisTask>(`/tasks/${task.id}`);
          setTask(refreshed);
          setHistoryTasks((prev) =>
            prev.map((t) => (t.id === refreshed.id ? refreshed : t))
          );
        } catch {
          // ignore polling errors
        }
      })();
    }, 5000);

    return () => clearInterval(interval);
  }, [task?.id, task?.status]);

  const formatTaskStatus = (status: string) => {
    switch (status) {
      case "pending":
        return "排队中";
      case "running":
        return "分析中";
      case "completed":
        return "已完成";
      case "failed":
        return "失败";
      default:
        return status;
    }
  };

  const formatTime = (value?: string | null) => {
    if (!value) return "暂无";
    return new Date(value).toLocaleString("zh-CN");
  };

  const isReadyForMentor = (t: AnalysisTask | null) =>
    !!t?.result?.ready_for_mentor || !!t?.student_ready_for_mentor;

  const getTaskHeadline = () => {
    if (!task) {
      return "还没有加载论文任务";
    }
    if (task.status === "completed" && isReadyForMentor(task)) {
      return "当前稿件已经完成分析，可以考虑提交导师";
    }
    if (task.status === "completed") {
      return "当前稿件已经完成分析，建议先根据问题清单修改";
    }
    if (task.status === "failed") {
      return task.error_message || "当前稿件暂时未完成分析";
    }
    if (task.status === "running") {
      return "系统正在分析你最新提交的论文草稿";
    }
    return "任务已经创建，正在等待系统开始分析";
  };

  const getTaskNextAction = () => {
    if (!task) {
      return "如果你还没有提交论文，可以先上传新稿。提交后，这里会自动显示最新分析状态。";
    }
    if (task.status === "completed" && isReadyForMentor(task)) {
      return "建议检查摘要和问题列表，确认无误后进入导师评审阶段。";
    }
    if (task.status === "completed") {
      return "优先处理高严重度问题，修改完成后再提交新版本。";
    }
    if (task.status === "failed") {
      return "建议稍后刷新一次；如果仍未完成，可以重新提交稿件。";
    }
    return "稍后刷新状态，等待系统返回完整分析结果。";
  };

  const getTaskLabel = (item: AnalysisTask | null) => {
    if (!item) {
      return "未选择稿件";
    }
    return item.thesis_title?.trim() || "未命名稿件";
  };

  const isLowSeverity = (severity: string) => {
    const s = severity.toLowerCase();
    return (
      s.includes("低") || s.includes("low") || s.includes("minor") || s.includes("info")
    );
  };

  const formatSeverity = (severity: string) => {
    const s = severity.toLowerCase();
    if (s.includes("高") || s.includes("high")) return "高";
    if (s.includes("中") || s.includes("medium")) return "中";
    return "低";
  };

  const severityOrder = (severity: string) => {
    const s = severity.toLowerCase();
    if (s.includes("高") || s.includes("high")) return 0;
    if (s.includes("中") || s.includes("medium")) return 1;
    return 2;
  };

  const formatCheckStatus = (status: string) => {
    switch (status) {
      case "passed":
        return "通过";
      case "failed":
        return "未通过";
      case "needs_manual_review":
        return "待人工复核";
      default:
        return status;
    }
  };

  const formatLayerLabel = (layer: string) => {
    switch (layer) {
      case "rule":
        return "规则层";
      case "text_model":
        return "文本模型层";
      case "vision_model":
        return "视觉模型层";
      default:
        return layer;
    }
  };

  const formatIssuePage = (page: number, pageLabel?: string | null, pdfPage?: number | null) => {
    if (pageLabel && pdfPage && page !== pdfPage) {
      return `论文第 ${pageLabel} 页（PDF 第 ${pdfPage} 页）`;
    }
    if (pageLabel) {
      return `论文第 ${pageLabel} 页`;
    }
    return `PDF 第 ${page} 页`;
  };

  const formatCheckPages = (pages: number[], pageLabels: string[], pdfPages: number[]) => {
    if (pageLabels.length > 0) {
      return pageLabels
        .map((label, index) => {
          const page = pages[index];
          const pdfPage = pdfPages[index];
          if (pdfPage && page !== pdfPage) {
            return `${label}（PDF ${pdfPage}）`;
          }
          return label;
        })
        .join("、");
    }
    return pages.join("、");
  };

  const toggleIgnoreIssue = async (key: string) => {
    // if already ignored, un-ignore locally (no backend call needed)
    if (ignoredIssues.has(key)) {
      setIgnoredIssues((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
      return;
    }
    // in dev mode, call backend to persist; in prod, only low-severity goes through local set
    if (isDevMode && task) {
      try {
        await apiFetch(`/tasks/${task.id}/issues/${encodeURIComponent(key)}/ignore`, { method: "POST" });
      } catch (err) {
        const message =
          typeof err === "object" && err !== null && "detail" in err
            ? String((err as { detail: string }).detail)
            : "忽略失败。";
        setError(message);
        return;
      }
    }
    setIgnoredIssues((prev) => new Set(prev).add(key));
  };

  const handleSubmitForMentor = async () => {
    if (!task) return;
    setNotice(null);
    setError(null);
    setLoading(true);
    try {
      await apiFetch(`/tasks/${task.id}/submit-for-mentor`, { method: "POST" });
      await handleTaskRefresh();
      setNotice("稿件已提交进入导师评审流程。");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "提交失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const latestTask = historyTasks[0] ?? null;
  const hasActiveTask =
    !!latestTask && (latestTask.status === "pending" || latestTask.status === "running");

  return (
    <section className="section">
      <h2 className="section-title">学生工作台</h2>
      {!authChecked ? <div className="notice">正在检查登录状态...</div> : null}
      <div className="student-dashboard">
        <div className="card dashboard-hero">
          <div className="dashboard-hero-copy">
            <p className="eyebrow">当前状态</p>
            <h3>{getTaskHeadline()}</h3>
            <p className="meta">{getTaskNextAction()}</p>
          </div>
          <div className="dashboard-hero-stats">
            <div className="task-meta-card">
              <span className="meta">当前稿件</span>
              <strong>{getTaskLabel(task)}</strong>
            </div>
            <div className="task-meta-card">
              <span className="meta">分析状态</span>
              <strong>{task ? formatTaskStatus(task.status) : "暂无"}</strong>
            </div>
            <div className="task-meta-card">
              <span className="meta">导师提交建议</span>
              <strong>
                {task?.result
                  ? isReadyForMentor(task)
                    ? "可以提交导师"
                    : "建议先修改"
                  : "等待分析结果"}
              </strong>
            </div>
          </div>
        </div>

        <div className="student-console-layout">
          <div className="student-main-column">
            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">当前稿件</p>
                  <h3>论文状态总览</h3>
                </div>
                <span className={`task-badge task-${task?.status ?? "pending"}`}>
                  {task ? formatTaskStatus(task.status) : "未加载"}
                </span>
              </div>

              <div className="task-toolbar">
                <div>
                  <strong>{getTaskLabel(task)}</strong>
                  <span className="meta" style={{ marginLeft: 8 }}>
                    提交于 {formatTime(task?.created_at)}
                  </span>
                </div>
                <button className="ghost" onClick={handleTaskRefresh} disabled={loading}>
                  刷新状态
                </button>
                <button className="ghost" onClick={() => void loadTasks()} disabled={loading}>
                  刷新历史
                </button>
              </div>

              {task ? (
                <div className="task-detail">
                  <div className="task-meta-grid">
                    <div className="task-meta-card">
                      <span className="meta">开始时间</span>
                      <strong>{formatTime(task.started_at)}</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">完成时间</span>
                      <strong>{formatTime(task.finished_at)}</strong>
                    </div>
                  </div>

                  {task.result ? (
                    <div className="task-result-stack">
                      <div className="task-summary-card">
                        <h4>AI 分析摘要</h4>
                        <p>{task.result.summary}</p>
                        {task.result.global_summary && (
                          <p className="meta">全文整体复核：{task.result.global_summary}</p>
                        )}
                        {task.result.visual_summary && (
                          <p className="meta">图表视觉复核：{task.result.visual_summary}</p>
                        )}
                        <p className="meta">总体评估：{task.result.overall_assessment}</p>
                        <p className="meta">
                          下一步判断：{isReadyForMentor(task) ? "可以进入导师评审" : "建议继续修改后再提交"}
                        </p>
                        {task.result.layer_summaries.length > 0 && (
                          <div className="issue-list" style={{ marginTop: 12 }}>
                            {task.result.layer_summaries.map((layer) => (
                              <div key={layer.layer} className="issue-item">
                                <div className="issue-row">
                                  <strong>{formatLayerLabel(layer.layer)}</strong>
                                  <span className="issue-severity">
                                    {layer.passed}/{layer.total} 通过
                                  </span>
                                </div>
                                <p className="meta">
                                  未通过 {layer.failed} 项，待人工复核 {layer.needs_manual_review} 项
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="task-summary-card">
                        <h4>问题与修改建议</h4>
                        {task.result.issues.length === 0 ? (
                          <p className="meta">当前没有识别到明确问题，可以结合导师意见或自查后再决定是否提交。</p>
                        ) : (
                          <div className="issue-list">
                            {(() => {
                              const indexedIssues = task.result!.issues.map((issue, idx) => ({ ...issue, _origIdx: idx }));
                              const sortedIssues = [...indexedIssues]
                                .filter((issue) => !ignoredIssues.has(`${issue.page}-${issue.issue_type}-${issue._origIdx}`))
                                .sort((a, b) => severityOrder(a.severity) - severityOrder(b.severity) || a._origIdx - b._origIdx);
                              const highMediumCount = sortedIssues.filter(
                                (i) => !isLowSeverity(i.severity)
                              ).length;
                              const allCleared = highMediumCount === 0;
                              return (
                                <>
                                  {sortedIssues.length === 0 ? (
                                    <p className="meta">所有问题已处理或忽略。</p>
                                  ) : (
                                    sortedIssues.map((issue) => {
                                      const key = `${issue.page}-${issue.issue_type}-${issue._origIdx}`;
                                      const low = isLowSeverity(issue.severity);
                                      return (
                                        <div key={key} className="issue-item">
                                          <div className="issue-row">
                                            <strong>
                                              {formatIssuePage(issue.page, issue.page_label, issue.pdf_page)} · {issue.issue_type}
                                            </strong>
                                            <span className="issue-severity">{formatSeverity(issue.severity)}</span>
                                          </div>
                                          <p>{issue.description}</p>
                                          <p className="meta">建议修改：{issue.suggestion}</p>
                                          {(low || isDevMode) && (
                                            <button
                                              className="ghost"
                                              style={{ marginTop: 8, fontSize: 12 }}
                                              onClick={() => toggleIgnoreIssue(key)}
                                              disabled={loading}
                                            >
                                              忽略此问题{isDevMode && !low ? " (开发)" : ""}
                                            </button>
                                          )}
                                        </div>
                                      );
                                    })
                                  )}
                                  {allCleared && !isReadyForMentor(task) && (
                                    <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--stroke)" }}>
                                      <p className="meta">所有中高优先级问题已处理，可以提交进入导师评审。</p>
                                      <button
                                        className="primary"
                                        onClick={handleSubmitForMentor}
                                        disabled={loading}
                                        style={{ marginTop: 8 }}
                                      >
                                        提交进入导师评审
                                      </button>
                                    </div>
                                  )}
                                </>
                              );
                            })()}
                          </div>
                        )}
                      </div>

                      <div className="task-summary-card">
                        <h4 style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }} onClick={() => setChecksExpanded((v) => !v)}>
                          <span>{checksExpanded ? "▾" : "▸"} 逐项校验结果</span>
                          <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: "auto" }}>
                            {task.result.checks.length} 项
                          </span>
                        </h4>
                        {checksExpanded && (
                          task.result.checks.length === 0 ? (
                            <p className="meta">当前没有返回逐项校验明细。</p>
                          ) : (
                            <div className="issue-list">
                              {task.result.checks.map((check) => (
                                <div key={check.check_id} className="issue-item">
                                  <div className="issue-row">
                                    <strong>{check.title}</strong>
                                    <span className="issue-severity">{formatCheckStatus(check.status)}</span>
                                  </div>
                                  <p className="meta">
                                    {formatLayerLabel(check.layer)} · {check.source_section}
                                  </p>
                                  <p>{check.requirement}</p>
                                  <p className="meta">判定依据：{check.rationale}</p>
                                  <p className="meta">建议处理：{check.suggestion}</p>
                                  {check.pages.length > 0 && (
                                    <p className="meta">
                                      涉及页码：{formatCheckPages(check.pages, check.page_labels, check.pdf_pages)}
                                    </p>
                                  )}
                                </div>
                            ))}
                          </div>
                        )
                      )}
                      </div>
                    </div>
                  ) : task.status === "failed" ? (
                    <div className="task-summary-card">
                      <h4>分析失败</h4>
                      <p className="meta">{task.error_message || "未知错误，请稍后重试。"}</p>
                    </div>
                  ) : (
                    <div className="task-summary-card">
                      <h4>等待分析结果</h4>
                      <p className="meta">任务还没有返回结构化结果。你可以过一会刷新，或者先查看通知中心。</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="task-empty">
                  <h4>还没有加载任何任务</h4>
                  <p className="meta">如果这是第一次提交，可以直接在右侧上传新稿。提交后，这里会自动显示分析进度和修改建议。</p>
                </div>
              )}
            </div>
          </div>

          <div className="student-side-column">
            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">快速操作</p>
                  <h3>提交新稿</h3>
                </div>
              </div>
              {hasActiveTask ? (
                <div className="task-empty">
                  <h4>当前有分析任务正在进行</h4>
                  <p className="meta">请等待当前分析完成后再提交新稿。</p>
                </div>
              ) : (
                <form className="form" onSubmit={handleDraftSubmit}>
                  <div>
                    <label htmlFor="draft-title">标题</label>
                    <input
                      id="draft-title"
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="论文草稿标题"
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="draft-file">PDF 文件</label>
                    <input
                      id="draft-file"
                      type="file"
                      accept="application/pdf"
                      onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                      required
                    />
                  </div>
                  <button className="primary" type="submit" disabled={loading}>
                    {loading ? "正在提交..." : "提交新稿"}
                  </button>
                </form>
              )}
            </div>

            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">通知中心</p>
                  <h3>最近提醒</h3>
                </div>
                <button className="ghost" onClick={handleNotifications} disabled={loading}>
                  加载通知
                </button>
              </div>

              <div className="form">
                {notifications.length === 0 ? (
                  <p className="meta">暂时还没有加载通知。</p>
                ) : (
                  notifications.map((item) => (
                    <div key={item.id} className="notice">
                      <strong>{item.title}</strong>
                      <p className="meta">{item.body}</p>
                      <p className="meta">{item.created_at}</p>
                      {!item.is_read ? (
                        <button className="ghost" onClick={() => markRead(item.id)}>
                          标记已读
                        </button>
                      ) : (
                        <span className="meta">已读</span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">历史任务</p>
                  <h3>最近提交记录</h3>
                </div>
              </div>

              <div className="history-task-list">
                {historyTasks.length === 0 ? (
                  <p className="meta">当前还没有历史任务记录。</p>
                ) : (
                  historyTasks.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`history-task-item ${task?.id === item.id ? "active" : ""}`}
                      onClick={async () => {
                        if (!item.result && item.status === "completed") {
                          try {
                            const full = await apiFetch<AnalysisTask>(`/tasks/${item.id}`);
                            setTask(full);
                            setHistoryTasks((prev) =>
                              prev.map((t) => (t.id === full.id ? full : t))
                            );
                          } catch {
                            setTask(item);
                          }
                        } else {
                          setTask(item);
                        }
                      }}
                    >
                      <div className="history-task-row">
                        <strong>{getTaskLabel(item)}</strong>
                        <span className={`task-badge task-${item.status}`}>
                          {formatTaskStatus(item.status)}
                        </span>
                      </div>
                      <p className="meta">提交时间：{formatTime(item.created_at)}</p>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {notice ? <div className="notice">{notice}</div> : null}
      {error ? <div className="notice error">{error}</div> : null}
    </section>
  );
}
