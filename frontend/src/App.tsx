import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { UserRead, apiFetch } from "./api/client";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { NotFound } from "./pages/NotFound";
import { Register } from "./pages/Register";
import { Student } from "./pages/Student";

export function App() {
  const [user, setUser] = useState<UserRead | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function loadSession() {
      try {
        const sessionUser = await apiFetch<UserRead>("/auth/me");
        if (mounted) {
          setUser(sessionUser);
        }
      } catch {
        if (mounted) {
          setUser(null);
        }
      } finally {
        if (mounted) {
          setAuthChecked(true);
        }
      }
    }

    void loadSession();

    return () => {
      mounted = false;
    };
  }, []);

  const authStatus = useMemo(
    () => (user ? `已登录：${user.role}` : "未登录"),
    [user]
  );

  const handleAuth = (nextUser: UserRead | null) => {
    setUser(nextUser);
    setAuthChecked(true);
  };

  const handleSignOut = async () => {
    try {
      await apiFetch<void>("/auth/logout", { method: "POST" });
    } finally {
      handleAuth(null);
    }
  };

  return (
    <BrowserRouter>
      <div className="page">
        <div className="ambient">
          <span className="orb orb-one" />
          <span className="orb orb-two" />
          <span className="orb orb-three" />
        </div>

        <header className="nav">
          <div className="brand">
              <span className="brand-dot" />
            <div>
              <p className="brand-title">论文辅导系统</p>
              <p className="brand-sub">论文草稿分析与导师评审</p>
            </div>
          </div>

          <nav className="nav-links">
            <NavLink to="/" end>
              首页
            </NavLink>
            <NavLink to="/student">学生</NavLink>
            <NavLink to="/login">登录</NavLink>
            <NavLink to="/register">注册</NavLink>
          </nav>

          <div className="nav-status">
            <span className="status-pill">{authStatus}</span>
            {user ? (
              <button className="ghost" onClick={() => void handleSignOut()}>
                退出登录
              </button>
            ) : null}
          </div>
        </header>

        <main className="content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login onAuth={handleAuth} />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/student"
              element={<Student user={user} authChecked={authChecked} />}
            />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>

        <footer className="footer">
          <span>论文辅导系统 · 后端基于 FastAPI</span>
          <span>接口地址：localhost:8000</span>
        </footer>
      </div>
    </BrowserRouter>
  );
}
