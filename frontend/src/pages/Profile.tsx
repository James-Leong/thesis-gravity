import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  MentorListItem,
  StudentApplication,
  UserRead,
  apiFetch,
  formatRoleLabel,
} from "../api/client";

type ProfileProps = {
  user: UserRead | null;
  onUserUpdate: (user: UserRead) => void;
};

export function Profile({ user, onUserUpdate }: ProfileProps) {
  const [name, setName] = useState(user?.name ?? "");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Mentor application state
  const [showMentorSearch, setShowMentorSearch] = useState(false);
  const [mentorSearch, setMentorSearch] = useState("");
  const [mentorList, setMentorList] = useState<MentorListItem[]>([]);
  const [myApplication, setMyApplication] = useState<StudentApplication | null>(null);
  const [searching, setSearching] = useState(false);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    setName(user?.name ?? "");
  }, [user]);

  const loadMyApplication = async () => {
    if (!user || user.role !== "student") return;
    try {
      const app = await apiFetch<StudentApplication>("/mentor/my-application");
      setMyApplication(app);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    void loadMyApplication();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const searchMentors = async (q: string) => {
    setMentorSearch(q);
    if (!q.trim()) {
      setMentorList([]);
      return;
    }
    setSearching(true);
    try {
      const result = await apiFetch<MentorListItem[]>(
        `/mentor/list?q=${encodeURIComponent(q.trim())}`
      );
      setMentorList(result);
    } catch {
      setMentorList([]);
    } finally {
      setSearching(false);
    }
  };

  const handleApplyMentor = async (mentorId: number) => {
    setNotice(null);
    setError(null);
    setApplying(true);
    try {
      await apiFetch("/mentor/applications", {
        method: "POST",
        body: JSON.stringify({ mentor_id: mentorId }),
      });
      setNotice("申请已发送，请等待导师审批。");
      setShowMentorSearch(false);
      setMentorSearch("");
      setMentorList([]);
      await loadMyApplication();
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "申请失败。";
      setError(message);
    } finally {
      setApplying(false);
    }
  };

  const handleSaveProfile = async (event: React.FormEvent) => {
    event.preventDefault();
    setNotice(null);
    setError(null);
    setSaving(true);
    try {
      const updated = await apiFetch<UserRead>("/auth/profile", {
        method: "PUT",
        body: JSON.stringify({ name: name.trim() || null }),
      });
      onUserUpdate(updated);
      setNotice("个人信息已更新。");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "保存失败。";
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return (
      <section className="section auth-section">
        <div className="card">
          <h2 className="section-title">请先登录</h2>
          <p className="meta">登录后可查看和编辑个人信息。</p>
          <div className="hero-actions">
            <Link to="/login" className="primary button-link">
              去登录
            </Link>
          </div>
        </div>
      </section>
    );
  }

  const formatTime = (value?: string) => {
    if (!value) return "暂无";
    return new Date(value).toLocaleString("zh-CN");
  };

  const displayName = (item: MentorListItem) => {
    if (item.name) return `${item.name} (${item.email})`;
    return item.email;
  };

  return (
    <section className="section">
      <h2 className="section-title">个人信息</h2>

      <div className="profile-layout">
        {/* Basic info */}
        <div className="card">
          <div className="section-heading compact">
            <div>
              <p className="eyebrow">基本信息</p>
            </div>
          </div>
          <div className="task-meta-grid">
            <div className="task-meta-card">
              <span className="meta">账号</span>
              <strong>{user.email}</strong>
            </div>
            <div className="task-meta-card">
              <span className="meta">角色</span>
              <strong>{formatRoleLabel(user.role)}</strong>
            </div>
            <div className="task-meta-card">
              <span className="meta">注册时间</span>
              <strong>{formatTime(user.created_at)}</strong>
            </div>
            <div className="task-meta-card">
              <span className="meta">姓名</span>
              <strong>{user.name || "未设置"}</strong>
            </div>
          </div>
        </div>

        {/* Edit profile */}
        <div className="card">
          <div className="section-heading compact">
            <div>
              <p className="eyebrow">编辑信息</p>
            </div>
          </div>
          <form className="form" onSubmit={handleSaveProfile}>
            <div>
              <label htmlFor="profile-name">姓名</label>
              <input
                id="profile-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="请输入你的姓名"
              />
            </div>
            <button
              className="primary"
              type="submit"
              disabled={saving}
              style={{ justifySelf: "start", minWidth: 120 }}
            >
              {saving ? "正在保存..." : "保存"}
            </button>
          </form>
        </div>

        {/* Mentor application (students only) */}
        {user.role === "student" ? (
          <div className="card">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">导师绑定</p>
              </div>
            </div>

            {myApplication?.has_application ? (
              myApplication.application?.status === "pending" ? (
                <div
                  className="task-empty"
                  style={{
                    borderColor: "rgba(43, 83, 255, 0.2)",
                    background: "rgba(43, 83, 255, 0.04)",
                  }}
                >
                  <h4>申请审批中</h4>
                  <p className="meta">
                    已向导师{" "}
                    {myApplication.mentor?.name
                      ? `${myApplication.mentor.name} (${myApplication.mentor.email})`
                      : myApplication.mentor?.email}{" "}
                    发送绑定申请，请等待审批。
                  </p>
                </div>
              ) : myApplication.application?.status === "approved" ? (
                <div
                  className="task-empty"
                  style={{
                    borderColor: "rgba(42, 182, 166, 0.4)",
                    background: "rgba(42, 182, 166, 0.06)",
                  }}
                >
                  <h4>已绑定导师</h4>
                  <p className="meta">
                    当前导师：{" "}
                    {myApplication.mentor?.name
                      ? `${myApplication.mentor.name} (${myApplication.mentor.email})`
                      : myApplication.mentor?.email}
                  </p>
                  <p className="meta">
                    绑定时间：{formatTime(myApplication.application?.updated_at)}
                  </p>
                </div>
              ) : (
                <div className="task-empty">
                  <h4>申请已被拒绝</h4>
                  <p className="meta">你可以重新向其他导师发起申请。</p>
                  <button
                    className="primary"
                    style={{ marginTop: 12 }}
                    onClick={() => setShowMentorSearch(true)}
                  >
                    重新申请
                  </button>
                </div>
              )
            ) : (
              <>
                {showMentorSearch ? (
                  <div>
                    <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                      <input
                        type="text"
                        value={mentorSearch}
                        onChange={(e) => searchMentors(e.target.value)}
                        placeholder="搜索导师姓名或邮箱..."
                        autoFocus
                        style={{ flex: 1, minWidth: 200 }}
                      />
                      <button
                        className="ghost"
                        onClick={() => {
                          setShowMentorSearch(false);
                          setMentorSearch("");
                          setMentorList([]);
                        }}
                      >
                        取消
                      </button>
                    </div>
                    {searching ? (
                      <p className="meta">正在搜索...</p>
                    ) : mentorSearch.trim() && mentorList.length === 0 ? (
                      <p className="meta">未找到匹配的导师。</p>
                    ) : (
                      <div className="issue-list">
                        {mentorList.map((mentor) => (
                          <div key={mentor.id} className="issue-item">
                            <div className="issue-row">
                              <strong>{displayName(mentor)}</strong>
                            </div>
                            <button
                              className="primary"
                              style={{ marginTop: 10, padding: "8px 14px", fontSize: 13 }}
                              onClick={() => handleApplyMentor(mentor.id)}
                              disabled={applying}
                            >
                              申请绑定
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="task-empty">
                    <h4>尚未绑定导师</h4>
                    <p className="meta">绑定导师后可以提交论文进行评审。</p>
                    <button
                      className="primary"
                      style={{ marginTop: 12 }}
                      onClick={() => setShowMentorSearch(true)}
                    >
                      查找导师
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        ) : null}
      </div>

      {notice ? <div className="notice">{notice}</div> : null}
      {error ? <div className="notice error">{error}</div> : null}
    </section>
  );
}
