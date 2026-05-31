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
        setTask(selected);
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

  const getTaskHeadline = () => {
    if (!task) {
      return "还没有加载论文任务";
    }
    if (task.status === "completed" && task.result?.ready_for_mentor) {
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
    if (task.status === "completed" && task.result?.ready_for_mentor) {
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
                  ? task.result.ready_for_mentor
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
                  <p className="eyebrow">当前查看</p>
                  <h4>{getTaskLabel(task)}</h4>
                  <p className="meta">提交时间：{formatTime(task?.created_at)}</p>
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
                        <p className="meta">总体评估：{task.result.overall_assessment}</p>
                        <p className="meta">
                          下一步判断：{task.result.ready_for_mentor ? "可以进入导师评审" : "建议继续修改后再提交"}
                        </p>
                      </div>

                      <div className="task-summary-card">
                        <h4>问题与修改建议</h4>
                        {task.result.issues.length === 0 ? (
                          <p className="meta">当前没有识别到明确问题，可以结合导师意见或自查后再决定是否提交。</p>
                        ) : (
                          <div className="issue-list">
                            {task.result.issues.map((issue, index) => (
                              <div key={`${issue.page}-${index}`} className="issue-item">
                                <div className="issue-row">
                                  <strong>
                                    第 {issue.page} 页 · {issue.issue_type}
                                  </strong>
                                  <span className="issue-severity">{issue.severity}</span>
                                </div>
                                <p>{issue.description}</p>
                                <p className="meta">建议修改：{issue.suggestion}</p>
                              </div>
                            ))}
                          </div>
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
                      onClick={() => {
                        setTask(item);
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

            <div className="card">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">快速操作</p>
                  <h3>提交新稿</h3>
                </div>
              </div>
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
          </div>
        </div>
      </div>

      {notice ? <div className="notice">{notice}</div> : null}
      {error ? <div className="notice error">{error}</div> : null}
    </section>
  );
}
