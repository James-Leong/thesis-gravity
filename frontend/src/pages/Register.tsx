import { useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch, UserRead } from "../api/client";

export function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("student");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiFetch<UserRead>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, role }),
      });
      setNotice(`账号创建成功：${result.email}。`);
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "注册失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="section">
      <h2 className="section-title">注册</h2>
      <div className="card">
        <form className="form" onSubmit={handleSubmit}>
          <p className="meta">
            请先选择你的身份。导师登录后可以创建学生账号，学生登录后进入学生工作台。
          </p>
          <div>
            <label htmlFor="reg-email">邮箱</label>
            <input
              id="reg-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="请输入邮箱"
              required
            />
          </div>
          <div>
            <label htmlFor="reg-password">密码</label>
            <input
              id="reg-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="至少 8 个字符"
              required
              minLength={8}
            />
          </div>
          <div>
            <label htmlFor="reg-role">角色</label>
            <select
              id="reg-role"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              <option value="student">学生</option>
              <option value="mentor">导师</option>
              <option value="academic">教务</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <button className="primary" type="submit" disabled={loading}>
            {loading ? "正在创建..." : "创建账号"}
          </button>
          {notice ? <div className="notice">{notice}</div> : null}
          {error ? <div className="notice error">{error}</div> : null}
          <p className="meta">
            已有账号？<Link to="/login">去登录</Link>
          </p>
        </form>
      </div>
    </section>
  );
}
