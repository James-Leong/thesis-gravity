import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <section className="section">
      <div className="card">
        <h2>页面未找到</h2>
        <p className="meta">你请求的页面不存在。</p>
        <Link to="/" className="ghost button-link">
          返回首页
        </Link>
      </div>
    </section>
  );
}
