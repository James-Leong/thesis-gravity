import { useEffect, useState } from "react";
import {
  API_BASE_URL,
  AnalysisCheck,
  AnalysisIssue,
  AnalysisTask,
  MentorApplication,
  MentorPendingReview,
  MentorReview,
  MentorReviewSubmission,
  MentorStudentItem,
  MentorStudentList,
  MentorTrackedThesis,
  MentorVersionDetail,
  UserRead,
  apiFetch,
} from "../api/client";

type MentorProps = {
  user: UserRead;
};

export function Mentor({ user }: MentorProps) {
  const [activeTab, setActiveTab] = useState<"reviews" | "applications" | "students">("reviews");
  const [pendingReviews, setPendingReviews] = useState<MentorPendingReview[]>([]);
  const [trackedTheses, setTrackedTheses] = useState<MentorTrackedThesis[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [versionDetail, setVersionDetail] = useState<MentorVersionDetail | null>(null);
  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(true);
  const [progressPanelOpen, setProgressPanelOpen] = useState(false);
  const [progressQuery, setProgressQuery] = useState("");
  const [decision, setDecision] = useState<"approved" | "changes_requested">("approved");
  const [comments, setComments] = useState("");
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checksExpanded, setChecksExpanded] = useState(false);
  // Applications & students
  const [applications, setApplications] = useState<MentorApplication[]>([]);
  const [students, setStudents] = useState<MentorStudentItem[]>([]);
  const [studentTotal, setStudentTotal] = useState(0);
  const [studentPage, setStudentPage] = useState(0);
  const [studentHasMore, setStudentHasMore] = useState(true);
  const PAGE_SIZE = 20;

  const loadPendingReviews = async (showNotice = true) => {
    setInitialLoading(true);
    try {
      const result = await apiFetch<MentorPendingReview[]>("/mentor/pending-reviews");
      setPendingReviews(result);
      if (result.length > 0 && !selectedVersionId) {
        setSelectedVersionId(result[0].version.id);
      }
      if (showNotice) {
        setNotice(`已加载 ${result.length} 条待评审记录。`);
      }
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "加载待评审列表失败。";
      setError(message);
    } finally {
      setInitialLoading(false);
    }
  };

  const loadVersionDetail = async (versionId: number) => {
    try {
      const result = await apiFetch<MentorVersionDetail>(`/mentor/versions/${versionId}`);
      setVersionDetail(result);
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "加载版本详情失败。";
      setError(message);
    }
  };

  const loadTrackedTheses = async (query = "", showNotice = false) => {
    try {
      const params = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";
      const result = await apiFetch<MentorTrackedThesis[]>(`/mentor/theses${params}`);
      setTrackedTheses(result);
      if (showNotice) {
        setNotice(query.trim() ? `已筛选出 ${result.length} 条论文进度。` : `已加载 ${result.length} 条论文进度。`);
      }
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "加载论文进度失败。";
      setError(message);
    }
  };

  useEffect(() => {
    void loadPendingReviews(false);
    void loadTrackedTheses();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedVersionId) {
      setVersionDetail(null);
      return;
    }
    void loadVersionDetail(selectedVersionId);
  }, [selectedVersionId]);

  const loadApplications = async () => {
    try {
      const result = await apiFetch<MentorApplication[]>("/mentor/applications");
      setApplications(result);
    } catch {
      // ignore
    }
  };

  const loadStudents = async (append = false) => {
    try {
      const skip = append ? (studentPage + 1) * PAGE_SIZE : 0;
      const result = await apiFetch<MentorStudentList>(
        `/mentor/students?skip=${skip}&limit=${PAGE_SIZE}`
      );
      setStudentTotal(result.total);
      if (append) {
        setStudents((prev) => [...prev, ...result.items]);
        setStudentPage((p) => p + 1);
      } else {
        setStudents(result.items);
        setStudentPage(0);
      }
      setStudentHasMore(skip + result.items.length < result.total);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    void loadApplications();
    void loadStudents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-refresh data for the active tab every 10s
  useEffect(() => {
    const interval = setInterval(() => {
      if (activeTab === "reviews") {
        void loadPendingReviews(false);
        void loadTrackedTheses(progressQuery);
      } else if (activeTab === "applications") {
        void loadApplications();
      } else {
        void loadStudents();
      }
    }, 10_000);
    return () => clearInterval(interval);
  }, [activeTab, progressQuery]);

  const handleApproveApplication = async (applicationId: number) => {
    setNotice(null);
    setError(null);
    try {
      await apiFetch(`/mentor/applications/${applicationId}/approve`, { method: "POST" });
      setNotice("已批准该申请。");
      void loadApplications();
      void loadStudents();
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "操作失败。";
      setError(message);
    }
  };

  const handleRejectApplication = async (applicationId: number) => {
    setNotice(null);
    setError(null);
    try {
      await apiFetch(`/mentor/applications/${applicationId}/reject`, { method: "POST" });
      setNotice("已拒绝该申请。");
      void loadApplications();
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "操作失败。";
      setError(message);
    }
  };

  const handleSubmitReview = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedVersionId) return;

    setNotice(null);
    setError(null);
    setLoading(true);
    try {
      const result = await apiFetch<MentorReviewSubmission>("/mentor/reviews", {
        method: "POST",
        body: JSON.stringify({
          version_id: selectedVersionId,
          decision,
          comments: comments.trim() || null,
        }),
      });
      setNotice(
        result.review.decision === "approved"
          ? `已通过《${result.thesis.title}》的评审。`
          : `已退回《${result.thesis.title}》要求修改。`
      );
      setComments("");
      setSelectedVersionId(result.version.id);
      await loadVersionDetail(result.version.id);
      await loadPendingReviews(false);
      await loadTrackedTheses(progressQuery);
      setProgressPanelOpen(true);
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "提交评审失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (value?: string | null) => {
    if (!value) return "暂无";
    return new Date(value).toLocaleString("zh-CN");
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

  const formatDecision = (decisionValue: string) => {
    switch (decisionValue) {
      case "approved":
        return "通过";
      case "changes_requested":
        return "退回修改";
      default:
        return decisionValue;
    }
  };

  const formatDecisionBadgeClass = (decisionValue: string) => {
    switch (decisionValue) {
      case "approved":
        return "check-status-passed";
      case "changes_requested":
        return "check-status-failed";
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

  const renderAnalysisResult = (task: AnalysisTask | null) => {
    if (!task) {
      return (
        <div className="task-empty">
          <h4>暂无分析任务</h4>
          <p className="meta">该版本尚未生成分析结果。</p>
        </div>
      );
    }

    if (task.status !== "completed" || !task.result) {
      return (
        <div className="task-empty">
          <h4>分析尚未完成</h4>
          <p className="meta">当前状态：{formatTaskStatus(task.status)}</p>
          {task.error_message ? <p className="meta">{task.error_message}</p> : null}
        </div>
      );
    }

    const result = task.result;
    const layerSummaries = result.layer_summaries ?? [];
    const summaryChecks = layerSummaries.reduce((total, layer) => total + layer.total, 0);
    const failedChecks = layerSummaries.reduce((total, layer) => total + layer.failed, 0);
    const manualReviewChecks = layerSummaries.reduce(
      (total, layer) => total + layer.needs_manual_review,
      0
    );
    const priorityIssues = (result.issues ?? []).filter((issue: AnalysisIssue) => {
      const s = issue.severity.toLowerCase();
      return !(s.includes("低") || s.includes("low") || s.includes("minor") || s.includes("info"));
    });

    return (
      <div className="task-result-stack">
        <div className="task-overview-grid">
          <div className="task-summary-card overview-highlight">
            <p className="eyebrow">核心结论</p>
            <h4>{result.summary}</h4>
            <p className="meta">总体评估：{result.overall_assessment}</p>
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
            <span className="issue-count-pill">{(result.issues ?? []).length} 条</span>
          </div>
          {(result.issues ?? []).length === 0 ? (
            <p className="meta">当前没有识别到明确问题。</p>
          ) : (
            <div className="issue-list">
              {(result.issues ?? []).map((issue: AnalysisIssue, idx: number) => (
                <div key={idx} className="issue-item issue-card">
                  <div className="issue-row">
                    <strong>
                      {formatIssuePage(issue.page, issue.page_label, issue.pdf_page)} ·{" "}
                      {issue.issue_type}
                    </strong>
                    <span className={`issue-severity ${getSeverityClassName(issue.severity)}`}>
                      {formatSeverity(issue.severity)}
                    </span>
                  </div>
                  <p>{issue.description}</p>
                  <p className="meta">建议修改：{issue.suggestion}</p>
                </div>
              ))}
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
                {result.checks.map((check: AnalysisCheck) => (
                  <div key={check.check_id} className="issue-item">
                    <div className="issue-row">
                      <strong>{check.title}</strong>
                      <span
                        className={`issue-severity ${getCheckStatusClassName(check.status)}`}
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
                        {formatCheckPages(check.pages, check.page_labels, check.pdf_pages)}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            )
          ) : null}
        </div>
      </div>
    );
  };

  const renderReviews = (reviews: MentorReview[]) => {
    if (reviews.length === 0) return null;
    return (
      <div className="task-summary-card">
        <h4>历史评审记录</h4>
        <div className="issue-list">
          {reviews.map((review) => (
            <div key={review.id} className="issue-item">
              <div className="issue-row">
                <strong>{formatTime(review.created_at)}</strong>
                <span className={`issue-severity ${formatDecisionBadgeClass(review.decision)}`}>
                  {formatDecision(review.decision)}
                </span>
              </div>
              {review.comments ? <p className="meta">{review.comments}</p> : null}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const getProgressSummary = (item: MentorTrackedThesis) => {
    if (item.thesis.status === "mentor_review") {
      return "等待导师评审";
    }
    if (item.thesis.status === "changes_requested") {
      return item.latest_review?.comments ? "已退回修改，可继续跟进学生处理进度" : "已退回修改";
    }
    if (item.thesis.status === "approved") {
      return "导师已通过，论文任务已完成";
    }
    if (item.thesis.status === "analysis_pending") {
      return "学生已提交新版本，AI 正在处理中";
    }
    if (item.thesis.status === "analysis_done") {
      return "AI 分析已完成，等待学生决定是否提交导师";
    }
    return formatThesisStatus(item.thesis.status);
  };

  const canSubmitReview = versionDetail?.thesis.status === "mentor_review";

  const renderStudentIdentity = (student: {
    name: string | null;
    email: string;
  }) => {
    if (!student.name) {
      return <strong className="identity-email">{student.email}</strong>;
    }

    return (
      <div className="identity-stack">
        <strong>{student.name}</strong>
        <span className="meta identity-email">{student.email}</span>
      </div>
    );
  };

  const pdfPreviewUrl = versionDetail
    ? `${API_BASE_URL}/theses/versions/${versionDetail.version.id}/file`
    : null;

  return (
    <section className="section">
      <h2 className="section-title">导师工作台</h2>

      <div className="mentor-tabs">
        <button
          className={`mentor-tab ${activeTab === "reviews" ? "active" : ""}`}
          onClick={() => { setActiveTab("reviews"); setNotice(null); }}
        >
          待评审
        </button>
        <button
          className={`mentor-tab ${activeTab === "applications" ? "active" : ""}`}
          onClick={() => { setActiveTab("applications"); setNotice(null); }}
        >
          申请审批
          {applications.length > 0 ? (
            <span className="mentor-tab-count">{applications.length}</span>
          ) : null}
        </button>
        <button
          className={`mentor-tab ${activeTab === "students" ? "active" : ""}`}
          onClick={() => { setActiveTab("students"); setNotice(null); }}
        >
          我的学生
        </button>
      </div>

      {activeTab === "reviews" ? (
        <div className="mentor-dashboard">
          <div className="card mentor-sidebar">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">待评审列表</p>
              </div>
            </div>
            {initialLoading && pendingReviews.length === 0 ? (
              <p className="meta">正在加载...</p>
            ) : pendingReviews.length === 0 ? (
              <div className="task-empty">
                <h4>暂无待评审论文</h4>
                <p className="meta">学生提交导师评审后，会在这里显示。</p>
              </div>
            ) : (
              <div className="mentor-review-list">
                {pendingReviews.map((item) => (
                  <button
                    key={item.version.id}
                    type="button"
                    className={`mentor-review-item ${
                      selectedVersionId === item.version.id ? "active" : ""
                    }`}
                    onClick={() => setSelectedVersionId(item.version.id)}
                  >
                    <div className="mentor-review-row">
                      <strong>{item.thesis.title || "未命名论文"}</strong>
                    </div>
                    <p className="meta">
                      学生：{item.thesis.student.name
                        ? `${item.thesis.student.name} (${item.thesis.student.email})`
                        : item.thesis.student.email}
                    </p>
                    <p className="meta">提交时间：{formatTime(item.version.submitted_at)}</p>
                  </button>
                ))}
              </div>
            )}

            <div className="section-heading compact" style={{ marginTop: 24 }}>
              <div>
                <p className="eyebrow">学生论文进度</p>
              </div>
              <button
                className="ghost"
                type="button"
                onClick={() => setProgressPanelOpen((value) => !value)}
              >
                {progressPanelOpen ? "收起" : "展开"}
              </button>
            </div>
            {progressPanelOpen ? (
              <div className="mentor-progress-panel">
                <div className="form" style={{ marginBottom: 12 }}>
                  <input
                    value={progressQuery}
                    onChange={(event) => setProgressQuery(event.target.value)}
                    placeholder="搜索学生姓名、邮箱或论文标题"
                  />
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => void loadTrackedTheses(progressQuery, true)}
                  >
                    搜索
                  </button>
                </div>
                {trackedTheses.length === 0 ? (
                  <p className="meta">当前没有可查看的论文进度。</p>
                ) : (
                  <div className="mentor-review-list">
                    {trackedTheses.map((item) => (
                      <button
                        key={item.current_version.id}
                        type="button"
                        className={`mentor-review-item ${
                          selectedVersionId === item.current_version.id ? "active" : ""
                        }`}
                        onClick={() => setSelectedVersionId(item.current_version.id)}
                      >
                        <div className="mentor-review-row">
                          <strong>{item.thesis.title || "未命名论文"}</strong>
                          <span className={`task-badge task-${item.thesis.status}`}>
                            {formatThesisStatus(item.thesis.status)}
                          </span>
                        </div>
                        <p className="meta">
                          学生：{item.thesis.student.name
                            ? `${item.thesis.student.name} (${item.thesis.student.email})`
                            : item.thesis.student.email}
                        </p>
                        <p className="meta">
                          当前版本：第 {item.current_version.version_no} 版 · {formatTime(item.current_version.submitted_at)}
                        </p>
                        <p className="meta">{getProgressSummary(item)}</p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>

          <div className="mentor-main-column">
            {!versionDetail ? (
              <div className="card">
                <div className="task-empty">
                  <h4>请选择左侧待评审记录</h4>
                  <p className="meta">选择论文后查看分析结果并提交评审意见。</p>
                </div>
              </div>
            ) : (
              <>
                <div className="card">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">论文信息</p>
                      <h3>{versionDetail.thesis.title || "未命名论文"}</h3>
                    </div>
                    <span className={`task-badge task-${versionDetail.thesis.status}`}>
                      {formatThesisStatus(versionDetail.thesis.status)}
                    </span>
                  </div>
                  <div className="task-meta-grid">
                    <div className="task-meta-card">
                      <span className="meta">学生</span>
                      {renderStudentIdentity(versionDetail.thesis.student)}
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">版本号</span>
                      <strong>第 {versionDetail.version.version_no} 版</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">提交时间</span>
                      <strong>{formatTime(versionDetail.version.submitted_at)}</strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">分析状态</span>
                      <strong>
                        {versionDetail.latest_task
                          ? formatTaskStatus(versionDetail.latest_task.status)
                          : "暂无"}
                      </strong>
                    </div>
                    <div className="task-meta-card">
                      <span className="meta">论文阶段</span>
                      <strong>{formatThesisStatus(versionDetail.thesis.status)}</strong>
                    </div>
                  </div>
                  <div className="pdf-preview-actions">
                    <button
                      className="ghost pdf-preview-action"
                      type="button"
                      onClick={() => setPdfPreviewOpen((value) => !value)}
                    >
                      {pdfPreviewOpen ? "收起预览" : "展开预览"}
                    </button>
                    <a
                      className="button-link ghost pdf-preview-action"
                      href={pdfPreviewUrl ?? "#"}
                      target="_blank"
                      rel="noreferrer"
                    >
                      新窗口打开
                    </a>
                  </div>
                </div>

                {pdfPreviewOpen && pdfPreviewUrl ? (
                  <div className="card">
                    <div className="section-heading compact">
                      <div>
                        <p className="eyebrow">论文原件</p>
                        <h4>在线 PDF 预览</h4>
                      </div>
                    </div>
                    <iframe
                      title={`论文预览-${versionDetail.version.id}`}
                      src={pdfPreviewUrl}
                      style={{
                        width: "100%",
                        height: "720px",
                        border: "1px solid var(--border)",
                        borderRadius: "16px",
                        background: "#fff",
                      }}
                    />
                  </div>
                ) : null}

                <div className="card">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">自动分析结果</p>
                      <h4>分析详情</h4>
                    </div>
                  </div>
                  {renderAnalysisResult(versionDetail.latest_task)}
                </div>

                {renderReviews(versionDetail.reviews)}

                <div className="card">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">导师评审</p>
                      <h4>{canSubmitReview ? "提交评审决定" : "当前评审状态"}</h4>
                    </div>
                  </div>
                  {canSubmitReview ? (
                    <form className="form mentor-review-form" onSubmit={handleSubmitReview}>
                      <div>
                        <label>评审决定</label>
                        <div className="mentor-decision-options">
                          <label
                            className={`mentor-decision-option ${
                              decision === "approved" ? "selected" : ""
                            }`}
                          >
                            <input
                              type="radio"
                              name="decision"
                              value="approved"
                              checked={decision === "approved"}
                              onChange={() => setDecision("approved")}
                            />
                            <span>通过</span>
                          </label>
                          <label
                            className={`mentor-decision-option ${
                              decision === "changes_requested" ? "selected" : ""
                            }`}
                          >
                            <input
                              type="radio"
                              name="decision"
                              value="changes_requested"
                              checked={decision === "changes_requested"}
                              onChange={() => setDecision("changes_requested")}
                            />
                            <span>退回修改</span>
                          </label>
                        </div>
                      </div>
                      <div>
                        <label htmlFor="mentor-comments">评审意见</label>
                        <textarea
                          id="mentor-comments"
                          rows={5}
                          value={comments}
                          onChange={(event) => setComments(event.target.value)}
                          placeholder="填写具体修改建议或评审意见..."
                        />
                      </div>
                      <button className="primary" type="submit" disabled={loading}>
                        {loading ? "正在提交..." : "提交评审"}
                      </button>
                    </form>
                  ) : (
                    <div className="task-empty">
                      <h4>{formatThesisStatus(versionDetail?.thesis.status ?? "")}</h4>
                      <p className="meta">
                        {versionDetail?.thesis.status === "changes_requested"
                          ? "这篇论文已经退回给学生修改，当前不能重复提交评审。请等待学生上传新版本后再次审核。"
                          : versionDetail?.thesis.status === "approved"
                            ? "这篇论文已经完成导师审批，当前记录仅供查看，不再接受新的评审决定。"
                            : "当前论文不在导师评审阶段，暂不可提交新的评审决定。"}
                      </p>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      ) : activeTab === "applications" ? (
        <div className="card">
          <div className="section-heading compact">
            <div>
              <p className="eyebrow">申请审批</p>
            </div>
          </div>
          {applications.length === 0 ? (
            <div className="task-empty">
              <h4>暂无待审批的申请</h4>
              <p className="meta">学生申请绑定导师后会在这里显示。</p>
            </div>
          ) : (
            <>
              <div className="issue-list">
                {applications.map((app) => (
                  <div key={app.application.id} className="issue-item">
                    <div className="issue-row">
                      <div>
                        <strong>
                          {app.student.name
                            ? `${app.student.name} (${app.student.email})`
                            : app.student.email}
                        </strong>
                        <p className="meta">申请时间：{formatTime(app.application.created_at)}</p>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                      <button
                        className="primary"
                        onClick={() => handleApproveApplication(app.application.id)}
                      >
                        通过
                      </button>
                      <button
                        className="ghost"
                        onClick={() => handleRejectApplication(app.application.id)}
                      >
                        拒绝
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <p className="meta" style={{ marginTop: 12 }}>
                共 {applications.length} 条申请
              </p>
            </>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="section-heading compact">
            <div>
              <p className="eyebrow">我的学生</p>
            </div>
          </div>
          {students.length === 0 ? (
            <div className="task-empty">
              <h4>暂无已绑定的学生</h4>
              <p className="meta">学生申请并经你批准绑定后会在这里显示。</p>
            </div>
          ) : (
            <>
              <div className="issue-list">
                {students.map((student) => (
                  <div key={student.id} className="issue-item">
                    <div className="issue-row">
                      <strong>
                        {student.name
                          ? `${student.name} (${student.email})`
                          : student.email}
                      </strong>
                    </div>
                    <p className="meta">论文数量：{student.thesis_count}</p>
                    <p className="meta">绑定时间：{formatTime(student.bound_at)}</p>
                  </div>
                ))}
              </div>
              {studentHasMore && (
                <button
                  className="ghost"
                  style={{ marginTop: 12, width: "100%" }}
                  onClick={() => void loadStudents(true)}
                >
                  加载更多
                </button>
              )}
              <p className="meta" style={{ marginTop: 12 }}>
                共 {studentTotal} 名学生
              </p>
            </>
          )}
        </div>
      )}

      {notice ? <div className="notice">{notice}</div> : null}
      {error ? <div className="notice error">{error}</div> : null}
    </section>
  );
}
