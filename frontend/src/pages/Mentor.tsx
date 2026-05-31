import { useState } from "react";
import { UserRead, apiFetch } from "../api/client";

type MentorProps = {
  user: UserRead;
};

export function Mentor({ user }: MentorProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCreateStudent = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setNotice(null);
    setError(null);
    try {
      const result = await apiFetch<UserRead>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          role: "student",
        }),
      });
      setNotice(`学生账号已创建：${result.email}`);
      setEmail("");
      setPassword("");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "创建学生账号失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="section">
      <h2 className="section-title">导师工作台</h2>
      <div className="card-grid">
        <div className="card">
          <h3>当前导师</h3>
          <p className="meta">登录账号：{user.email}</p>
          <p className="meta">你可以先为学生创建账号，后续再进入评审流程。</p>
        </div>

        <div className="card">
          <h3>添加学生</h3>
          <form className="form" onSubmit={handleCreateStudent}>
            <div>
              <label htmlFor="student-email">学生邮箱</label>
              <input
                id="student-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="student@example.edu"
                required
              />
            </div>
            <div>
              <label htmlFor="student-password">初始密码</label>
              <input
                id="student-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="至少 8 个字符"
                required
                minLength={8}
              />
            </div>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? "正在创建..." : "创建学生账号"}
            </button>
          </form>
        </div>

        <div className="card">
          <h3>流程说明</h3>
          <p className="meta">1. 导师先为学生创建账号。</p>
          <p className="meta">2. 学生登录后进入学生工作台提交论文草稿。</p>
          <p className="meta">3. 后续将补齐导师查看版本与提交评审的流程。</p>
        </div>
      </div>

      {notice ? <div className="notice">{notice}</div> : null}
      {error ? <div className="notice error">{error}</div> : null}
    </section>
  );
}
