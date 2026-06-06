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
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [ignoredIssues, setIgnoredIssues] = useState<Set<string>>(new Set());
  const [checksExpanded, setChecksExpanded] = useState(false);
  const [readNotificationsExpanded, setReadNotificationsExpanded] = useState(false);
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

  const loadNotifications = async () => {
    if (!requireToken()) return;
    setNotificationsLoading(true);
    try {
      const result = await apiFetch<Notification[]>("/notifications?unread_only=false");
      setNotifications(result);
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "加载通知失败。";
      setError(message);
    } finally {
      setNotificationsLoading(false);
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
    void loadNotifications();
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

  const formatNotificationTitle = (value: string) => {
    if (value === "Draft review completed") return "草稿分析已完成";
    return value;
  };

  const formatNotificationBody = (value: string) => {
    if (value === "Your draft review is ready in the system.") {
      return "论文草稿分析结果已生成。";
    }
    return value;
  };

  const isReadyForMentor = (t: AnalysisTask | null) =>
    !!t?.result?.ready_for_mentor || !!t?.student_ready_for_mentor;

  const getCurrentPaperHint = () => {
    if (!task) {
      return "提交论文后会显示在这里。";
    }
    if (task.status === "completed" && isReadyForMentor(task)) {
      return "可以提交导师评审。";
    }
    if (task.status === "completed") {
      return priorityIssues.length > 0
        ? `建议先处理 ${priorityIssues.length} 条重点问题。`
        : "建议检查问题清单后提交新版本。";
    }
    if (task.status === "failed") {
      return "分析失败，可以重新提交或稍后查看。";
    }
    if (task.status === "running") {
      return "正在分析，完成后会自动更新。";
    }
    return "等待开始分析。";
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

  const getSeverityClassName = (severity: string) => {
    const s = severity.toLowerCase();
    if (s.includes("高") || s.includes("high")) return "severity-high";
    if (s.includes("中") || s.includes("medium")) return "severity-medium";
    return "severity-low";
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

  const getCheckStatusClassName = (status: string) => {
    switch (status) {
      case "passed":
        return "check-status-passed";
      case "failed":
        return "check-status-failed";
      case "needs_manual_review":
        return "check-status-manual";
      default:
        return "";
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
  const result = task?.result ?? null;
  const layerSummaries = result?.layer_summaries ?? [];
  const summaryChecks = layerSummaries.reduce((total, layer) => total + layer.total, 0);
  const failedChecks = layerSummaries.reduce((total, layer) => total + layer.failed, 0);
  const manualReviewChecks = layerSummaries.reduce(
    (total, layer) => total + layer.needs_manual_review,
    0
  );
  const indexedIssues =
    result?.issues.map((issue, idx) => ({
      ...issue,
      _origIdx: idx,
      _key: `${issue.page}-${issue.issue_type}-${idx}`,
    })) ?? [];
  const visibleIssues = indexedIssues
    .filter((issue) => !ignoredIssues.has(issue._key))
    .sort(
      (a, b) => severityOrder(a.severity) - severityOrder(b.severity) || a._origIdx - b._origIdx
    );
  const priorityIssues = visibleIssues.filter((issue) => !isLowSeverity(issue.severity));
  const allPriorityIssuesCleared = priorityIssues.length === 0;
  const unreadNotifications = notifications.filter((item) => !item.is_read);
  const readNotifications = notifications.filter((item) => item.is_read);

  const renderNotification = (item: Notification) => (
    <div
      key={item.id}
      className={`notification-item ${item.is_read ? "is-read" : "is-unread"}`}
    >
      <strong>{formatNotificationTitle(item.title)}</strong>
      <p className="meta">{formatNotificationBody(item.body)}</p>
      <p className="meta">{formatTime(item.created_at)}</p>
      {!item.is_read ? (
        <button className="ghost" onClick={() => markRead(item.id)}>
          标记已读
        </button>
      ) : (
        <span className="notification-read-state">已读</span>
      )}
    </div>
  );

  return (
    <section className="section">
      <h2 className="section-title">学生工作台</h2>
      {!authChecked ? <div className="notice">正在检查登录状态...</div> : null}
      <div className="student-dashboard">
        <div className="card dashboard-hero">
          <div className="dashboard-hero-bar">
            <div className="dashboard-hero-copy">
              <p className="eyebrow">当前处理论文</p>
              <h3>{task ? getTaskLabel(task) : "暂无处理中的论文"}</h3>
              <p className="meta">{getCurrentPaperHint()}</p>
            </div>
          </div>
        </div>

        <div className="student-console-layout">
          <div className="student-main-column">
            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">当前稿件</p>
                </div>
                <span className={`task-badge task-${task?.status ?? "pending"}`}>
                  {task ? formatTaskStatus(task.status) : "未加载"}
                </span>
              </div>

              {task ? (
                <div className="task-detail">
                  <div className="task-meta-grid">
                    <div className="task-meta-card">
                      <span className="meta">提交时间</span>
                      <strong>{formatTime(task.created_at)}</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">开始分析</span>
                      <strong>{formatTime(task.started_at)}</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">完成时间</span>
                      <strong>{formatTime(task.finished_at)}</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">导师阶段</span>
                      <strong>
                        {result
                          ? isReadyForMentor(task)
                            ? "可以提交导师"
                            : "建议修改后提交"
                          : "等待分析结果"}
                      </strong>
                    </div>
                  </div>

                  {result ? (
                    <div className="task-result-stack">
                      <div className="task-overview-grid">
                        <div className="task-summary-card overview-highlight">
                          <p className="eyebrow">核心结论</p>
                          <h4>{result.summary}</h4>
                          <p className="meta">总体评估：{result.overall_assessment}</p>
                          <p className="meta">
                            下一步判断：
                            {isReadyForMentor(task) ? "可以进入导师评审" : "建议继续修改后再提交"}
                          </p>
                        </div>
                        <div className="task-summary-card overview-metrics">
                          <div className="overview-metric">
                            <span className="meta">检查总数</span>
                            <strong>{summaryChecks || result.checks.length}</strong>
                          </div>
                          <div className="overview-metric">
                            <span className="meta">未通过</span>
                            <strong>{failedChecks}</strong>
                          </div>
                          <div className="overview-metric">
                            <span className="meta">待人工复核</span>
                            <strong>{manualReviewChecks}</strong>
                          </div>
                          <div className="overview-metric">
                            <span className="meta">重点问题</span>
                            <strong>{priorityIssues.length}</strong>
                          </div>
                        </div>
                      </div>

                      {(result.global_summary || result.visual_summary || layerSummaries.length > 0) && (
                        <div className="task-summary-card">
                          <h4>分析视角</h4>
                          <div className="analysis-insight-grid">
                            {result.global_summary ? (
                              <div className="issue-item">
                                <strong>全文整体复核</strong>
                                <p className="meta">{result.global_summary}</p>
                              </div>
                            ) : null}
                            {result.visual_summary ? (
                              <div className="issue-item">
                                <strong>图表视觉复核</strong>
                                <p className="meta">{result.visual_summary}</p>
                              </div>
                            ) : null}
                          </div>
                          {layerSummaries.length > 0 ? (
                            <div className="layer-summary-grid">
                              {layerSummaries.map((layer) => (
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
                          ) : null}
                        </div>
                      )}

                      <div className="task-summary-card">
                        <div className="section-heading compact">
                          <div>
                            <h4>问题与修改建议</h4>
                          </div>
                          <span className="issue-count-pill">{visibleIssues.length} 条待处理</span>
                        </div>

                        {result.issues.length === 0 ? (
                          <p className="meta">当前没有识别到明确问题，可以结合导师意见或自查后再决定是否提交。</p>
                        ) : (
                          <div className="issue-list">
                            {visibleIssues.length === 0 ? (
                              <p className="meta">所有问题已处理或忽略。</p>
                            ) : (
                              visibleIssues.map((issue) => {
                                const low = isLowSeverity(issue.severity);
                                return (
                                  <div key={issue._key} className="issue-item issue-card">
                                    <div className="issue-row">
                                      <strong>
                                        {formatIssuePage(
                                          issue.page,
                                          issue.page_label,
                                          issue.pdf_page
                                        )}{" "}
                                        · {issue.issue_type}
                                      </strong>
                                    <span
                                      className={`issue-severity ${getSeverityClassName(
                                        issue.severity
                                      )}`}
                                    >
                                      {formatSeverity(issue.severity)}
                                    </span>
                                    </div>
                                    <p>{issue.description}</p>
                                    <p className="meta">建议修改：{issue.suggestion}</p>
                                    {(low || isDevMode) && (
                                      <button
                                        className="ghost"
                                        style={{ marginTop: 8, fontSize: 12 }}
                                        onClick={() => toggleIgnoreIssue(issue._key)}
                                        disabled={loading}
                                      >
                                        忽略此问题{isDevMode && !low ? " (开发)" : ""}
                                      </button>
                                    )}
                                  </div>
                                );
                              })
                            )}
                            {allPriorityIssuesCleared && !isReadyForMentor(task) ? (
                              <div className="mentor-submit-panel">
                                <p className="meta">
                                  所有中高优先级问题已处理，可以提交进入导师评审。
                                </p>
                                <button
                                  className="primary"
                                  onClick={handleSubmitForMentor}
                                  disabled={loading}
                                >
                                  提交进入导师评审
                                </button>
                              </div>
                            ) : null}
                          </div>
                        )}
                      </div>

                      <div className="task-summary-card">
                        <h4
                          style={{
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                          }}
                          onClick={() => setChecksExpanded((v) => !v)}
                        >
                          <span>{checksExpanded ? "▾" : "▸"} 逐项校验结果</span>
                          <span
                            style={{
                              fontSize: 12,
                              color: "var(--muted)",
                              marginLeft: "auto",
                            }}
                          >
                            {result.checks.length} 项
                          </span>
                        </h4>
                        {checksExpanded ? (
                          result.checks.length === 0 ? (
                            <p className="meta">当前没有返回逐项校验明细。</p>
                          ) : (
                            <div className="issue-list">
                              {result.checks.map((check) => (
                                <div key={check.check_id} className="issue-item">
                                  <div className="issue-row">
                                    <strong>{check.title}</strong>
                                    <span
                                      className={`issue-severity ${getCheckStatusClassName(
                                        check.status
                                      )}`}
                                    >
                                      {formatCheckStatus(check.status)}
                                    </span>
                                  </div>
                                  <p className="meta">
                                    {formatLayerLabel(check.layer)} · {check.source_section}
                                  </p>
                                  <p>{check.requirement}</p>
                                  <p className="meta">判定依据：{check.rationale}</p>
                                  <p className="meta">建议处理：{check.suggestion}</p>
                                  {check.pages.length > 0 ? (
                                    <p className="meta">
                                      涉及页码：
                                      {formatCheckPages(
                                        check.pages,
                                        check.page_labels,
                                        check.pdf_pages
                                      )}
                                    </p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          )
                        ) : null}
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
                      <p className="meta">
                        任务还没有返回结构化结果。你可以过一会刷新，或者先查看通知中心。
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="task-empty">
                  <h4>还没有加载任何任务</h4>
                  <p className="meta">
                    如果这是第一次提交，可以直接在右侧上传新稿。提交后，这里会自动显示分析进度和修改建议。
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="student-side-column">
            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">提交新稿</p>
                </div>
              </div>
              {hasActiveTask ? (
                <div className="task-empty">
                  <h4>当前有分析任务正在进行</h4>
                  <p className="meta">请等待当前分析完成后再提交新稿。</p>
                </div>
              ) : (
                <form className="form draft-form" onSubmit={handleDraftSubmit}>
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
                    <label htmlFor="draft-file" className="file-upload">
                      <input
                        id="draft-file"
                        className="file-input"
                        type="file"
                        accept="application/pdf"
                        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                        required
                      />
                      <span className={`file-upload-name ${file ? "has-file" : ""}`}>
                        {file ? file.name : "未选择任何文件"}
                      </span>
                    </label>
                  </div>
                  <button className="primary" type="submit" disabled={loading}>
                    {loading ? "正在提交..." : "提交"}
                  </button>
                </form>
              )}
            </div>

            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">通知中心</p>
                </div>
              </div>

              <div className="form">
                {notificationsLoading && notifications.length === 0 ? (
                  <p className="meta">正在加载通知...</p>
                ) : notifications.length === 0 ? (
                  <p className="meta">暂无通知。</p>
                ) : (
                  <>
                    {unreadNotifications.length > 0 ? (
                      unreadNotifications.map(renderNotification)
                    ) : (
                      <p className="meta">暂无未读通知。</p>
                    )}
                    {readNotifications.length > 0 ? (
                      <div className="read-notification-group">
                        <button
                          type="button"
                          className="read-notification-toggle"
                          onClick={() => setReadNotificationsExpanded((value) => !value)}
                        >
                          <span>{readNotificationsExpanded ? "收起已读通知" : "已读通知"}</span>
                          <span>{readNotifications.length} 条</span>
                        </button>
                        {readNotificationsExpanded ? (
                          <div className="read-notification-list">
                            {readNotifications.map(renderNotification)}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            </div>

            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">历史任务</p>
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
