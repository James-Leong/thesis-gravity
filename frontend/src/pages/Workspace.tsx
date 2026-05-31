import { Link } from "react-router-dom";
import { UserRead, formatRoleLabel } from "../api/client";
import { Mentor } from "./Mentor";
import { Student } from "./Student";

type WorkspaceProps = {
  user: UserRead | null;
  authChecked: boolean;
};

export function Workspace({ user, authChecked }: WorkspaceProps) {
  if (!authChecked) {
    return <div className="notice">正在检查登录状态...</div>;
  }

  if (!user) {
    return (
      <section className="section">
        <div className="card">
          <h2 className="section-title">请先登录</h2>
          <p className="meta">登录后，系统会根据你的身份进入对应工作台。</p>
          <div className="hero-actions">
            <Link to="/login" className="primary button-link">
              去登录
            </Link>
            <Link to="/register" className="ghost button-link">
              去注册
            </Link>
          </div>
        </div>
      </section>
    );
  }

  if (user.role === "student") {
    return <Student user={user} authChecked={authChecked} />;
  }

  if (user.role === "mentor") {
    return <Mentor user={user} />;
  }

  return (
    <section className="section">
      <div className="card">
        <h2 className="section-title">{formatRoleLabel(user.role)}工作台</h2>
        <p className="meta">当前身份的专属工作台前端尚未实现。</p>
      </div>
    </section>
  );
}
