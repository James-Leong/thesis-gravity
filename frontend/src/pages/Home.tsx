import { Link } from "react-router-dom";
import { UserRead } from "../api/client";

type HomeProps = {
  authChecked: boolean;
  user: UserRead | null;
};

export function Home({ authChecked, user }: HomeProps) {
  const isSignedIn = authChecked && Boolean(user);

  return (
    <div>
      <section className="hero">
        <div className="hero-copy">
          <h1>把论文草稿的混乱，变成清晰的修改方向。</h1>
          <p>
            上传 PDF 草稿，快速定位格式、表达与结构问题；导师评审与版本进度集中跟踪。
          </p>
          <div className="hero-actions">
            {isSignedIn ? (
              <>
                <Link to="/workspace" className="primary button-link">
                  进入工作台
                </Link>
                <Link to="/profile" className="ghost button-link">
                  个人信息
                </Link>
              </>
            ) : (
              <>
                <Link to="/login" className="primary button-link">
                  立即登录
                </Link>
                <Link to="/register" className="ghost button-link">
                  注册账号
                </Link>
              </>
            )}
          </div>
        </div>
        <div className="card home-flow-panel">
          <h3>论文辅导流程</h3>
          <p className="meta">
            从草稿分析到导师评审，围绕同一篇论文持续推进。
          </p>
          <div className="flow-list">
            <div className="flow-step">
              <span className="flow-index">1</span>
              <div>
                <h4>提交草稿</h4>
                <p className="meta">学生上传 PDF，系统生成结构化分析结果。</p>
              </div>
            </div>
            <div className="flow-step">
              <span className="flow-index">2</span>
              <div>
                <h4>按清单修改</h4>
                <p className="meta">问题按页码、优先级和依据展示。</p>
              </div>
            </div>
            <div className="flow-step">
              <span className="flow-index">3</span>
              <div>
                <h4>提交评审</h4>
                <p className="meta">学生申请绑定导师，审批后进入评审闭环。</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">为什么要用论文辅导系统</h2>
        <div className="card-grid">
          <div className="card">
            <h3>分析结果更好落地</h3>
            <p className="meta">
              反馈按问题、依据、页码组织，便于逐项修改。
            </p>
          </div>
          <div className="card">
            <h3>导师协作更清晰</h3>
            <p className="meta">
              学生绑定导师后提交评审，导师可查看版本并给出意见。
            </p>
          </div>
          <div className="card">
            <h3>版本进度可追踪</h3>
            <p className="meta">
              每次上传都保留版本记录，修改、评审和通知形成闭环。
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
