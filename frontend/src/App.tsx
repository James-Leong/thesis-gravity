import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import { UserRead, apiFetch, formatRoleLabel } from "./api/client";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { NotFound } from "./pages/NotFound";
import { Profile } from "./pages/Profile";
import { Register } from "./pages/Register";
import { Workspace } from "./pages/Workspace";

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
    () => (user ? `已登录：${formatRoleLabel(user.role)}` : "未登录"),
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
            {user ? <NavLink to="/workspace">工作台</NavLink> : null}
            {user ? <NavLink to="/profile">个人信息</NavLink> : null}
            {!user ? <NavLink to="/login">登录</NavLink> : null}
            {!user ? <NavLink to="/register">注册</NavLink> : null}
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
              path="/workspace"
              element={<Workspace user={user} authChecked={authChecked} />}
            />
            <Route
              path="/profile"
              element={<Profile user={user} onUserUpdate={handleAuth} />}
            />
            <Route path="/student" element={<Navigate to="/workspace" replace />} />
            <Route path="/mentor" element={<Navigate to="/workspace" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>

        <footer className="footer">
          <span>论文辅导系统 · 后端基于 FastAPI</span>
        </footer>
      </div>
    </BrowserRouter>
  );
}
