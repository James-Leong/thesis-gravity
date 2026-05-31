import { Link } from "react-router-dom";

export function Home() {
  return (
    <div>
      <section className="hero">
        <div>
          <h1>把论文草稿的混乱，变成清晰的修改方向。</h1>
          <p>
            用户先注册账号并选择身份，导师可以先添加学生，登录后系统再按身份进入对应工作台，
            把论文辅导流程和评审流程衔接起来。
          </p>
          <div className="hero-actions">
            <Link to="/login" className="primary button-link">
              立即登录
            </Link>
            <Link to="/register" className="ghost button-link">
              注册账号
            </Link>
          </div>
        </div>
        <div className="card">
          <h3>推荐使用流程</h3>
          <p className="meta">
            系统先完成身份和账号建立，再根据导师或学生的职责进入各自工作台。
          </p>
          <div className="card-grid">
            <div className="card">
              <h4>1. 注册</h4>
              <p className="meta">创建账号并选择学生或导师身份。</p>
            </div>
            <div className="card">
              <h4>2. 登录</h4>
              <p className="meta">登录后由系统自动识别角色并进入工作台。</p>
            </div>
            <div className="card">
              <h4>3. 协作</h4>
              <p className="meta">导师添加学生，学生提交草稿并接收分析反馈。</p>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">为什么要用论文辅导系统</h2>
        <div className="card-grid">
          <div className="card">
            <h3>按角色进入工作台</h3>
            <p className="meta">
              登录后不再暴露公开工作台入口，而是按身份进入对应界面。
            </p>
          </div>
          <div className="card">
            <h3>导师与学生协作清晰</h3>
            <p className="meta">
              导师负责添加学生，学生负责提交论文和查看反馈。
            </p>
          </div>
          <div className="card">
            <h3>结构化分析链路</h3>
            <p className="meta">
              草稿提交后自动进入分析任务，并返回结构化结果。
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
