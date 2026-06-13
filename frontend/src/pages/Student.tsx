import { useEffect, useState } from "react";
import {
  AnalysisTask,
  DraftResponse,
  Notification,
  ThesisVersionTask,
  ThesisWorkspace,
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
  const [theses, setTheses] = useState<ThesisWorkspace[]>([]);
  const [selectedThesisId, setSelectedThesisId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [ignoredIssues, setIgnoredIssues] = useState<Set<string>>(new Set());
  const [checksExpanded, setChecksExpanded] = useState(false);
  const [readNotificationsExpanded, setReadNotificationsExpanded] = useState(false);
  const isDevMode = import.meta.env.DEV;

  const requireToken = () => {
    if (!user) {
      setError("请先登录后再使用学生工作台。");
      return false;
    }
    return true;
  };

  const getSelectedThesis = (items = theses) =>
    items.find((item) => item.id === selectedThesisId) ?? items[0] ?? null;

  const getSelectedVersion = (thesis: ThesisWorkspace | null) => {
    if (!thesis) return null;
    return (
      thesis.versions.find((version) => version.id === selectedVersionId) ??
      thesis.current_version ??
      thesis.versions[0] ??
      null
    );
  };

  const selectedThesis = getSelectedThesis();
  const selectedVersion = getSelectedVersion(selectedThesis);
  const task = selectedVersion?.latest_task ?? null;

  useEffect(() => {
    const keys = task?.ignored_issue_keys ?? [];
    setIgnoredIssues(new Set(keys));
  }, [task?.id, task?.ignored_issue_keys]);

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

  const loadTheses = async (showNotice = true, thesisId?: number, versionId?: number) => {
    if (!requireToken()) return;
    setLoading(true);
    try {
      const result = await apiFetch<ThesisWorkspace[]>("/theses");
      setTheses(result);

      const nextSelectedThesis =
        (thesisId ? result.find((item) => item.id === thesisId) : null) ??
        result.find((item) => item.id === selectedThesisId) ??
        result[0] ??
        null;
      const nextSelectedVersion =
        nextSelectedThesis?.versions.find((item) => item.id === versionId) ??
        nextSelectedThesis?.versions.find((item) => item.id === selectedVersionId) ??
        nextSelectedThesis?.current_version ??
        nextSelectedThesis?.versions[0] ??
        null;

      setSelectedThesisId(nextSelectedThesis?.id ?? null);
      setSelectedVersionId(nextSelectedVersion?.id ?? null);

      if (nextSelectedThesis) {
        setTitle(nextSelectedThesis.title);
      }

      if (showNotice) {
        setNotice(result.length > 0 ? "论文任务已加载。" : "当前还没有论文任务。");
      }
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "加载论文任务失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authChecked || !user || user.role !== "student") return;
    void loadTheses(false);
    void loadNotifications();
  }, [authChecked, user]);

  useEffect(() => {
    if (!selectedThesis) {
      setTitle("");
      return;
    }
    setTitle(selectedThesis.title);
  }, [selectedThesis?.id]);

  useEffect(() => {
    if (!task || (task.status !== "pending" && task.status !== "running")) return;

    const interval = setInterval(() => {
      void loadTheses(false, selectedThesis?.id ?? undefined, selectedVersion?.id ?? undefined);
    }, 5000);

    return () => clearInterval(interval);
  }, [task?.id, task?.status, selectedThesis?.id, selectedVersion?.id]);

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
    if (selectedThesis && selectedThesis.status !== "approved") {
      form.append("thesis_id", String(selectedThesis.id));
    }

    setLoading(true);
    try {
      const result = await apiForm<DraftResponse>("/theses/drafts", form);
      setFile(null);
      await loadTheses(false, result.thesis_id, result.version_id);
      setNotice(
        selectedThesis && selectedThesis.status !== "approved"
          ? "已提交论文新版本，AI 正在处理中。"
          : "已创建新的论文任务，AI 正在处理中。"
      );
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
    if (!selectedThesis) {
      setError("当前还没有可刷新的论文任务。");
      return;
    }
    await loadTheses(true, selectedThesis.id, selectedVersion?.id);
  };

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

  const formatThesisStatus = (status: string) => {
    switch (status) {
      case "analysis_pending":
        return "AI 处理中";
      case "analysis_done":
        return "待提交导师";
      case "changes_requested":
        return "待修改";
      case "mentor_review":
        return "审核中";
      case "approved":
        return "已完成";
      default:
        return status;
    }
  };

  const formatStage = (stage: string) => {
    switch (stage) {
      case "draft":
        return "初稿";
      case "revision":
        return "修改稿";
      case "final":
        return "定稿";
      default:
        return stage;
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
    if (!selectedThesis) {
      return "提交论文后会在这里形成一个持续推进的论文任务。";
    }
    switch (selectedThesis.status) {
      case "analysis_pending":
        return "AI 正在处理当前版本，处理完成后再决定是否提交导师。";
      case "analysis_done":
        return isReadyForMentor(task)
          ? "分析已完成，可以整理后提交导师审核。"
          : "分析已完成，建议先根据问题清单继续修改。";
      case "changes_requested":
        return "导师已退回修改，继续上传新版本后会重新进入 AI 分析。";
      case "mentor_review":
        return "当前版本正在导师审核中，审核期间不能再次提交。";
      case "approved":
        return "论文任务已通过导师审核。";
      default:
        return "继续围绕这篇论文迭代版本。";
    }
  };

  const getTaskLabel = (item: ThesisWorkspace | null) => {
    if (!item) {
      return "暂无处理中的论文";
    }
    return item.title?.trim() || "未命名论文";
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
    if (!task) return;
    if (ignoredIssues.has(key)) {
      setIgnoredIssues((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
      return;
    }
    if (isDevMode) {
      try {
        await apiFetch(`/tasks/${task.id}/issues/${encodeURIComponent(key)}/ignore`, {
          method: "POST",
        });
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
    if (!task || !selectedThesis) return;
    setNotice(null);
    setError(null);
    setLoading(true);
    try {
      await apiFetch(`/tasks/${task.id}/submit-for-mentor`, { method: "POST" });
      await loadTheses(false, selectedThesis.id, selectedVersion?.id);
      setNotice("当前版本已提交导师审核。");
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
  const currentTaskRunning =
    !!selectedThesis?.current_version?.latest_task &&
    (selectedThesis.current_version.latest_task.status === "pending" ||
      selectedThesis.current_version.latest_task.status === "running");
  const uploadBlockedByReview = selectedThesis?.status === "mentor_review";
  const continueCurrentThesis = !!selectedThesis && selectedThesis.status !== "approved";

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

  const renderVersionButton = (version: ThesisVersionTask) => (
    <button
      key={version.id}
      type="button"
      className={`history-task-item ${selectedVersionId === version.id ? "active" : ""}`}
      onClick={() => setSelectedVersionId(version.id)}
    >
      <div className="history-task-row">
        <strong>第 {version.version_no} 版</strong>
        <span className={`task-badge task-${version.latest_task?.status ?? "pending"}`}>
          {version.latest_task ? formatTaskStatus(version.latest_task.status) : "未分析"}
        </span>
      </div>
      <p className="meta">
        {formatStage(version.stage)} · 提交时间：{formatTime(version.submitted_at)}
      </p>
    </button>
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
              <h3>{getTaskLabel(selectedThesis)}</h3>
              <p className="meta">{getCurrentPaperHint()}</p>
            </div>
          </div>
        </div>

        <div className="student-console-layout">
          <div className="student-main-column">
            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">当前论文任务</p>
                </div>
                <span className={`task-badge task-${selectedThesis?.status ?? "pending"}`}>
                  {selectedThesis ? formatThesisStatus(selectedThesis.status) : "未加载"}
                </span>
              </div>

              {selectedThesis ? (
                <div className="task-detail">
                  <div className="task-meta-grid">
                    <div className="task-meta-card">
                      <span className="meta">论文状态</span>
                      <strong>{formatThesisStatus(selectedThesis.status)}</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">当前版本</span>
                      <strong>
                        {selectedVersion
                          ? `第 ${selectedVersion.version_no} 版（${formatStage(selectedVersion.stage)}）`
                          : "暂无"}
                      </strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">版本提交时间</span>
                      <strong>{formatTime(selectedVersion?.submitted_at)}</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">AI 分析状态</span>
                      <strong>{task ? formatTaskStatus(task.status) : "暂无"}</strong>
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
                            {selectedThesis.status === "mentor_review"
                              ? "等待导师审核"
                              : isReadyForMentor(task)
                                ? "可以进入导师评审"
                                : "建议继续修改后再提交"}
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
                                    {(low || isDevMode) && selectedThesis.status !== "mentor_review" ? (
                                      <button
                                        className="ghost"
                                        style={{ marginTop: 8, fontSize: 12 }}
                                        onClick={() => toggleIgnoreIssue(issue._key)}
                                        disabled={loading}
                                      >
                                        忽略此问题{isDevMode && !low ? " (开发)" : ""}
                                      </button>
                                    ) : null}
                                  </div>
                                );
                              })
                            )}
                            {allPriorityIssuesCleared &&
                            !isReadyForMentor(task) &&
                            selectedThesis.status !== "mentor_review" ? (
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
                          onClick={() => setChecksExpanded((value) => !value)}
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
                  ) : task?.status === "failed" ? (
                    <div className="task-summary-card">
                      <h4>分析失败</h4>
                      <p className="meta">{task.error_message || "未知错误，请稍后重试。"}</p>
                    </div>
                  ) : (
                    <div className="task-summary-card">
                      <h4>等待分析结果</h4>
                      <p className="meta">
                        当前版本还没有返回结构化结果。你可以稍后刷新，或先查看通知中心。
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="task-empty">
                  <h4>还没有加载任何论文任务</h4>
                  <p className="meta">
                    首次提交后，这里会按同一篇论文展示多个版本、AI 分析和导师审核状态。
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="student-side-column">
            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">{continueCurrentThesis ? "提交新版本" : "创建论文任务"}</p>
                </div>
              </div>
              {uploadBlockedByReview ? (
                <div className="task-empty">
                  <h4>当前版本正在导师审核中</h4>
                  <p className="meta">导师处理完成前，不允许再次提交新版本。</p>
                </div>
              ) : currentTaskRunning ? (
                <div className="task-empty">
                  <h4>当前有 AI 分析任务正在进行</h4>
                  <p className="meta">请等待当前版本分析完成后再提交下一版。</p>
                </div>
              ) : (
                <form className="form draft-form" onSubmit={handleDraftSubmit}>
                  <div>
                    <label htmlFor="draft-title">标题</label>
                    <input
                      id="draft-title"
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="论文标题"
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
                    {loading
                      ? "正在提交..."
                      : continueCurrentThesis
                        ? "提交新版本"
                        : "创建并提交"}
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
                  <p className="eyebrow">论文与版本</p>
                </div>
                <button className="ghost" type="button" onClick={handleTaskRefresh} disabled={loading}>
                  刷新
                </button>
              </div>

              <div className="history-task-list">
                {theses.length === 0 ? (
                  <p className="meta">当前还没有论文任务记录。</p>
                ) : (
                  theses.map((item) => (
                    <div key={item.id} className="issue-item">
                      <button
                        type="button"
                        className={`history-task-item ${selectedThesisId === item.id ? "active" : ""}`}
                        onClick={() => {
                          setSelectedThesisId(item.id);
                          setSelectedVersionId(item.current_version?.id ?? item.versions[0]?.id ?? null);
                        }}
                      >
                        <div className="history-task-row">
                          <strong>{item.title}</strong>
                          <span className={`task-badge task-${item.status}`}>
                            {formatThesisStatus(item.status)}
                          </span>
                        </div>
                        <p className="meta">
                          共 {item.versions.length} 个版本 · 更新时间：{formatTime(item.updated_at)}
                        </p>
                      </button>
                      {selectedThesisId === item.id ? (
                        <div style={{ marginTop: 8 }}>{item.versions.map(renderVersionButton)}</div>
                      ) : null}
                    </div>
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
