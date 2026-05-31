import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UserRead, apiFetch } from "../api/client";

type LoginProps = {
  onAuth: (user: UserRead | null) => void;
};

export function Login({ onAuth }: LoginProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiFetch<UserRead>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      onAuth(result);
      setNotice("登录成功，已写入安全会话 Cookie。");
      navigate("/workspace");
    } catch (err) {
      const message =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : "登录失败。";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="section">
      <h2 className="section-title">登录</h2>
      <div className="card">
        <form className="form" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="email">邮箱</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="请输入邮箱"
              required
            />
          </div>
          <div>
            <label htmlFor="password">密码</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入密码"
              required
            />
          </div>
          <button className="primary" type="submit" disabled={loading}>
            {loading ? "正在登录..." : "登录"}
          </button>
          {notice ? <div className="notice">{notice}</div> : null}
          {error ? <div className="notice error">{error}</div> : null}
        </form>
      </div>
    </section>
  );
}
