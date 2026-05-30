import { Link } from "react-router-dom";

export function Home() {
  return (
    <div>
      <section className="hero">
        <div>
          <h1>把论文草稿的混乱，变成清晰的修改方向。</h1>
          <p>
            论文辅导系统将结构化智能分析与导师评审流程结合起来，让学生知道下一步该做什么，
            也让导师把精力集中在真正的学术质量上。
          </p>
          <div className="hero-actions">
            <Link to="/login" className="primary button-link">
              立即登录
            </Link>
            <Link to="/student" className="ghost button-link">
              学生工作台
            </Link>
          </div>
        </div>
        <div className="card">
          <h3>上传之后会发生什么？</h3>
          <p className="meta">
            草稿会变成一个版本，版本会生成分析任务，任务会返回结构化反馈，方便直接处理。
          </p>
          <div className="card-grid">
            <div className="card">
              <h4>1. 提交</h4>
              <p className="meta">一次完成 PDF 和标题上传。</p>
            </div>
            <div className="card">
              <h4>2. 分析</h4>
              <p className="meta">Agno 返回按页拆分的问题与建议。</p>
            </div>
            <div className="card">
              <h4>3. 处理</h4>
              <p className="meta">修改、重新提交，或发送给导师评审。</p>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">为什么要用论文辅导系统</h2>
        <div className="card-grid">
          <div className="card">
            <h3>结构化分析结果</h3>
            <p className="meta">
              输出结果有固定结构，便于导师直接查看和处理。
            </p>
          </div>
          <div className="card">
            <h3>面向角色的访问控制</h3>
            <p className="meta">
              学生、导师、教务和管理员都能在各自权限范围内工作。
            </p>
          </div>
          <div className="card">
            <h3>FastAPI 后端基座</h3>
            <p className="meta">
              每个流程都有安全、可审计的接口支撑。
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
