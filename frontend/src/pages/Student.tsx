import { useState } from "react";
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
  const [taskId, setTaskId] = useState("");
  const [task, setTask] = useState<AnalysisTask | null>(null);
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
      setTaskId(String(result.task.id));
      setTask(result.task);
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

  const handleTaskCheck = async () => {
    setNotice(null);
    setError(null);
    if (!requireToken()) return;
    if (!taskId) {
      setError("请先输入任务编号。");
      return;
    }
    setLoading(true);
    try {
      const result = await apiFetch<AnalysisTask>(`/tasks/${taskId}`);
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

  return (
    <section className="section">
      <h2 className="section-title">学生工作台</h2>
      {!authChecked ? <div className="notice">正在检查登录状态...</div> : null}
      <div className="card-grid">
        <div className="card">
          <h3>提交草稿</h3>
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
                onChange={(event) =>
                  setFile(event.target.files?.[0] ?? null)
                }
                required
              />
            </div>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? "正在提交..." : "提交草稿"}
            </button>
          </form>
        </div>

        <div className="card">
          <h3>查看分析任务</h3>
          <div className="form">
            <div>
              <label htmlFor="task-id">任务编号</label>
              <input
                id="task-id"
                value={taskId}
                onChange={(event) => setTaskId(event.target.value)}
                placeholder="任务编号"
              />
            </div>
            <button className="ghost" onClick={handleTaskCheck} disabled={loading}>
              刷新状态
            </button>
            {task ? (
              <div className="notice">
                <strong>状态：</strong> {task.status}
                {task.result ? (
                  <div className="meta">
                    <p>{task.result.summary}</p>
                    <p>是否可交导师：{String(task.result.ready_for_mentor)}</p>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="card">
          <h3>通知</h3>
          <button className="ghost" onClick={handleNotifications} disabled={loading}>
            加载通知
          </button>
          <div className="form">
            {notifications.length === 0 ? (
              <p className="meta">尚未加载通知。</p>
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

      {notice ? <div className="notice">{notice}</div> : null}
      {error ? <div className="notice error">{error}</div> : null}
    </section>
  );
}
